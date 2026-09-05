"""A thin, read-only wrapper around the local `git` executable."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.gitlog.models import BACKEND, FRONTEND, UNKNOWN, Commit, Identity

RECORD = "\x1e"
FIELD = "\x1f"

# Ordered by preference; the first one that resolves becomes the trunk.
TRUNK_CANDIDATES = ("origin/main", "origin/master", "main", "master", "origin/develop", "develop")

_BACKEND_MARKERS = ("*.csproj", "*.sln", "pom.xml", "build.gradle", "go.mod", "Cargo.toml", "requirements.txt", "pyproject.toml")
_FRONTEND_MARKERS = ("package.json", "angular.json", "vite.config.ts", "next.config.js")

_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(spec|test)\.[a-z]+$|test[^/]*\.(cs|py|java|rb)$", re.IGNORECASE)


class GitError(RuntimeError):
    """Raised when a git invocation fails or a path is not a repository."""


@dataclass(frozen=True)
class GitRepo:
    """Read-only access to one local repository."""

    path: Path
    label: str
    kind: str = UNKNOWN

    @classmethod
    def open(cls, path: Path | str, label: str | None = None, kind: str | None = None) -> "GitRepo":
        resolved = _resolve_worktree(path)
        return cls(
            path=resolved,
            label=label or resolved.name,
            kind=kind or detect_kind(resolved),
        )

    # ----- plumbing -------------------------------------------------

    def _run(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.path), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as error:  # pragma: no cover - environment dependent
            raise GitError("git executable not found on PATH.") from error
        if result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            raise GitError(f"git {' '.join(args[:2])} failed in {self.path}: {detail[0] if detail else 'unknown error'}")
        return result.stdout

    def _run_quiet(self, *args: str) -> str:
        """Like `_run`, but returns an empty string instead of raising."""
        try:
            return self._run(*args)
        except GitError:
            return ""

    # ----- discovery ------------------------------------------------

    def ref_exists(self, ref: str) -> bool:
        return bool(self._run_quiet("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip())

    def trunk(self, preferred: str | None = None) -> str:
        if preferred:
            if not self.ref_exists(preferred):
                raise GitError(f"{self.label}: trunk ref '{preferred}' does not exist.")
            return preferred
        for candidate in TRUNK_CANDIDATES:
            if self.ref_exists(candidate):
                return candidate
        raise GitError(f"{self.label}: could not find a trunk branch; pass --trunk explicitly.")

    def branches(self, include_remote: bool = True) -> list[str]:
        """Branch names, remote-tracking by default, with HEAD pointers removed."""
        args = ["branch", "--format=%(refname:short)"]
        if include_remote:
            args.insert(1, "-r")
        names = [line.strip() for line in self._run_quiet(*args).splitlines() if line.strip()]
        return [n for n in names if "HEAD" not in n.split("/")]

    def identities(self, limit: int = 400) -> list[Identity]:
        """Every author identity in the repository, most frequent first."""
        output = self._run_quiet("log", "--all", "--no-merges", f"--format=%an{FIELD}%ae")
        counts: dict[tuple[str, str], int] = {}
        for line in output.splitlines():
            if FIELD not in line:
                continue
            name, email = line.split(FIELD, 1)
            key = (name.strip(), email.strip().lower())
            counts[key] = counts.get(key, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        return [Identity(name=n, email=e, commits=c) for (n, e), c in ordered[:limit]]

    # ----- history --------------------------------------------------

    def commits(self, ref: str, author_pattern: str | None = None, exclude: str | None = None, with_stats: bool = False) -> list[Commit]:
        """Non-merge commits on `ref`, optionally excluding those reachable from `exclude`."""
        fmt = f"{RECORD}%H{FIELD}%ad{FIELD}%an{FIELD}%ae{FIELD}%s"
        args = ["log", ref]
        if exclude:
            args += ["--not", exclude]
        args += ["--no-merges", "--date=short", f"--format={fmt}"]
        if author_pattern:
            args += ["--regexp-ignore-case", "--extended-regexp", f"--author={author_pattern}"]
        if with_stats:
            args.append("--numstat")
        return _parse_log(self._run_quiet(*args), self.label)

    def count(self, ref: str, author_pattern: str | None = None, exclude: str | None = None) -> int:
        args = ["log", ref]
        if exclude:
            args += ["--not", exclude]
        args += ["--no-merges", "--format=%H"]
        if author_pattern:
            args += ["--regexp-ignore-case", "--extended-regexp", f"--author={author_pattern}"]
        return sum(1 for line in self._run_quiet(*args).splitlines() if line.strip())

    def shas(self, refs: list[str], author_pattern: str | None = None, exclude: str | None = None) -> set[str]:
        """De-duplicated commit hashes across several refs."""
        if not refs:
            return set()
        args = ["log", *refs]
        if exclude:
            args += ["--not", exclude]
        args += ["--no-merges", "--format=%H"]
        if author_pattern:
            args += ["--regexp-ignore-case", "--extended-regexp", f"--author={author_pattern}"]
        return {line.strip() for line in self._run_quiet(*args).splitlines() if line.strip()}

    def contributor_counts(self, ref: str) -> dict[str, int]:
        """Trunk commit counts keyed by lower-cased email."""
        counts: dict[str, int] = {}
        for line in self._run_quiet("log", ref, "--no-merges", "--format=%ae").splitlines():
            email = line.strip().lower()
            if email:
                counts[email] = counts.get(email, 0) + 1
        return counts

    def path_touches(self, ref: str, author_pattern: str | None = None) -> tuple[int, int]:
        """Returns (test path touches, total path touches) for the given author filter."""
        args = ["log", ref, "--no-merges", "--name-only", "--format="]
        if author_pattern:
            args += ["--regexp-ignore-case", "--extended-regexp", f"--author={author_pattern}"]
        total = 0
        tests = 0
        for line in self._run_quiet(*args).splitlines():
            path = line.strip()
            if not path:
                continue
            total += 1
            if _TEST_PATH.search(path):
                tests += 1
        return tests, total


# ----- helpers ------------------------------------------------------


def _resolve_worktree(path: Path | str) -> Path:
    """Accepts a worktree, a bare repo, or a path ending in `.git`."""
    candidate = Path(path).expanduser().resolve()
    if candidate.name == ".git" and candidate.parent.exists():
        candidate = candidate.parent
    if not candidate.exists():
        raise GitError(f"{candidate} does not exist.")
    probe = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--git-dir"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if probe.returncode != 0:
        raise GitError(f"{candidate} is not a git repository.")
    return candidate


def detect_kind(path: Path) -> str:
    """Guess whether a repository is backend or frontend from build files near the root."""
    for marker in _FRONTEND_MARKERS:
        if any(path.glob(marker)) or any(path.glob(f"*/{marker}")):
            return FRONTEND
    for marker in _BACKEND_MARKERS:
        if any(path.glob(marker)) or any(path.glob(f"*/{marker}")):
            return BACKEND
    return UNKNOWN


_RENAME_SEGMENT = re.compile(r"\{([^{}]*) => ([^{}]*)\}")


def _normalize_path(raw: str) -> str:
    """Resolves numstat rename notation to the destination path.

    git writes renames as `dir/{old => new}/file.ts`, or `old.ts => new.ts` when
    the whole path changed. Counting either verbatim would invent files that
    never existed.
    """
    path = raw.strip()
    if not path:
        return ""
    if "{" in path and " => " in path:
        path = _RENAME_SEGMENT.sub(lambda m: m.group(2), path)
    elif " => " in path:
        path = path.split(" => ", 1)[1]
    return path.replace("//", "/").strip()


def _parse_log(output: str, repo: str) -> list[Commit]:
    """Parses the record-separated log format, with optional trailing numstat lines."""
    commits: list[Commit] = []
    for chunk in output.split(RECORD):
        if not chunk.strip():
            continue
        head, _, tail = chunk.partition("\n")
        parts = head.split(FIELD)
        if len(parts) < 5:
            continue
        sha, raw_date, name, email, subject = parts[0], parts[1], parts[2], parts[3], FIELD.join(parts[4:])
        try:
            when = date.fromisoformat(raw_date.strip())
        except ValueError:
            continue
        insertions = deletions = 0
        paths: list[str] = []
        for line in tail.splitlines():
            fields = line.split("\t")
            if len(fields) != 3:
                continue
            added, removed, path = fields
            insertions += int(added) if added.isdigit() else 0
            deletions += int(removed) if removed.isdigit() else 0
            resolved = _normalize_path(path)
            if resolved:
                paths.append(resolved)
        commits.append(
            Commit(
                sha=sha.strip(),
                date=when,
                author_name=name.strip(),
                author_email=email.strip().lower(),
                subject=subject.strip(),
                repo=repo,
                files=len(paths),
                insertions=insertions,
                deletions=deletions,
                paths=tuple(paths),
            )
        )
    return commits
