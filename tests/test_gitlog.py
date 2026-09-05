"""Tests for local git collection and portfolio aggregation.

The git-backed tests build a small real repository in a temporary directory, so
the subprocess layer and the log parsing are both exercised for real.
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.analysis import portfolio as portfolio_module
from app.gitlog.collect import author_pattern, classify_branch, collect_repo, is_release_cut
from app.gitlog.models import BACKEND, FRONTEND
from app.gitlog.repo import GitError, GitRepo, _normalize_path, _parse_log, detect_kind

FIELD = "\x1f"
RECORD = "\x1e"


# ----- pure helpers -------------------------------------------------


def test_author_pattern_escapes_regex_metacharacters():
    pattern = author_pattern(["a.b@c.com", "x+y@z.io"])
    assert r"a\.b@c\.com" in pattern
    assert r"x\+y@z\.io" in pattern


def test_author_pattern_rejects_empty_input():
    with pytest.raises(ValueError):
        author_pattern(["  ", ""])


@pytest.mark.parametrize(
    "name,expected",
    [
        ("origin/Client/Northwind", "client"),
        ("Client/Contoso", "client"),
        ("origin/RELEASE", "release"),
        ("release/2026-08", "release"),
        ("origin/LEGACY_RELEASE_05_11", "other"),
        ("origin/main", "other"),
        ("feature/clientele-report", "other"),
    ],
)
def test_classify_branch(name, expected):
    assert classify_branch(name) == expected


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("version 9.8.17", True),
        ("Version 8.12.22 (#1166)", True),
        ("Database Version 90810 (#1865)", True),
        ("[PROJ-3480] version check on save", False),
        ("bump versioning tab layout", False),
    ],
)
def test_is_release_cut(subject, expected):
    assert is_release_cut(subject) is expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("src/app/thing.ts", "src/app/thing.ts"),
        ("src/{old => new}/thing.ts", "src/new/thing.ts"),
        ("old/path.ts => new/path.ts", "new/path.ts"),
        ("src/{a => }/thing.ts", "src/thing.ts"),
        ("  spaced.ts  ", "spaced.ts"),
    ],
)
def test_normalize_path_resolves_rename_notation(raw, expected):
    assert _normalize_path(raw) == expected


def test_parse_log_reads_subject_containing_field_separator():
    subject = f"fix: a{FIELD}b"
    raw = f"{RECORD}abc123{FIELD}2026-01-02{FIELD}Dana Reed{FIELD}A@B.com{FIELD}{subject}"
    commits = _parse_log(raw, "repo")
    assert len(commits) == 1
    assert commits[0].subject == subject
    assert commits[0].author_email == "a@b.com"
    assert commits[0].date == date(2026, 1, 2)


def test_parse_log_accumulates_numstat_and_skips_binary_rows():
    raw = (
        f"{RECORD}sha{FIELD}2026-01-02{FIELD}A{FIELD}a@b.com{FIELD}subject\n"
        "10\t2\tsrc/a.ts\n"
        "-\t-\tassets/logo.png\n"
        "5\t1\tsrc/b.ts\n"
    )
    commit = _parse_log(raw, "repo")[0]
    assert commit.insertions == 15
    assert commit.deletions == 3
    assert commit.files == 3
    assert "assets/logo.png" in commit.paths


def test_parse_log_ignores_malformed_records():
    assert _parse_log(f"{RECORD}too{FIELD}few", "repo") == []
    assert _parse_log(f"{RECORD}sha{FIELD}not-a-date{FIELD}A{FIELD}a@b.com{FIELD}s", "repo") == []


def test_detect_kind(tmp_path: Path):
    frontend = tmp_path / "fe"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}", encoding="utf-8")
    assert detect_kind(frontend) == FRONTEND

    backend = tmp_path / "be"
    (backend / "src").mkdir(parents=True)
    (backend / "src" / "Api.csproj").write_text("<Project/>", encoding="utf-8")
    assert detect_kind(backend) == BACKEND


# ----- git-backed -----------------------------------------------------


def _git(path: Path, *args: str, **env: str) -> None:
    import os
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": env.get("when", "2026-01-02T10:00:00"),
        "GIT_COMMITTER_DATE": env.get("when", "2026-01-02T10:00:00"),
        "GIT_AUTHOR_NAME": env.get("name", "Dana Reed"),
        "GIT_AUTHOR_EMAIL": env.get("email", "dana@example.com"),
        "GIT_COMMITTER_NAME": "Committer",
        "GIT_COMMITTER_EMAIL": "committer@example.com",
    }
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, env=environment)
    if result.returncode != 0:
        raise AssertionError(f"git {args}: {result.stderr}")


def _commit(path: Path, filename: str, subject: str, *, name="Dana Reed", email="dana@example.com", when="2026-01-02T10:00:00") -> None:
    (path / filename).parent.mkdir(parents=True, exist_ok=True)
    (path / filename).write_text(f"content for {subject}\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", subject, name=name, email=email, when=when)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    path = tmp_path / "sample"
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "committer@example.com")
    _git(path, "config", "user.name", "Committer")

    _commit(path, "src/app/one.ts", "feat: one (#11)", when="2025-03-01T09:00:00")
    _commit(path, "src/app/two.ts", "fix: two (#12)", when="2026-01-05T09:00:00")
    _commit(path, "tests/one.spec.ts", "test: cover one", when="2026-01-06T09:00:00")
    _commit(path, "src/other.ts", "chore: someone else", name="Other", email="other@example.com", when="2026-01-07T09:00:00")
    _commit(path, "src/app/three.ts", "version 9.8.17", when="2026-02-01T09:00:00")

    _git(path, "checkout", "-b", "Client/Northwind")
    _commit(path, "src/northwind.ts", "[PROJ-1] northwind only", when="2026-03-01T09:00:00")
    _commit(path, "src/northwind2.ts", "[PROJ-2] northwind again", when="2026-03-02T09:00:00")
    _git(path, "checkout", "main")
    return path


def test_open_accepts_dot_git_directory(sample_repo: Path):
    repo = GitRepo.open(sample_repo / ".git")
    assert repo.path == sample_repo.resolve()


def test_open_rejects_non_repository(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitError):
        GitRepo.open(plain)


def test_trunk_detection_and_override(sample_repo: Path):
    repo = GitRepo.open(sample_repo)
    assert repo.trunk() == "main"
    with pytest.raises(GitError):
        repo.trunk("origin/nope")


def test_identities_lists_every_author(sample_repo: Path):
    repo = GitRepo.open(sample_repo)
    emails = {identity.email for identity in repo.identities()}
    assert emails == {"dana@example.com", "other@example.com"}


def test_collect_repo_counts_only_the_subject(sample_repo: Path):
    repo = GitRepo.open(sample_repo, kind=FRONTEND)
    report = collect_repo(repo, ["dana@example.com"], include_branches=False)
    assert report.trunk_commits == 4
    assert all(c.author_email == "dana@example.com" for c in report.commits)


def test_collect_repo_attributes_off_trunk_branch_work(sample_repo: Path):
    repo = GitRepo.open(sample_repo, kind=FRONTEND)
    report = collect_repo(repo, ["dana@example.com"], remote=False)
    assert report.offtrunk_commits == 2
    northwind = next(b for b in report.branches if "Northwind" in b.name)
    assert northwind.mine == 2
    assert northwind.share == 1.0


def test_collect_repo_ranks_the_subject(sample_repo: Path):
    repo = GitRepo.open(sample_repo)
    report = collect_repo(repo, ["dana@example.com"], include_branches=False)
    assert report.rank == 1
    assert len(report.contributors) == 2


def test_collect_repo_measures_test_paths(sample_repo: Path):
    repo = GitRepo.open(sample_repo)
    report = collect_repo(repo, ["dana@example.com"], include_branches=False)
    assert report.test_touches == 1
    assert report.total_touches == 4


# ----- aggregation ----------------------------------------------------


def test_portfolio_totals_and_derived_figures(sample_repo: Path):
    repo = GitRepo.open(sample_repo, kind=FRONTEND)
    report = collect_repo(repo, ["dana@example.com"], remote=False)
    built = portfolio_module.build([report], ["dana@example.com"])

    assert built.commits == 6
    assert built.pull_requests == 2
    assert built.release_cuts == 1
    assert built.first == date(2025, 3, 1)
    assert built.last == date(2026, 3, 2)
    assert [y.year for y in built.years] == [2025, 2026]
    assert {t[0] for t in built.tickets} == {"PROJ"}


def test_portfolio_deduplicates_pull_requests_per_repository():
    from app.gitlog.models import Commit, RepoReport

    def commit(sha: str, subject: str, repo: str) -> Commit:
        return Commit(sha=sha, date=date(2026, 1, 1), author_name="A", author_email="a@b.com", subject=subject, repo=repo)

    first = RepoReport(label="be", path=Path("."), kind=BACKEND, trunk="main",
                       commits=[commit("1", "a (#7)", "be"), commit("2", "b (#7)", "be")])
    second = RepoReport(label="fe", path=Path("."), kind=FRONTEND, trunk="main",
                        commits=[commit("3", "c (#7)", "fe")])

    built = portfolio_module.build([first, second], ["a@b.com"])
    # #7 in two different repositories is two pull requests; twice in one repo is one.
    assert built.pull_requests == 2


def test_portfolio_proportions_split_by_kind():
    from app.gitlog.models import Commit, RepoReport

    def commit(sha: str, repo: str, added: int) -> Commit:
        return Commit(sha=sha, date=date(2026, 1, 1), author_name="A", author_email="a@b.com",
                      subject="s", repo=repo, insertions=added, paths=(f"{repo}/f{sha}.txt",))

    be = RepoReport(label="be", path=Path("."), kind=BACKEND, trunk="main", commits=[commit("1", "be", 90)])
    fe = RepoReport(label="fe", path=Path("."), kind=FRONTEND, trunk="main",
                    commits=[commit("2", "fe", 10), commit("3", "fe", 0)])

    built = portfolio_module.build([be, fe], ["a@b.com"])
    lines = next(p for p in built.proportions if p.label == "Lines added")
    assert lines.share(BACKEND) == pytest.approx(0.9)
    commits = next(p for p in built.proportions if p.label == "Commits")
    assert commits.share(FRONTEND) == pytest.approx(2 / 3)


def test_modules_strip_generic_wrappers():
    from app.gitlog.models import Commit, RepoReport

    commits = [
        Commit(sha=str(i), date=date(2026, 1, 1), author_name="A", author_email="a@b.com",
               subject="s", repo="r", paths=("src/app/planner/edit.ts",))
        for i in range(3)
    ]
    built = portfolio_module.build([RepoReport(label="r", path=Path("."), kind=FRONTEND, trunk="main", commits=commits)], ["a@b.com"])
    assert built.modules[0] == ("planner", 3)


# ----- branch selection regressions -----------------------------------


@pytest.fixture
def many_branches_repo(tmp_path: Path) -> Path:
    """A trunk plus a client branch hidden behind many noisier branches."""
    path = tmp_path / "many"
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "committer@example.com")
    _git(path, "config", "user.name", "Committer")
    _commit(path, "base.txt", "base", when="2026-01-01T09:00:00")

    # A client branch whose commits are also reachable from a later snapshot,
    # which is what made `git log --source` miss it entirely.
    _git(path, "checkout", "-b", "Client/Northwind")
    _commit(path, "q1.txt", "northwind one", when="2026-02-01T09:00:00")
    _commit(path, "q2.txt", "northwind two", when="2026-02-02T09:00:00")
    _commit(path, "q3.txt", "northwind three", when="2026-02-03T09:00:00")
    _git(path, "branch", "RELEASE-SNAPSHOT")

    _git(path, "checkout", "main")
    for index in range(8):
        _git(path, "checkout", "-b", f"feature-{index}")
        _commit(path, f"f{index}.txt", f"feature {index}", when="2026-03-01T09:00:00")
        _commit(path, f"f{index}b.txt", f"feature {index} more", when="2026-03-02T09:00:00")
        _commit(path, f"f{index}c.txt", f"feature {index} again", when="2026-03-03T09:00:00")
        _git(path, "checkout", "main")
    return path


def test_client_branches_survive_the_feature_branch_cap(many_branches_repo: Path):
    """A client branch must be measured even when the cap is exhausted."""
    repo = GitRepo.open(many_branches_repo)
    report = collect_repo(repo, ["dana@example.com"], remote=False, max_branches=1)
    names = {b.name for b in report.branches}
    assert "Client/Northwind" in names
    assert "RELEASE-SNAPSHOT" in names
    northwind = next(b for b in report.branches if b.name == "Client/Northwind")
    assert northwind.mine == 3


def test_feature_branch_cap_is_respected(many_branches_repo: Path):
    repo = GitRepo.open(many_branches_repo)
    report = collect_repo(repo, ["dana@example.com"], remote=False, max_branches=2)
    features = [b for b in report.branches if b.name.startswith("feature-")]
    assert len(features) == 2


def test_branch_totals_count_every_author(many_branches_repo: Path):
    path = many_branches_repo
    _git(path, "checkout", "Client/Northwind")
    _commit(path, "other.txt", "someone else", name="Other", email="other@example.com", when="2026-02-04T09:00:00")
    _git(path, "checkout", "main")

    repo = GitRepo.open(path)
    report = collect_repo(repo, ["dana@example.com"], remote=False)
    northwind = next(b for b in report.branches if b.name == "Client/Northwind")
    assert northwind.mine == 3
    assert northwind.total == 4
    assert northwind.share == pytest.approx(0.75)


def test_portfolio_drops_trivial_branches_and_caps_each_type():
    from app.gitlog.models import BranchStat, RepoReport

    branches = [BranchStat(repo="r", name="Client/Tiny", mine=1, total=1, first=None, last=None)]
    branches += [
        BranchStat(repo="r", name=f"Client/C{i}", mine=20 - i, total=100, first=None, last=None)
        for i in range(15)
    ]
    report = RepoReport(label="r", path=Path("."), kind=BACKEND, trunk="main", branches=branches)
    built = portfolio_module.build([report], ["a@b.com"])

    names = {b.name for b in built.branches}
    assert "Client/Tiny" not in names, "a single-commit branch is noise"
    assert len(built.branches) == 12, "client branches are capped"
