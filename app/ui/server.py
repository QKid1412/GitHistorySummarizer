"""A loopback-only HTTP server backing the report builder UI.

This process reads local repositories and writes files, so the endpoints are
guarded two ways: the socket binds to 127.0.0.1 and never to a routable address,
and every API call must carry the single-use token printed into the page. Without
the token a page on another origin could drive this server through your browser.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from app.analysis import portfolio as portfolio_module
from app.gitlog.collect import collect_repo
from app.gitlog.repo import GitError, GitRepo
from app.report import build as report_build
from app.report.build import PROSE, REDACTION, TEAM, JobConfig
from app.report.html import DETAILED, SHAREABLE
from app.ui.page import render

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY = 1 << 20


class Api:
    """The operations the page can trigger. Pure of HTTP concerns."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ----- endpoints ------------------------------------------------

    def detect(self, payload: dict) -> dict:
        repos = self._open(payload.get("repos") or [])
        merged: dict[str, dict] = {}
        described = []

        for repo in repos:
            described.append({"label": repo.label, "kind": repo.kind, "path": str(repo.path)})
            for identity in repo.identities():
                row = merged.setdefault(
                    identity.email, {"name": identity.name, "email": identity.email, "commits": 0}
                )
                row["commits"] += identity.commits

        identities = sorted(merged.values(), key=lambda row: row["commits"], reverse=True)
        return {"repos": described, "identities": identities[:60]}

    def generate(self, payload: dict) -> dict:
        repos = self._open(payload.get("repos") or [])
        authors = [a.strip() for a in (payload.get("authors") or []) if a and a.strip()]

        requested = payload.get("versions")
        if isinstance(requested, str):
            requested = [requested]
        versions = tuple(v for v in (requested or []) if v in (DETAILED, SHAREABLE, TEAM))
        if not versions:
            versions = (DETAILED, SHAREABLE)

        # The team report profiles everyone, so it needs no subject identity.
        if any(v in (DETAILED, SHAREABLE) for v in versions) and not authors:
            raise ValueError(
                "The detailed and shareable versions need your identity. Type your email, tick one "
                "below, or generate only the team report."
            )

        out_root = Path(str(payload.get("output") or "").strip()).expanduser()
        if not str(out_root):
            raise ValueError("Choose a folder to save into.")

        use_ai = bool(payload.get("useAi"))
        api_key = str(payload.get("apiKey") or "")
        prose = _job(payload.get("prose"))
        redaction = _job(payload.get("redaction"))
        # A per-job key on its own is enough; the shared one is a convenience.
        if use_ai and not any(k.strip() for k in (api_key, prose.api_key, redaction.api_key)):
            raise ValueError("AI drafting is on but no API key was supplied.")

        # One run at a time: two concurrent runs would fight over git and the
        # progress the page shows would be meaningless.
        with self._lock:
            reports = []
            if any(v in (DETAILED, SHAREABLE) for v in versions):
                for repo in repos:
                    reports.append(collect_repo(repo, patterns=authors, max_branches=25))

                total = sum(r.trunk_commits + r.offtrunk_commits for r in reports)
                if total == 0:
                    raise ValueError(
                        "No commits matched those identities. Use Detect identities to see what is "
                        "in these repositories."
                    )

            built = portfolio_module.build(reports, authors)
            options = report_build.Options(
                title=str(payload.get("title") or "").strip() or _default_title(reports),
                subtitle=str(payload.get("subtitle") or "").strip() or None,
                shareable_title=str(payload.get("shareableTitle") or "").strip() or None,
                author_name=str(payload.get("authorName") or "").strip() or None,
                team_title=str(payload.get("teamTitle") or "").strip() or None,
                top=max(1, min(int(payload.get("top") or 8), 100)),
                versions=versions,
                use_ai=use_ai,
                api_key=api_key,
                model=str(payload.get("model") or "").strip() or report_build.DEFAULT_MODEL,
                base_url=str(payload.get("baseUrl") or "").strip() or report_build.DEFAULT_BASE_URL,
                prose=prose,
                redaction=redaction,
            )

            run = out_root / datetime.now().strftime("%Y-%m-%d_%H%M%S")
            suffix = 1
            while run.exists():
                run = out_root / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{suffix:02d}"
                suffix += 1

            result = report_build.generate(built, run, options, repos=repos)

        files = []
        for path in result.files:
            sensitive = (path.name == "redaction-key.txt" or "detailed" in path.parts
                         or "team" in path.parts)
            version = next((v for v in ("shareable", "team", "detailed") if v in path.parts), "detailed")
            files.append({
                "path": str(path),
                "version": version,
                "sensitive": sensitive,
                "openable": path.suffix in (".html", ".md", ".txt", ".json"),
            })

        ranks = "; ".join(
            f"{label}: ranked {rank} of {contributors}"
            for label, rank, contributors in built.ranks() if rank
        )
        if built.commits:
            summary = (
                f"<strong>{built.commits:,} commits</strong>, {built.pull_requests:,} pull requests, "
                f"{built.distinct_files:,} distinct files."
            )
            if ranks:
                summary += f"<br>{ranks} trunk contributors."
        else:
            summary = f"<strong>Team report written</strong> for the top {options.top} contributors."

        return {"summary": summary, "files": files, "warnings": result.warnings}

    def prompts(self, payload: dict) -> dict:
        """The built-in system prompts, so the page can show what instructions append to."""
        from app.report import narrative
        return {"prose": narrative.STREAM_SYSTEM, "redaction": narrative.TERMS_SYSTEM}

    def browse(self, payload: dict) -> dict:
        """Opens a native folder picker. The server is local, so this is the user's own desktop."""
        try:
            import tkinter
            from tkinter import filedialog
        except ImportError:
            raise ValueError("No folder picker is available in this Python build. Type the path instead.")

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            chosen = filedialog.askdirectory(title="Choose a folder")
        finally:
            root.destroy()
        return {"path": chosen or ""}

    def open_path(self, payload: dict) -> dict:
        target = Path(str(payload.get("path") or ""))
        if not target.exists():
            raise ValueError(f"{target} no longer exists.")
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", str(target)], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"opened": str(target)}

    # ----- helpers --------------------------------------------------

    @staticmethod
    def _open(paths: list) -> list[GitRepo]:
        cleaned = [str(p).strip() for p in paths if str(p).strip()]
        if not cleaned:
            raise ValueError("Add at least one repository.")
        repos = [GitRepo.open(Path(p)) for p in cleaned]

        seen: dict[str, int] = {}
        resolved: list[GitRepo] = []
        for repo in repos:
            count = seen.get(repo.label, 0)
            seen[repo.label] = count + 1
            label = repo.label if count == 0 else f"{repo.label} ({count + 1})"
            resolved.append(GitRepo(path=repo.path, label=label, kind=repo.kind))
        return resolved


def _job(raw) -> JobConfig:
    """Reads one job's optional provider overrides from the request body."""
    data = raw if isinstance(raw, dict) else {}
    return JobConfig(
        api_key=str(data.get("apiKey") or ""),
        model=str(data.get("model") or "").strip(),
        base_url=str(data.get("baseUrl") or "").strip(),
        instructions=str(data.get("instructions") or ""),
    )


def _default_title(reports) -> str:
    names = [r.label for r in reports]
    if len(names) == 1:
        return f"{names[0]} contribution record"
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} and {len(names) - 1} other repositories"


def make_handler(token: str, api: Api):
    routes = {
        "/api/detect": api.detect,
        "/api/generate": api.generate,
        "/api/prompts": api.prompts,
        "/api/browse": api.browse,
        "/api/open": api.open_path,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "ReportBuilder/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # noqa: A003 - quieten the default access log
            pass

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, render(token).encode("utf-8"), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "Not found."})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            handler = routes.get(path)
            if handler is None:
                return self._json(404, {"error": "Not found."})
            if self.headers.get("X-Token") != token:
                return self._json(403, {"error": "Bad or missing token. Reload the page this server printed."})

            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json(400, {"error": "Bad Content-Length."})
            if length > MAX_BODY:
                return self._json(413, {"error": "Request too large."})

            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, OSError):
                return self._json(400, {"error": "Malformed JSON body."})

            try:
                self._json(200, handler(payload))
            except (GitError, ValueError) as error:
                self._json(400, {"error": str(error)})
            except Exception as error:  # noqa: BLE001 - the UI must show something useful
                self._json(500, {"error": f"{type(error).__name__}: {error}"})

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def serve(port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    token = secrets.token_urlsafe(24)
    server = HTTPServer((HOST, port), make_handler(token, Api()))
    url = f"http://{HOST}:{server.server_port}/"

    print("Contribution Report Builder")
    print(f"  {url}")
    print("  Bound to loopback only. Press Ctrl+C to stop.\n")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
