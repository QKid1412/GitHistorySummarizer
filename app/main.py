"""Command line interface for the local git contribution analyzer.

Reads one or more local repositories and writes a portfolio report. Nothing is
uploaded and no language model is involved.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.analysis import portfolio as portfolio_module
from app.gitlog.collect import collect_repo
from app.gitlog.models import BACKEND, FRONTEND, UNKNOWN
from app.gitlog.repo import GitError, GitRepo
from app.report import build as report_build
from app.report.build import PROSE, REDACTION, TEAM, JobConfig
from app.report.html import DETAILED, SHAREABLE

KINDS = (BACKEND, FRONTEND, UNKNOWN)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="Turn local git history into a portfolio report. Offline; no API keys required.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    authors = commands.add_parser("authors", help="List author identities found in the repositories.")
    _add_repo_args(authors)
    authors.add_argument("--limit", type=_positive, default=25, help="Identities to show per repository.")

    analyze = commands.add_parser("analyze", help="Analyze a subject author and write a report.")
    _add_repo_args(analyze)
    analyze.add_argument("--author", action="append", metavar="PATTERN",
                         help="Email or name fragment identifying you. Repeat for each identity you have committed under. Required unless --version team.")
    analyze.add_argument("--title", default=None, help="Report title. Defaults to a title built from the repository names.")
    analyze.add_argument("--subtitle", default=None, help="One-line standfirst under the title.")
    analyze.add_argument("--output", type=Path, default=Path("output"), help="Base directory for timestamped reports.")
    analyze.add_argument("--version", action="append", choices=("detailed", "shareable", "team", "both", "all"),
                         help="Which versions to write; repeatable. 'detailed' keeps real names, 'shareable' replaces them and adds a drafting guide, 'team' profiles the whole contributor list. Defaults to detailed+shareable.")
    analyze.add_argument("--top", type=_positive, default=8, help="Contributors to profile in the team report (default 8).")
    analyze.add_argument("--team-title", default=None, help="Title for the team report.")
    analyze.add_argument("--api-key", default="", metavar="KEY",
                         help="Enable AI-drafted prose and generic redaction. Sends directory names, branch names and commit subjects to the provider. Omit to stay fully offline.")
    analyze.add_argument("--model", default=report_build.DEFAULT_MODEL, help="Model name, used only with --api-key.")
    analyze.add_argument("--base-url", default=report_build.DEFAULT_BASE_URL, help="OpenAI-compatible endpoint, used only with --api-key.")
    for job, what in (("prose", "work-stream prose"), ("redact", "redaction wording")):
        analyze.add_argument(f"--{job}-api-key", default="", metavar="KEY",
                             help=f"Use a different key for {what}. Defaults to --api-key.")
        analyze.add_argument(f"--{job}-model", default="", metavar="MODEL",
                             help=f"Use a different model for {what}. Defaults to --model.")
        analyze.add_argument(f"--{job}-base-url", default="", metavar="URL",
                             help=f"Use a different endpoint for {what}. Defaults to --base-url.")
        analyze.add_argument(f"--{job}-instructions", default="", metavar="TEXT",
                             help=f"Extra instructions appended to the built-in {what} prompt. The built-in rules still apply.")
        analyze.add_argument(f"--{job}-instructions-file", type=Path, default=None, metavar="PATH",
                             help=f"Read the {what} instructions from a file instead.")
    analyze.add_argument("--no-branches", action="store_true", help="Skip off-trunk branch analysis. Much faster on large repositories.")
    analyze.add_argument("--max-branches", type=_positive, default=25, help="Cap on ordinary feature branches measured. Release and client branches are always measured.")
    analyze.add_argument("--local-branches", action="store_true", help="Analyze local branches instead of remote-tracking ones.")
    return parser


def _add_repo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", action="append", required=True, type=Path, metavar="PATH",
                        help="Path to a repository or its .git directory. Repeat for each repository.")
    parser.add_argument("--label", action="append", metavar="NAME",
                        help="Display name for a repository, in the same order as --repo. Defaults to the directory name.")
    parser.add_argument("--kind", action="append", choices=KINDS, metavar="KIND",
                        help=f"Override detection for a repository, in the same order as --repo. One of: {', '.join(KINDS)}.")
    parser.add_argument("--trunk", action="append", metavar="REF",
                        help="Trunk ref for a repository, in the same order as --repo. Auto-detected when omitted.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repos = _open_repos(args)
        if args.command == "authors":
            return _authors(repos, args.limit)
        return _analyze(repos, args)
    except (GitError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        # Most often an unwritable --output path. A traceback helps nobody here.
        print(f"Error: could not write output: {error}", file=sys.stderr)
        return 2


# ----- commands -----------------------------------------------------


def _authors(repos: list[GitRepo], limit: int) -> int:
    for repo in repos:
        print(f"\n{repo.label}  ({repo.kind})  {repo.path}")
        identities = repo.identities()
        if not identities:
            print("  no commits found")
            continue
        for identity in identities[:limit]:
            print(f"  {identity.commits:>7,}  {identity.name} <{identity.email}>")
        if len(identities) > limit:
            print(f"  ... {len(identities) - limit} more")
    print("\nPick your identities and pass each to analyze with --author, e.g.")
    print("  python -m app.main analyze --repo <path> --author you@work.com --author you@personal.com")
    return 0


def _analyze(repos: list[GitRepo], args: argparse.Namespace) -> int:
    trunks = _per_repo(args.trunk, len(repos), "--trunk")
    versions = _versions(args.version)

    # The team report profiles everyone, so it needs no subject. The personal
    # versions do, and asking for them without one is the likelier mistake.
    personal = [v for v in versions if v in (DETAILED, SHAREABLE)]
    if personal and not args.author:
        raise ValueError(
            "--author is required for the " + " and ".join(personal) + " version(s). "
            "Run the `authors` command to see the identities in these repositories, "
            "or use --version team to profile the whole contributor list instead."
        )

    reports = []
    if personal:
        for index, repo in enumerate(repos):
            print(f"Reading {repo.label} ...", flush=True)
            report = collect_repo(
                repo,
                patterns=args.author,
                trunk=trunks[index],
                include_branches=not args.no_branches,
                remote=not args.local_branches,
                max_branches=args.max_branches,
            )
            found = f"{report.trunk_commits:,} on {report.trunk}"
            if not args.no_branches:
                found += f", {report.offtrunk_commits:,} off-trunk"
            print(f"  {found}")
            reports.append(report)

        if sum(r.trunk_commits + r.offtrunk_commits for r in reports) == 0:
            print("\nNo commits matched. Run the `authors` command to see the identities in these repositories.",
                  file=sys.stderr)
            return 1

    built = portfolio_module.build(reports, args.author or [])
    title = args.title or _default_title(reports) if reports else (args.title or "Contribution record")
    options = report_build.Options(
        title=title,
        subtitle=args.subtitle,
        versions=versions,
        team_title=args.team_title,
        top=args.top,
        use_ai=_ai_requested(args),
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        prose=JobConfig(
            api_key=args.prose_api_key, model=args.prose_model, base_url=args.prose_base_url,
            instructions=_instructions(args.prose_instructions, args.prose_instructions_file),
        ),
        redaction=JobConfig(
            api_key=args.redact_api_key, model=args.redact_model, base_url=args.redact_base_url,
            instructions=_instructions(args.redact_instructions, args.redact_instructions_file),
        ),
    )
    if options.use_ai:
        print("\nAI drafting enabled: directory names, branch names and commit subjects will be")
        print("sent to the provider. No file contents or diffs are sent.")

    run = _run_directory(args.output)
    result = report_build.generate(built, run, options, repos=repos)

    if built.commits:
        print(f"\n{built.commits:,} commits, {built.pull_requests:,} pull requests, "
              f"{built.distinct_files:,} distinct files")
        for label, rank, contributors in built.ranks():
            if rank:
                print(f"  {label}: ranked {rank} of {contributors} trunk contributors")

    for warning in result.warnings:
        print(f"\nNote: {warning}")

    print("")
    for path in result.files:
        print(f"Wrote {path}")

    if DETAILED in versions:
        print("\nThe detailed version reproduces real branch names and paths. Keep it local.")
    if SHAREABLE in versions:
        print("The shareable version uses placeholders; redaction-key.txt maps them back")
        print("and must not be shared.")
    if TEAM in versions:
        print("The team report names colleagues and reads their seniority from commit metadata.")
        print("It is not a performance assessment; keep it internal.")
    return 0


# ----- helpers ------------------------------------------------------


def _open_repos(args: argparse.Namespace) -> list[GitRepo]:
    paths: list[Path] = args.repo
    labels = _per_repo(args.label, len(paths), "--label")
    kinds = _per_repo(args.kind, len(paths), "--kind")
    repos = [GitRepo.open(path, label=labels[i], kind=kinds[i]) for i, path in enumerate(paths)]

    seen: dict[str, int] = {}
    resolved: list[GitRepo] = []
    for repo in repos:
        count = seen.get(repo.label, 0)
        seen[repo.label] = count + 1
        label = repo.label if count == 0 else f"{repo.label} ({count + 1})"
        resolved.append(GitRepo(path=repo.path, label=label, kind=repo.kind))
    return resolved


def _per_repo(values: list[str] | None, count: int, flag: str) -> list[str | None]:
    """Aligns a repeatable option with --repo. One value applies to every repository."""
    if not values:
        return [None] * count
    if len(values) == 1:
        return [values[0]] * count
    if len(values) != count:
        raise ValueError(f"{flag} was given {len(values)} times but --repo was given {count} times.")
    return list(values)


def _ai_requested(args: argparse.Namespace) -> bool:
    return any(str(getattr(args, name, "") or "").strip()
               for name in ("api_key", "prose_api_key", "redact_api_key"))


def _instructions(inline: str, path: Path | None) -> str:
    """Inline text, or the contents of a file. The file wins if both are given."""
    if path:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"Could not read instructions from {path}: {error}") from error
    return inline or ""


def _versions(requested: list[str] | None) -> tuple[str, ...]:
    """Expands the repeatable --version flag, preserving a stable order."""
    if not requested:
        return (DETAILED, SHAREABLE)
    chosen: list[str] = []
    for value in requested:
        for name in {"both": (DETAILED, SHAREABLE), "all": (DETAILED, SHAREABLE, TEAM)}.get(value, (value,)):
            if name not in chosen:
                chosen.append(name)
    return tuple(chosen)


def _default_title(reports) -> str:
    names = [r.label for r in reports]
    if len(names) == 1:
        return f"{names[0]} contribution record"
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} and {len(names) - 1} other repositories"


def _run_directory(base: Path, now: date | None = None) -> Path:
    from datetime import datetime
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    candidate = base / stamp
    suffix = 1
    while candidate.exists():
        candidate = base / f"{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected a positive integer.") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer.")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
