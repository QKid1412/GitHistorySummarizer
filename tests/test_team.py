"""Tests for contributor profiling and the seniority scoring model.

Identity merging is the part most worth testing: getting it wrong splits one
senior engineer into three junior-looking ones, which is a claim about a real
person that the tool would be making on its own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.analysis import team as team_module
from app.gitlog.repo import GitRepo
from app.report import team_html


# ----- identity normalisation ---------------------------------------


@pytest.mark.parametrize(
    "email,expected",
    [
        ("Jane.Doe@work.com", "janedoe"),
        ("jane-doe@personal.io", "janedoe"),
        ("jane_doe+github@work.com", "janedoe"),
        ("jane.doe_external@acme.com", "janedoe"),
    ],
)
def test_mailbox_normalises_to_one_form(email, expected):
    assert team_module.mailbox(email) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Jane Doe", "doejane"),
        ("Doe, Jane", "doejane"),
        ("DESKTOP-AB12\\Jane Doe", "doejane"),
        ("jane doe", "doejane"),
    ],
)
def test_person_key_survives_surname_first_and_machine_prefixes(name, expected):
    assert team_module.person_key(name) == expected


# ----- git-backed ---------------------------------------------------


def _git(path: Path, *args: str, name="Jane Doe", email="jane@work.com", when="2026-01-02T10:00:00") -> None:
    import os
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
    }
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise AssertionError(f"git {args}: {result.stderr}")


def _commit(path: Path, filename: str, subject: str, **who) -> None:
    (path / filename).parent.mkdir(parents=True, exist_ok=True)
    (path / filename).write_text(f"// {subject}\n", encoding="utf-8")
    _git(path, "add", "-A", **who)
    _git(path, "commit", "-m", subject, **who)


@pytest.fixture
def team_repo(tmp_path: Path) -> Path:
    path = tmp_path / "team"
    path.mkdir()
    _git(path, "init", "-b", "main")

    # Jane commits under three identities that must merge into one person.
    _commit(path, "src/orders/view.ts", "orders ui", when="2024-01-02T09:00:00")
    _commit(path, "src/orders/OrderRepository.cs", "orders service",
            name="Doe, Jane", email="jane.doe@corp.com", when="2024-02-02T09:00:00")
    _commit(path, "DbUpdate/Versions/001_orders.sql", "orders schema",
            name="DESKTOP-X1\\jane", email="jane@work.com", when="2024-03-02T09:00:00")
    _commit(path, "src/orders/OrderModel.cs", "orders model", when="2024-04-02T09:00:00")
    _commit(path, "src/orders/version.ts", "version 2.1.0", when="2024-05-02T09:00:00")
    _commit(path, ".github/workflows/ci.yml", "add ci", when="2024-06-02T09:00:00")

    # A second, clearly separate person.
    _commit(path, "src/reports/list.ts", "reports list",
            name="Sam Roe", email="sam@work.com", when="2025-01-02T09:00:00")
    _commit(path, "src/reports/chart.ts", "reports chart",
            name="Sam Roe", email="sam@work.com", when="2025-02-02T09:00:00")

    (path / ".github").mkdir(exist_ok=True)
    (path / ".github" / "CODEOWNERS").write_text("* @jane-doe\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "Create CODEOWNERS", when="2024-07-02T09:00:00")
    return path


def test_identities_merge_into_one_person(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=10)
    names = {p.display for p in people}
    assert len(people) == 2, f"expected two people, got {names}"
    jane = next(p for p in people if "Jane" in p.display)
    assert len(jane.emails) == 2
    assert jane.commits == 7, "all three identities must count toward one person"


def test_display_name_prefers_the_full_form(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=10)
    jane = next(p for p in people if "jane" in p.display.lower())
    assert jane.display == "Jane Doe", "should not surface the machine-prefixed handle"


def test_codeowner_is_detected(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=10)
    jane = next(p for p in people if "Jane" in p.display)
    sam = next(p for p in people if "Sam" in p.display)
    assert jane.codeowner is True
    assert sam.codeowner is False


def test_vertical_ownership_is_detected_across_layers(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=10)
    jane = next(p for p in people if "Jane" in p.display)
    vertical = jane.vertical_modules()
    assert vertical, "orders was touched at ui, service, schema and model"
    assert jane.layers_of(vertical[0][0]), "layer names must be recoverable for the prose"


def test_version_cuts_and_infrastructure_are_counted(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=10)
    jane = next(p for p in people if "Jane" in p.display)
    assert jane.version_cuts == 1
    assert jane.infra.get("ci/deploy", 0) >= 1


def test_top_limits_the_cohort(team_repo: Path):
    assert len(team_module.profile_team([GitRepo.open(team_repo)], top=1)) == 1


# ----- scoring ------------------------------------------------------


def test_codeowner_outranks_a_higher_volume_contributor():
    owner = team_module.Person(name="Owner", commits=100)
    owner.names["Owner"] = 1
    owner.codeowner = True
    owner.first, owner.last = "2018-01-01", "2026-01-01"

    prolific = team_module.Person(name="Prolific", commits=5000)
    prolific.names["Prolific"] = 1
    prolific.first, prolific.last = "2024-01-01", "2026-01-01"

    ranked = team_module.rank([owner, prolific])
    assert ranked[0][0].display == "Owner"
    assert ranked[0][1].by_key("authority").points == 15


def test_every_component_carries_evidence():
    person = team_module.Person(name="A", commits=10)
    person.names["A"] = 1
    person.first, person.last = "2025-01-01", "2026-01-01"
    score = team_module.rank([person])[0][1]
    assert len(score.components) == len(team_module.WEIGHTS)
    assert all(c.evidence for c in score.components), "a score with no evidence cannot be argued with"
    assert all(0 <= c.points <= c.maximum for c in score.components)


def test_best_branch_prefers_meaningful_ownership_over_tiny_snapshots():
    person = team_module.Person(name="A")
    person.branches = {"RELEASE-BACKUP": (17, 17), "RELEASE": (23, 26)}
    assert person.best_branch[0] == "RELEASE", "a 17/17 snapshot must not beat 23/26 on the real line"


def test_best_branch_ignores_branches_that_are_too_small():
    person = team_module.Person(name="A")
    person.branches = {"tiny": (4, 4)}
    assert person.best_branch is None


def test_inactive_person_scores_zero_currency():
    active = team_module.Person(name="Now", commits=10, recent=10)
    active.names["Now"] = 1
    active.first, active.last = "2025-01-01", "2026-01-01"
    gone = team_module.Person(name="Gone", commits=10, recent=0)
    gone.names["Gone"] = 1
    gone.first, gone.last = "2020-01-01", "2021-01-01"

    scores = team_module.score_team([active, gone])
    assert scores[id(gone)].by_key("currency").points == 0
    assert "inactive since" in scores[id(gone)].by_key("currency").evidence


# ----- rendering ----------------------------------------------------


def test_report_renders_with_caveats_and_the_weight_table(team_repo: Path):
    people = team_module.profile_team([GitRepo.open(team_repo)], top=5)
    html = team_html.render(team_module.rank(people), "Contributor record", ["team"])

    assert "Do not use this for a performance conversation" in html
    assert "Signal breakdown" in html
    for key in team_module.WEIGHTS:
        assert key in html, f"{key} must appear so the model is auditable"
    for limit in team_module.LIMITS[:2]:
        assert limit[:40] in html


def test_report_marks_departed_contributors():
    gone = team_module.Person(name="Gone", commits=50, recent=0)
    gone.names["Gone"] = 1
    gone.first, gone.last = "2019-01-01", "2020-06-01"
    html = team_html.render(team_module.rank([gone]), "Record", ["repo"])
    assert "Last commit 2020-06-01" in html


def test_report_escapes_contributor_names():
    person = team_module.Person(name="<script>alert(1)</script>", commits=5)
    person.names["<script>alert(1)</script>"] = 1
    person.first, person.last = "2025-01-01", "2026-01-01"
    html = team_html.render(team_module.rank([person]), "Record", ["repo"])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ----- vendored code exclusion ---------------------------------------


@pytest.fixture
def vendored_repo(tmp_path: Path) -> Path:
    """A person whose volume is mostly a checked-in third-party library."""
    path = tmp_path / "vend"
    path.mkdir()
    _git(path, "init", "-b", "main")
    _commit(path, "src/orders/view.ts", "real work", when="2025-01-02T09:00:00")
    for index in range(6):
        _commit(path, f"shared_lib/scheduler/build/bundle{index}.js", f"bump library {index}",
                when=f"2025-02-0{index + 1}T09:00:00")
    _commit(path, "node_modules/thing/index.js", "vendor drift", when="2025-03-02T09:00:00")
    return path


def test_vendored_paths_are_excluded_from_authorship(vendored_repo: Path):
    person = team_module.profile_team([GitRepo.open(vendored_repo)], top=1)[0]
    assert person.vendored_touches >= 7
    assert person.path_touches == 1, "only the real source file counts as authorship"
    modules = {m.split(":", 1)[-1] for m in person.modules}
    assert not any("shared_lib" in m or "node_modules" in m for m in modules)


def test_vendored_paths_do_not_create_false_vertical_ownership(vendored_repo: Path):
    person = team_module.profile_team([GitRepo.open(vendored_repo)], top=1)[0]
    assert not any("shared_lib" in module for module, _ in person.vertical_modules())


def test_report_discloses_the_exclusion(vendored_repo: Path):
    people = team_module.profile_team([GitRepo.open(vendored_repo)], top=1)
    html = team_html.render(team_module.rank(people), "Record", ["vend"])
    assert "Excluded from authorship" in html
    assert "not authorship" in html


def test_near_tie_is_called_out():
    a = team_module.Person(name="A", commits=100, merges_to_trunk=100, recent=10)
    a.names["A"] = 1
    a.first, a.last = "2020-01-01", "2026-01-01"
    b = team_module.Person(name="B", commits=99, merges_to_trunk=99, recent=10)
    b.names["B"] = 1
    b.first, b.last = "2020-01-01", "2026-01-01"
    html = team_html.render(team_module.rank([a, b]), "Record", ["repo"])
    assert "effectively tied" in html
