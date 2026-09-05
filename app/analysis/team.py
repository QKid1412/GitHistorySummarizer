"""Profiles every contributor to a set of repositories and ranks them by seniority signal.

Two things this module tries hard to get right, because both are easy to get
wrong in ways that quietly slander someone:

1. **Identity merging.** People commit under work, personal and machine-generated
   addresses. Counting those separately splits one senior engineer into three
   junior-looking ones.
2. **Explicit scoring.** The rank comes from named, weighted components, each
   carrying the evidence that produced it, so a reader can disagree with a
   weight rather than with an opaque verdict.

The score orders a list. It does not measure a person; see `LIMITS`.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.gitlog.repo import FIELD, RECORD, GitRepo

# Weight, and what a full score means. Kept together so the model is auditable.
WEIGHTS = {
    "authority": (15, "Named in CODEOWNERS as a reviewer"),
    "integration": (15, "Share of all merges into trunk"),
    "release": (12, "Share of all version-bump commits"),
    "tenure": (10, "Years between first and last commit"),
    "breadth": (10, "Distinct subsystems touched, and backend/frontend balance"),
    "depth": (10, "Owning one subsystem across UI, service, schema and model layers"),
    "infrastructure": (10, "CI, containers, migrations, messaging, caching"),
    "pioneer": (6, "How early they arrived relative to the repository"),
    "branch": (8, "Largest ownership share of a release or client branch"),
    "architecture": (8, "First to introduce a structural dependency"),
    "currency": (8, "Commits in the last twelve months"),
    "testing": (5, "Test-file share of changed paths, against the cohort"),
    "docs": (4, "Documentation and architecture writing"),
}

LIMITS = [
    "Commit counts measure activity, not value. A vendored library bump and a one-line fix to a "
    "pricing rule are both one commit.",
    "Merge counts may reflect repository permissions rather than judgement. Being the person who "
    "clicks merge can mean you are trusted or that you hold the button.",
    "Path counts inflate wherever dependencies are committed to the repository.",
    "Tenure dominates volume. Someone who joined three years ago cannot out-commit someone with "
    "eight years, and that says nothing about either of them.",
    "Terse commit messages are not low rigour; message style tracks team convention and seniority.",
    "Everything that separates good engineers from great ones is missing: review depth, design "
    "influence, mentoring, incident response, and saying no to the wrong feature.",
]

_VERSION_CUT = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?(?:db\s+|database\s+)?version[\s_v]*\d", re.I)
_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(spec|test)\.[a-z]+$|test[^/]*\.(cs|py|java|rb)$", re.I)
_MACHINE = re.compile(r"^[A-Za-z0-9\-]+\\")
_NOISE_DIR = {"src", "app", "lib", "source"}

# Path signatures used to detect vertical ownership: one person carrying a
# subsystem through every layer rather than only its surface.
_LAYERS = {
    "ui": re.compile(r"\.(ts|tsx|html|scss|css|vue|jsx)$", re.I),
    "service": re.compile(r"(Repository|Service|Controller|Handler|UseCase)", re.I),
    "schema": re.compile(r"(DbUpdate|Migrations?|\.sqlproj$|\.sql$|Database/)", re.I),
    "model": re.compile(r"(Model|DTO|Entities|Domain)", re.I),
}

_INFRA = {
    "ci/deploy": re.compile(r"(^|/)\.(github|azure)/|pipelines?/|azure-pipelines|Dockerfile|docker-compose|\.ya?ml$", re.I),
    "migrations": re.compile(r"DbUpdate|Versions/|V_Next|In_Testing|\.sqlproj$", re.I),
    "messaging/cache": re.compile(r"Kafka|Redis|Caching|SignalR|Hangfire|RabbitMQ|ServiceBus", re.I),
    "build": re.compile(r"\.(csproj|sln|props|targets)$|package\.json$|angular\.json$|tsconfig", re.I),
    "auth": re.compile(r"Auth|Identity|Security|Permission|Token|Hash", re.I),
}

# Structural dependencies worth crediting whoever introduced them.
_ARCH_MARKERS = ("Kafka", "Caching", "Redis", "SignalR", "Dockerfile", "playwright", "Hangfire",
                 "docker-compose", "Serilog", "NetTopologySuite")

_DOCS = re.compile(r"(^|/)docs?/|README|ARCHITECTURE|\.md$", re.I)

# Checked-in dependencies and build output. These are real commits, but they are
# not authorship: a vendored scheduler library will otherwise dominate someone's
# module ranking and, worse, register as vertical ownership of a subsystem.
_VENDORED = re.compile(
    r"(^|/)(node_modules|bower_components|vendor|third_party|externals?|packages|"
    r"shared_lib|dist|build|bundles|out|obj|bin|coverage|\.angular|\.nuget)(/|$)"
    r"|\.min\.(js|css)$|-lock\.(json|yaml)$|\.(dll|exe|pdb|map)$",
    re.I,
)


@dataclass
class Person:
    """One contributor, with identities merged."""

    name: str
    emails: set[str] = field(default_factory=set)
    names: Counter = field(default_factory=Counter)
    commits: int = 0
    by_repo: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    first: str = "9999-99-99"
    last: str = "0000-00-00"
    recent: int = 0
    merges_to_trunk: int = 0
    version_cuts: int = 0
    path_touches: int = 0
    vendored_touches: int = 0
    test_touches: int = 0
    doc_touches: int = 0
    modules: Counter = field(default_factory=Counter)
    infra: Counter = field(default_factory=Counter)
    layers_by_module: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    branches: dict[str, tuple[int, int]] = field(default_factory=dict)
    architecture: list[str] = field(default_factory=list)
    codeowner: bool = False
    subjects: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        """Prefers a full 'Given Surname' form over a bare handle or machine login."""
        if not self.names:
            return self.name
        def quality(item: tuple[str, int]) -> tuple[int, int, int]:
            name, count = item
            clean = _MACHINE.sub("", name).strip()
            return (0 if _MACHINE.match(name) else 1, 1 if " " in clean else 0, count)
        best = max(self.names.items(), key=quality)[0]
        clean = _MACHINE.sub("", best).strip()
        if "," in clean:
            surname, _, given = clean.partition(",")
            clean = f"{given.strip()} {surname.strip()}"
        return clean

    @property
    def years(self) -> float:
        try:
            return max((date.fromisoformat(self.last) - date.fromisoformat(self.first)).days / 365.25, 0.1)
        except ValueError:
            return 0.1

    @property
    def per_year(self) -> float:
        return self.commits / self.years

    @property
    def test_ratio(self) -> float:
        return self.test_touches / self.path_touches if self.path_touches else 0.0

    @property
    def active(self) -> bool:
        return self.recent > 0

    @property
    def best_branch(self) -> tuple[str, int, int] | None:
        """The branch where this person's ownership is most meaningful.

        Ranked by commits multiplied by share, not by share alone: owning 17 of
        17 commits on a one-week snapshot branch says far less than owning 23 of
        26 on the release line a customer went live from.
        """
        best = None
        best_weight = 0.0
        for name, (mine, total) in self.branches.items():
            if mine < 5 or total < 10:
                continue
            weight = mine * (mine / total)
            if weight > best_weight:
                best, best_weight = (name, mine, total), weight
        return best

    def vertical_modules(self, minimum: int = 3) -> list[tuple[str, int]]:
        """Subsystems this person touched across at least `minimum` distinct layers."""
        found = [(module, len(layers)) for module, layers in self.layers_by_module.items() if len(layers) >= minimum]
        found.sort(key=lambda item: (-item[1], -self.modules.get(item[0], 0)))
        return found

    def layers_of(self, module: str) -> list[str]:
        """The named layers touched in one subsystem, in stack order."""
        order = ["ui", "service", "model", "schema"]
        found = self.layers_by_module.get(module, set())
        return [layer for layer in order if layer in found]


@dataclass
class Component:
    key: str
    points: float
    maximum: float
    evidence: str


@dataclass
class Score:
    total: float
    components: list[Component]

    def by_key(self, key: str) -> Component | None:
        return next((c for c in self.components if c.key == key), None)


# ----- identity merging ---------------------------------------------


# Role markers organisations append when issuing a second address.
_ROLE_SUFFIXES = ("external", "contractor", "consultant", "ext", "admin")


def mailbox(email: str) -> str:
    """Normalised mailbox, so one person's several addresses collapse to one key.

    Strips punctuation and +tags, then removes two things that commonly get
    appended to a local part: a role marker, and the organisation's own name, as
    in `jane.doe_acme@acme.com`. The organisation name is taken from the
    address's own domain rather than a hardcoded list, so this works for any
    employer without the tool needing to know who they are.
    """
    local, _, domain = email.lower().partition("@")
    head = re.sub(r"[.\-_]", "", local.split("+", 1)[0])

    suffixes = list(_ROLE_SUFFIXES)
    label = domain.split(".")[0] if domain else ""
    if len(label) > 3:
        suffixes.append(re.sub(r"[.\-_]", "", label))

    for suffix in suffixes:
        if suffix and head.endswith(suffix) and len(head) > len(suffix) + 3:
            head = head[: -len(suffix)]
    return head


def person_key(name: str) -> str:
    cleaned = _MACHINE.sub("", name).strip()
    if "," in cleaned:
        surname, _, given = cleaned.partition(",")
        cleaned = f"{given.strip()} {surname.strip()}"
    return "".join(sorted(re.findall(r"[a-z]+", cleaned.lower())))


class _Union:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# ----- collection ---------------------------------------------------


def profile_team(repos: list[GitRepo], top: int = 8, since: str | None = None) -> list[Person]:
    """Reads every repository once and returns the `top` contributors by commit volume."""
    union = _Union()
    raw: list[tuple[str, str, str, str, str, list[str]]] = []

    for repo in repos:
        trunk = repo.trunk()
        fmt = f"{RECORD}%ad{FIELD}%an{FIELD}%ae{FIELD}%s"
        output = repo._run_quiet("log", "--all", "--no-merges", "--date=short", f"--format={fmt}", "--name-only")
        for chunk in output.split(RECORD):
            if not chunk.strip():
                continue
            head, _, tail = chunk.partition("\n")
            parts = head.split(FIELD)
            if len(parts) < 4:
                continue
            when, name, email, subject = parts[0], parts[1], parts[2].lower(), FIELD.join(parts[3:])
            if not re.match(r"\d{4}-\d\d-\d\d$", when):
                continue
            paths = [line.strip() for line in tail.splitlines() if line.strip()]
            raw.append((repo.label, repo.kind, when, name, email, paths))

            union.union("e:" + email, "m:" + mailbox(email))
            key = person_key(name)
            if len(key) > 4:
                union.union("e:" + email, "n:" + key)

    people: dict[str, Person] = {}
    for label, kind, when, name, email, paths in raw:
        root = union.find("e:" + email)
        person = people.setdefault(root, Person(name=name))
        person.emails.add(email)
        person.names[name] += 1
        person.commits += 1
        person.by_repo[label] = person.by_repo.get(label, 0) + 1
        person.by_kind[kind] = person.by_kind.get(kind, 0) + 1
        person.first = min(person.first, when)
        person.last = max(person.last, when)
        if since and when >= since:
            person.recent += 1
        if len(person.subjects) < 600:
            person.subjects.append(f"{when}|{kind}|{name}|{paths[0] if paths else ''}")

        for path in paths:
            if _VENDORED.search(path):
                person.vendored_touches += 1
                continue
            person.path_touches += 1
            if _TEST_PATH.search(path):
                person.test_touches += 1
            if _DOCS.search(path):
                person.doc_touches += 1
            module = _module_of(path)
            if module:
                person.modules[f"{kind}:{module}"] += 1
                for layer, rx in _LAYERS.items():
                    if rx.search(path):
                        person.layers_by_module[f"{kind}:{module}"].add(layer)
            for label_, rx in _INFRA.items():
                if rx.search(path):
                    person.infra[label_] += 1

    ranked = sorted(people.values(), key=lambda p: p.commits, reverse=True)[:top]
    _add_subjects(repos, ranked)
    _add_merges_and_releases(repos, ranked)
    _add_codeowners(repos, ranked)
    _add_architecture(repos, ranked)
    return ranked


def _module_of(path: str) -> str:
    parts = [p for p in path.split("/")[:-1] if p]
    while parts and parts[0].lower() in _NOISE_DIR and len(parts) > 1:
        parts = parts[1:]
    return "/".join(parts[:2]) if parts else ""


def _email_index(people: list[Person]) -> dict[str, Person]:
    return {email: person for person in people for email in person.emails}


def _add_subjects(repos: list[GitRepo], people: list[Person]) -> None:
    """Recent commit subjects, for characterising what each person is doing now."""
    index = _email_index(people)
    for person in people:
        person.subjects = []
    for repo in repos:
        out = repo._run_quiet("log", "--all", "--no-merges", "--date=short", f"--format=%ae{FIELD}%ad{FIELD}%s")
        for line in out.splitlines():
            parts = line.split(FIELD, 2)
            if len(parts) != 3:
                continue
            person = index.get(parts[0].strip().lower())
            if person is None:
                continue
            if _VERSION_CUT.match(parts[2]):
                person.version_cuts += 1
            if len(person.subjects) < 400:
                person.subjects.append(f"{parts[1]}|{repo.kind}|{parts[2]}")


def _add_merges_and_releases(repos: list[GitRepo], people: list[Person]) -> None:
    index = _email_index(people)
    for repo in repos:
        trunk = repo.trunk()
        for line in repo._run_quiet("log", trunk, "--merges", "--format=%ae").splitlines():
            person = index.get(line.strip().lower())
            if person:
                person.merges_to_trunk += 1

        for branch in _significant_branches(repo, trunk):
            counts: Counter = Counter()
            total = 0
            for line in repo._run_quiet("log", branch, "--not", trunk, "--no-merges", "--format=%ae").splitlines():
                email = line.strip().lower()
                if not email:
                    continue
                total += 1
                person = index.get(email)
                if person:
                    counts[id(person)] += 1
            if total < 5:
                continue
            short = branch[len("origin/"):] if branch.startswith("origin/") else branch
            for person in people:
                mine = counts.get(id(person), 0)
                if mine:
                    prev_mine, prev_total = person.branches.get(short, (0, 0))
                    person.branches[short] = (prev_mine + mine, prev_total + total)


def _significant_branches(repo: GitRepo, trunk: str, cap: int = 40) -> list[str]:
    """Release and client branches only; feature branches say little about ownership."""
    from app.gitlog.collect import CLIENT, RELEASE, classify_branch

    names = [n for n in repo.branches(include_remote=True) if n != trunk]
    keep = [n for n in names if classify_branch(n) in (RELEASE, CLIENT)]
    return keep[:cap]


def _add_codeowners(repos: list[GitRepo], people: list[Person]) -> None:
    """CODEOWNERS is the only declared authority a repository usually carries."""
    handles: list[str] = []
    for repo in repos:
        for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
            content = repo._run_quiet("show", f"{repo.trunk()}:{path}")
            if content.strip():
                handles += re.findall(r"@([A-Za-z0-9._\-]+)", content)
    if not handles:
        return
    normalised = {re.sub(r"[.\-_]", "", h).lower() for h in handles}
    for person in people:
        candidates = {mailbox(e) for e in person.emails}
        candidates.add(person_key(person.display))
        for candidate in candidates:
            if any(candidate and (candidate in h or h in candidate) for h in normalised):
                person.codeowner = True
                break


def _add_architecture(repos: list[GitRepo], people: list[Person]) -> None:
    """Credits whoever first added each structural dependency."""
    index = _email_index(people)
    for repo in repos:
        for marker in _ARCH_MARKERS:
            out = repo._run_quiet(
                "log", repo.trunk(), "--diff-filter=A", "--reverse", "--date=short",
                f"--format={RECORD}%ae{FIELD}%ad", "--name-only", "--", f"*{marker}*",
            )
            chunk = out.split(RECORD)[1] if RECORD in out else ""
            if not chunk.strip():
                continue
            head = chunk.partition("\n")[0].split(FIELD)
            if len(head) < 2:
                continue
            person = index.get(head[0].strip().lower())
            if person:
                entry = f"{marker} ({head[1]}, {repo.kind})"
                if entry not in person.architecture:
                    person.architecture.append(entry)


# ----- scoring ------------------------------------------------------


def score_team(people: list[Person]) -> dict[int, Score]:
    """Scores each person relative to the cohort. Returns {id(person): Score}."""
    if not people:
        return {}

    max_merges = max((p.merges_to_trunk for p in people), default=1) or 1
    max_release = max((p.version_cuts for p in people), default=1) or 1
    max_years = max((p.years for p in people), default=1) or 1
    max_infra = max((sum(p.infra.values()) for p in people), default=1) or 1
    max_recent = max((p.recent for p in people), default=1) or 1
    max_docs = max((p.doc_touches for p in people), default=1) or 1
    max_tests = max((p.test_ratio for p in people), default=0.01) or 0.01
    earliest = min((p.first for p in people), default="9999")

    scores: dict[int, Score] = {}
    for person in people:
        parts: list[Component] = []

        def add(key: str, fraction: float, evidence: str) -> None:
            cap = WEIGHTS[key][0]
            parts.append(Component(key, round(min(max(fraction, 0.0), 1.0) * cap, 1), cap, evidence))

        add("authority", 1.0 if person.codeowner else 0.0,
            "Named in CODEOWNERS" if person.codeowner else "Not named in CODEOWNERS")

        add("integration", person.merges_to_trunk / max_merges,
            f"{person.merges_to_trunk:,} merges into trunk")

        add("release", person.version_cuts / max_release,
            f"{person.version_cuts} version-bump commits")

        add("tenure", person.years / max_years, f"{person.years:.1f} years")

        modules = len([m for m, n in person.modules.items() if n >= 20])
        balance = 1 - abs(0.5 - _kind_share(person)) * 2
        add("breadth", min(modules / 25, 1.0) * 0.7 + balance * 0.3,
            f"{modules} subsystems, {_kind_share(person) * 100:.0f}% of commits in one repository kind")

        vertical = person.vertical_modules()
        add("depth", min(len(vertical) / 4, 1.0),
            f"{len(vertical)} subsystems touched across 3+ layers"
            + (f", deepest {vertical[0][0].split(':')[-1]}" if vertical else ""))

        infra_total = sum(person.infra.values())
        add("infrastructure", infra_total / max_infra,
            ", ".join(f"{k} {v:,}" for k, v in person.infra.most_common(3)) or "no infrastructure footprint")

        head_start = _days_between(earliest, person.first)
        add("pioneer", 1 - min(head_start / 2000, 1.0),
            f"first commit {person.first}" + (" (earliest of the cohort)" if person.first == earliest else ""))

        branch = person.best_branch
        add("branch", (branch[1] / branch[2]) if branch else 0.0,
            f"{branch[1]} of {branch[2]} on {branch[0]} ({branch[1] / branch[2] * 100:.0f}%)" if branch
            else "no significant branch ownership")

        add("architecture", min(len(person.architecture) / 3, 1.0),
            "; ".join(person.architecture[:3]) or "introduced no tracked structural dependency")

        add("currency", person.recent / max_recent,
            f"{person.recent:,} commits in the last twelve months" if person.recent
            else f"inactive since {person.last}")

        add("testing", person.test_ratio / max_tests,
            f"{person.test_ratio * 100:.2f}% of changed paths were tests")

        add("docs", person.doc_touches / max_docs, f"{person.doc_touches:,} documentation touches")

        scores[id(person)] = Score(round(sum(p.points for p in parts), 1), parts)
    return scores


def _kind_share(person: Person) -> float:
    """Fraction of commits in the person's dominant repository kind; 1.0 when unknown."""
    if not person.by_kind:
        return 1.0
    return max(person.by_kind.values()) / (sum(person.by_kind.values()) or 1)


def _days_between(a: str, b: str) -> int:
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except ValueError:
        return 0


def rank(people: list[Person]) -> list[tuple[Person, Score]]:
    scores = score_team(people)
    pairs = [(person, scores[id(person)]) for person in people]
    pairs.sort(key=lambda pair: pair[1].total, reverse=True)
    return pairs
