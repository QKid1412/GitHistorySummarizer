"""Renders the team report: who contributes, and what the record says about seniority.

Every ranking statement is backed by the scoring component that produced it, so a
reader can argue with a weight instead of with a verdict.
"""

from __future__ import annotations

from datetime import date
from html import escape

from app.analysis.team import LIMITS, WEIGHTS, Component, Person, Score
from app.report.styles import CSS, FONT_LINK

TIERS = [
    (0.72, "Principal", "Codebase-wide authority: their decisions constrain everyone else's work."),
    (0.55, "Staff", "Ownership beyond their own output — a release line, a platform, a programme."),
    (0.38, "Senior", "Deep ownership of a domain, delivered independently."),
    (0.00, "Contributor", "Substantial delivery within a defined area."),
]

EXTRA_CSS = """
  .warn { margin-top:2rem; border:1px solid var(--flag); border-left-width:3px; background:var(--flag-soft);
          padding:1.3rem 1.5rem; display:flex; flex-direction:column; gap:0.6rem; }
  .warn h3 { color:var(--ink); font-size:1.05rem; }
  .warn p { margin:0; font-size:0.93rem; color:var(--ink-soft); line-height:1.62; }

  .people { margin-top:2rem; display:flex; flex-direction:column; gap:1.25rem; }
  .person { background:var(--surface); border:1px solid var(--rule); padding:1.8rem 1.7rem; }
  .phead { display:flex; flex-wrap:wrap; gap:0.55rem 1rem; align-items:baseline; }
  .phead .no { font-family:var(--f-mono); font-size:1.45rem; font-weight:600; color:var(--accent);
               font-variant-numeric:tabular-nums; }
  .phead .n { font-family:var(--f-display); font-size:1.45rem; font-weight:600; letter-spacing:-0.015em; }
  .phead .sc { margin-left:auto; font-family:var(--f-mono); font-size:0.8rem; color:var(--ink-faint);
               font-variant-numeric:tabular-nums; }
  .tag { font-family:var(--f-mono); font-size:0.6rem; letter-spacing:0.09em; text-transform:uppercase;
         padding:0.15rem 0.5rem; border-radius:2px; border:1px solid var(--accent); color:var(--accent); }
  .tag.out { border-color:var(--ink-faint); color:var(--ink-faint); }
  .role { font-family:var(--f-mono); font-size:0.66rem; letter-spacing:0.09em; text-transform:uppercase;
          color:var(--ink-faint); }

  .figs { display:grid; grid-template-columns:repeat(auto-fit,minmax(104px,1fr)); gap:1px;
          background:var(--rule); border:1px solid var(--rule); margin:1.15rem 0; }
  .fig { background:var(--surface-2); padding:0.7rem 0.8rem; display:flex; flex-direction:column; gap:0.18rem; }
  .fig b { font-family:var(--f-mono); font-variant-numeric:tabular-nums; font-size:1.1rem; font-weight:600;
           line-height:1; color:var(--ink); }
  .fig span { font-family:var(--f-mono); font-size:0.58rem; letter-spacing:0.08em; text-transform:uppercase;
              color:var(--ink-faint); line-height:1.35; }

  .block { margin-top:1.15rem; }
  .block h4 { margin:0 0 0.45rem; font-family:var(--f-mono); font-size:0.63rem; letter-spacing:0.11em;
              text-transform:uppercase; color:var(--accent); font-weight:500; }
  .block.gap h4 { color:var(--flag); }
  .block p { font-size:0.94rem; color:var(--ink-soft); line-height:1.62; margin:0 0 0.6rem; }
  .block p:last-child { margin-bottom:0; }
  .block strong { color:var(--ink); font-weight:600; }

  .bars { display:flex; flex-direction:column; gap:1px; background:var(--rule); border:1px solid var(--rule); }
  .bar-row { background:var(--surface); display:grid; grid-template-columns:8.5rem 5.5rem 1fr;
             gap:0 0.85rem; align-items:center; padding:0.42rem 0.8rem; }
  .bar-row .k { font-family:var(--f-mono); font-size:0.7rem; letter-spacing:0.05em; text-transform:uppercase;
                color:var(--ink-faint); }
  .bar-row .t { display:flex; height:9px; background:var(--surface-2); border-radius:2px; overflow:hidden; }
  .bar-row .t i { background:var(--accent); display:block; }
  .bar-row .t i.low { background:var(--rule); }
  .bar-row .e { font-size:0.78rem; color:var(--ink-soft); overflow:hidden; text-overflow:ellipsis; }
  .bar-row .pts { font-family:var(--f-mono); font-size:0.68rem; color:var(--ink-faint);
                  font-variant-numeric:tabular-nums; }
  @media (max-width:680px) { .bar-row { grid-template-columns:1fr; gap:0.25rem; } }

  ul.plain { margin:0; padding:0; list-style:none; display:flex; flex-direction:column; gap:1px;
             background:var(--rule); border:1px solid var(--rule); }
  ul.plain li { background:var(--surface); padding:1rem 1.2rem; font-size:0.93rem; line-height:1.6;
                color:var(--ink-soft); }
  ul.plain strong { color:var(--ink); font-weight:600; }
  ul.plain .ev { display:block; margin-top:0.3rem; font-family:var(--f-mono); font-size:0.72rem;
                 color:var(--ink-faint); }
  .gone { color:var(--ink-faint); font-style:italic; }
  .rank { font-family:var(--f-mono); font-weight:600; color:var(--accent); }
"""


def render(pairs: list[tuple[Person, Score]], title: str, repos: list[str],
           generated: date | None = None) -> str:
    stamp = generated or date.today()
    maximum = sum(w[0] for w in WEIGHTS.values())
    parts = [
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(title)}</title>", FONT_LINK,
        f"<style>{CSS}{EXTRA_CSS}</style>", "</head>", "<body>", '<div class="wrap">',
        _masthead(pairs, title, repos, stamp),
        _caveat(),
        _table(pairs, maximum),
        _people(pairs, maximum),
        _observations(pairs),
        _method(maximum, pairs),
        f'<footer>Compiled from local git history &middot; {stamp.isoformat()} &middot; internal use</footer>',
        "</div>", "</body>", "</html>",
    ]
    return "\n".join(parts)


# ----- sections -----------------------------------------------------


def _masthead(pairs, title: str, repos: list[str], stamp: date) -> str:
    total = sum(p.commits for p, _ in pairs)
    span = f"{min(p.first for p, _ in pairs)} to {max(p.last for p, _ in pairs)}" if pairs else ""
    return f"""
  <header class="masthead">
    <p class="eyebrow">Internal &middot; {escape(', '.join(repos))} &middot; {stamp.isoformat()}</p>
    <h1>{escape(title)}</h1>
    <p class="standfirst">The {len(pairs)} highest-volume contributors, what each one works on, and
      what the commit record does &mdash; and does not &mdash; say about their seniority.
      {total:,} commits across {span}.</p>
  </header>"""


def _caveat() -> str:
    return """
  <div class="warn">
    <h3>Read this before the rest</h3>
    <p>This analyses <strong>commit metadata</strong>, not people. Git records who typed what and
      when. It cannot see the review that stopped a bad design, the afternoon spent unblocking a
      colleague, the incident handled at 2am, or the hard problem solved in three lines.</p>
    <p>The ranking comes from thirteen weighted signals, each shown with its evidence, so you can
      disagree with a weight rather than with a verdict. Several people rank below their commit
      volume and at least one ranks well above it, because volume is among the weaker signals here.</p>
    <p><strong>Do not use this for a performance conversation.</strong> It maps how the codebase is
      divided and where authority sits. It is not a measure of anyone's worth.</p>
  </div>"""


def _table(pairs, maximum: float) -> str:
    rows = []
    for index, (person, score) in enumerate(pairs, 1):
        tier, _ = tier_of(score, maximum)
        gone = "" if person.active else f' <span class="gone">&mdash; last {person.last}</span>'
        rows.append(
            f"<tr><td class='rank'>{index}</td>"
            f"<td><strong>{escape(person.display)}</strong>{gone}</td>"
            f"<td>{escape(tier)}</td><td>{escape(role_of(person, score))}</td>"
            f"<td class='num'>{score.total:.0f}</td>"
            f"<td class='num'>{person.commits:,}</td>"
            f"<td class='num'>{person.years:.1f}y</td>"
            f"<td class='num'>{person.merges_to_trunk:,}</td>"
            f"<td class='num'>{person.version_cuts}</td>"
            f"<td class='num'>{person.test_ratio * 100:.2f}%</td></tr>"
        )
    tie = ""
    if len(pairs) >= 2:
        gap = pairs[0][1].total - pairs[1][1].total
        # Wide enough to catch pairs whose order flips on a single methodology
        # choice, which is exactly the case a reader must not over-read.
        if gap / maximum < 0.08:
            tie = (f" <strong>{escape(pairs[0][0].display)} and {escape(pairs[1][0].display)} are "
                   f"effectively tied</strong> &mdash; {gap:.1f} points apart out of {maximum:.0f}, "
                   "on different axes. Read the top two as a pair rather than as first and second.")

    return f"""
  <section>
    <h2>The ordering</h2>
    <p class="lede">Ranked by weighted signal, not by commit count. Adjacent positions are usually
      within noise of each other; the tier boundaries are the meaningful divisions.{tie}</p>
    <div class="scroller">
      <table>
        <thead><tr><th>#</th><th>Name</th><th>Tier</th><th>Read</th><th>Score</th><th>Commits</th>
          <th>Tenure</th><th>Merges&rarr;trunk</th><th>Releases</th><th>Tests</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    <p style="font-family:var(--f-mono);font-size:0.68rem;color:var(--ink-faint);margin-top:0.9rem;letter-spacing:0.04em">
      Score is out of {maximum:.0f}. Identities merged across work, personal and machine-generated addresses.</p>
  </section>"""


def _people(pairs, maximum: float) -> str:
    blocks = []
    for index, (person, score) in enumerate(pairs, 1):
        blocks.append(_person(index, person, score, maximum))
    return f"""
  <section>
    <h2>Each contributor</h2>
    <div class="people">{''.join(blocks)}</div>
  </section>"""


def _person(index: int, person: Person, score: Score, maximum: float) -> str:
    tier, tier_note = tier_of(score, maximum)
    status = f'<span class="tag out">Last commit {person.last}</span>' if not person.active else f'<span class="tag">{escape(tier)}</span>'

    kinds = ", ".join(f"{k} {v:,}" for k, v in sorted(person.by_kind.items(), key=lambda i: -i[1]))
    figs = [
        (f"{person.commits:,}", "Commits"),
        (f"{person.years:.1f}y", "Tenure"),
        (f"{person.per_year:,.0f}", "Commits / year"),
        (f"{person.merges_to_trunk:,}", "Merges to trunk"),
        (f"{person.version_cuts}", "Releases cut"),
        (f"{person.recent:,}", "Last 12 months"),
    ]
    figs_html = "".join(f'<div class="fig"><b>{v}</b><span>{escape(l)}</span></div>' for v, l in figs)

    ordered = sorted(score.components, key=lambda c: (c.points / c.maximum if c.maximum else 0), reverse=True)
    lifts = [c for c in ordered if c.points / c.maximum >= 0.5][:5]
    drags = [c for c in reversed(ordered) if c.points / c.maximum < 0.25][:4]

    return f"""
      <article class="person">
        <div class="phead">
          <span class="no">{index}</span><span class="n">{escape(person.display)}</span>
          {status}
          <span class="role">{escape(role_of(person, score))} &middot; {person.first[:4]}&ndash;{person.last[:4]}</span>
          <span class="sc">{score.total:.0f} / {maximum:.0f}</span>
        </div>
        <div class="figs">{figs_html}</div>

        <div class="block"><h4>What they work on</h4>
          <p>{_works_on(person)}</p>
          <p style="font-size:0.86rem;color:var(--ink-faint)">Split: {escape(kinds)}.</p>
        </div>

        <div class="block"><h4>Why this rank &mdash; what lifts them</h4>
          <p>{_lift_prose(person, lifts, tier)}</p>
        </div>

        {_drag_block(person, drags)}

        <div class="block"><h4>Signal breakdown</h4>
          <div class="bars">{_bars(score)}</div>
        </div>

        <div class="block gap"><h4>What the record cannot say</h4>
          <p>{_blind_spot(person, score)}</p>
        </div>
      </article>"""


def _bars(score: Score) -> str:
    rows = []
    for component in sorted(score.components, key=lambda c: (c.points / c.maximum if c.maximum else 0), reverse=True):
        fraction = component.points / component.maximum if component.maximum else 0
        klass = "" if fraction >= 0.25 else " low"
        rows.append(
            f'<div class="bar-row"><span class="k">{escape(component.key)}</span>'
            f'<span class="t"><i class="{klass.strip()}" style="width:{fraction * 100:.0f}%"></i></span>'
            f'<span class="e">{escape(component.evidence)} '
            f'<span class="pts">&middot; {component.points:.0f}/{component.maximum:.0f}</span></span></div>'
        )
    return "".join(rows)


def _drag_block(person: Person, drags: list[Component]) -> str:
    if not drags:
        return ""
    items = "; ".join(f"<strong>{escape(c.key)}</strong> &mdash; {escape(c.evidence)}" for c in drags)
    return f"""
        <div class="block gap"><h4>What holds them back</h4>
          <p>{items}. {_drag_note(person, drags)}</p>
        </div>"""


# ----- narrative helpers --------------------------------------------


def tier_of(score: Score, maximum: float) -> tuple[str, str]:
    fraction = score.total / maximum if maximum else 0
    for threshold, name, note in TIERS:
        if fraction >= threshold:
            return name, note
    return TIERS[-1][1], TIERS[-1][2]


def role_of(person: Person, score: Score) -> str:
    """A short descriptor derived from which signals dominate."""
    def strong(key: str, at: float = 0.6) -> bool:
        component = score.by_key(key)
        return bool(component and component.maximum and component.points / component.maximum >= at)

    if person.codeowner and strong("integration", 0.4):
        return "Codebase owner"
    if strong("integration") and strong("release"):
        return "Delivery and integration"
    if strong("infrastructure") and strong("testing", 0.5):
        return "Platform and build"
    if strong("pioneer", 0.8) and strong("architecture", 0.5) and not strong("release", 0.3):
        return "Founding architect"
    if strong("branch", 0.4) and person.branches:
        client = max(person.branches.items(), key=lambda i: i[1][0])[0]
        return "Client programmes" if "client" in client.lower() else "Release line"
    if strong("depth") and not strong("breadth", 0.5):
        return "Domain specialist"
    if len(person.by_kind) == 1:
        only = next(iter(person.by_kind))
        return f"{only.title()} specialist"
    if strong("infrastructure"):
        return "Platform engineering"
    return "Feature delivery"


def _works_on(person: Person) -> str:
    modules = [m.split(":", 1)[-1] for m, _ in person.modules.most_common(5)]
    vertical = person.vertical_modules()
    text = "Heaviest footprint in " + ", ".join(f"<code>{escape(m)}</code>" for m in modules[:4]) + "."
    if vertical:
        module = vertical[0][0]
        name = module.split(":", 1)[-1]
        layers = person.layers_of(module)
        readable = {"ui": "interface", "service": "service", "model": "model", "schema": "schema"}
        named = ", ".join(readable.get(l, l) for l in layers[:-1]) + f" and {readable.get(layers[-1], layers[-1])}"
        text += (f" Carries <code>{escape(name)}</code> through its {escape(named)} layers, which is "
                 f"vertical ownership of a subsystem rather than work on its surface"
                 f"{f' — one of {len(vertical)} such subsystems' if len(vertical) > 1 else ''}.")
    if person.architecture:
        text += " Introduced " + ", ".join(escape(a) for a in person.architecture[:3]) + "."
    if person.branches:
        top = sorted(person.branches.items(), key=lambda i: -i[1][0])[0]
        text += (f" Largest off-trunk contribution is <code>{escape(top[0])}</code> "
                 f"at {top[1][0]} of {top[1][1]} commits.")
    return text


def _lift_prose(person: Person, lifts: list[Component], tier: str) -> str:
    if not lifts:
        return ("No signal reaches half its available weight. The record shows steady delivery "
                "without the ownership markers that lift a rank.")
    sentences = []
    for component in lifts:
        sentences.append(_explain(component, person))
    joined = " ".join(sentences)
    return f"{joined} Together these place them in the <strong>{escape(tier)}</strong> band."


def _explain(component: Component, person: Person) -> str:
    key, evidence = component.key, escape(component.evidence)
    templates = {
        "authority": f"<strong>They hold declared review authority</strong> &mdash; {evidence} &mdash; "
                     "which is the only formal, written statement of trust a repository usually carries, "
                     "and it outranks any volume measure.",
        "integration": f"<strong>They are an integration point</strong>: {evidence}. Work reaching trunk "
                       "passes through them, which is a maintainer's responsibility rather than a "
                       "contributor's.",
        "release": f"<strong>They own releases</strong> &mdash; {evidence}. Deciding what ships and "
                   "tagging it is a trusted role that is rarely delegated downward.",
        "tenure": f"<strong>They carry institutional memory</strong>: {evidence}. Long tenure in one "
                  "codebase means being the person who remembers why a decision was made.",
        "breadth": f"<strong>They work across the whole system</strong> &mdash; {evidence} &mdash; rather "
                   "than within one area, which is what lets someone reason about change globally.",
        "depth": f"<strong>They own subsystems vertically</strong>: {evidence}. Carrying one area through "
                 "interface, service, schema and model is among the strongest ownership patterns a commit "
                 "log can show.",
        "infrastructure": f"<strong>They own the machinery others depend on</strong> &mdash; {evidence}. "
                          "This is leverage work: it changes how safely everyone else can move.",
        "pioneer": f"<strong>They were here early</strong> &mdash; {evidence} &mdash; so the structural "
                   "decisions they made are the ones later work had to fit around.",
        "branch": f"<strong>They carry a delivery line largely alone</strong>: {evidence}. Handing one "
                  "person a release or client branch is a trust decision visible in the graph.",
        "architecture": f"<strong>They introduce structural dependencies</strong> &mdash; {evidence}. "
                        "Being first to add a piece of architecture means being trusted to choose it.",
        "currency": f"<strong>They are central right now</strong>: {evidence}.",
        "testing": f"<strong>They test</strong> &mdash; {evidence} &mdash; which in a codebase with weak "
                   "coverage norms is a discipline signal rather than a routine one.",
        "docs": f"<strong>They write things down</strong>: {evidence}. Documentation is a force multiplier "
                "that commit counts never reward.",
    }
    return templates.get(key, f"{escape(key)}: {evidence}.")


def _drag_note(person: Person, drags: list[Component]) -> str:
    keys = {c.key for c in drags}
    if "currency" in keys and not person.active:
        return ("Their rank is depressed by absence rather than by the quality of the work; on "
                "demonstrated level they sit higher than this position implies.")
    if "authority" in keys and "integration" in keys:
        return ("Deep ownership within an area, without yet the codebase-wide responsibilities that "
                "mark the tier above.")
    if "testing" in keys and "docs" in keys:
        return ("Delivery-weighted rather than durability-weighted &mdash; worth checking whether that "
                "reflects the individual or the team's norms.")
    return "None of these are disqualifying; they mark where this person's remit stops."


def _blind_spot(person: Person, score: Score) -> str:
    lines = []
    if person.codeowner:
        lines.append("CODEOWNERS shows who must approve, not whether those approvals are timely or good. "
                     "A single default reviewer across large repositories is also a bus-factor risk.")
    if not person.active:
        lines.append(f"They stopped committing in {person.last}, so nothing here reflects current standing.")
    if person.test_ratio < 0.01:
        lines.append("Near-zero test authorship may mean testing happens elsewhere in their workflow, "
                     "or that this area is covered by someone else.")
    vertical = person.vertical_modules()
    if len(vertical) <= 1 and person.commits > 500:
        lines.append("A narrow footprint can mean specialisation or assignment; the record cannot "
                     "distinguish a choice from a rota.")
    lines.append("Review depth, mentoring, design influence and incident response are absent from every "
                 "figure above, and are usually the deciding evidence.")
    return " ".join(lines)


def _observations(pairs) -> str:
    if not pairs:
        return ""
    people = [p for p, _ in pairs]
    owners = [p.display for p in people if p.codeowner]
    departed = [p for p in people if not p.active]
    merges = sorted(people, key=lambda p: -p.merges_to_trunk)[:2]
    merge_share = sum(p.merges_to_trunk for p in merges) / max(sum(p.merges_to_trunk for p in people), 1)
    testers = sorted(people, key=lambda p: -p.test_ratio)[:1]
    solo = [p for p in people if p.vertical_modules()]

    items = []
    if owners:
        items.append(f"<li><strong>Declared authority sits with {escape(', '.join(owners))}.</strong> "
                     "CODEOWNERS is the only written statement of review responsibility in these "
                     "repositories, and it is worth checking whether that concentration is intended."
                     "<span class='ev'>Named as default reviewer</span></li>")
    if len(merges) >= 2 and merges[0].merges_to_trunk:
        items.append(f"<li><strong>Two people absorb most integration.</strong> "
                     f"{escape(merges[0].display)} and {escape(merges[1].display)} account for "
                     f"{merge_share * 100:.0f}% of the merges into trunk among this group."
                     f"<span class='ev'>{merges[0].merges_to_trunk:,} and {merges[1].merges_to_trunk:,} merges</span></li>")
    if departed:
        names = ", ".join(escape(p.display) for p in departed[:3])
        items.append(f"<li><strong>{len(departed)} of this group have stopped committing</strong> "
                     f"&mdash; {names}. Where they held sole ownership of a subsystem, that knowledge "
                     "left with them."
                     f"<span class='ev'>Last commits {', '.join(p.last for p in departed[:3])}</span></li>")
    if testers and testers[0].test_ratio > 0:
        items.append(f"<li><strong>Testing is one person's habit, not a shared practice.</strong> "
                     f"{escape(testers[0].display)} leads at {testers[0].test_ratio * 100:.2f}% of changed "
                     f"paths; the group median is {_median([p.test_ratio for p in people]) * 100:.2f}%. "
                     "That gap is a team norm, not eight individual choices."
                     "<span class='ev'>Test-file share of changed paths</span></li>")
    if solo:
        items.append(f"<li><strong>{len(solo)} subsystems have a single vertical owner.</strong> "
                     "Each is a single point of failure for both delivery and knowledge."
                     "<span class='ev'>Touched across interface, service, schema and model layers</span></li>")
    return f"""
  <section>
    <h2>What this shows about the team</h2>
    <ul class="plain">{''.join(items)}</ul>
  </section>"""


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _method(maximum: float, pairs: list | None = None) -> str:
    weights = "".join(
        f"<div class='bar-row'><span class='k'>{escape(key)}</span>"
        f"<span class='t'><i style='width:{points / maximum * 100 * 6:.0f}%'></i></span>"
        f"<span class='e'>{escape(note)} <span class='pts'>&middot; max {points}</span></span></div>"
        for key, (points, note) in WEIGHTS.items()
    )
    limits = "".join(f"<li>{escape(limit)}</li>" for limit in LIMITS)
    excluded = sum(person.vendored_touches for person, _ in (pairs or []))
    vendored = (f"<p style='font-size:0.9rem;color:var(--ink-soft);margin-top:1rem'>"
                f"{excluded:,} path changes were excluded as checked-in dependencies or build output "
                f"&mdash; node_modules, vendored libraries, bundles and compiled artefacts. Those are "
                f"real commits but not authorship, and counting them distorts both module ranking and "
                f"the vertical-ownership signal.</p>") if excluded else ""
    return f"""
  <section>
    <h2>Method, and where it is blind</h2>
    <p class="lede">The model is published so you can disagree with it precisely.</p>
    <div class="block"><h4>Weights, out of {maximum:.0f}</h4><div class="bars">{weights}</div></div>
    <div class="block"><h4>Excluded from authorship</h4>{vendored}</div>
    <div class="block"><h4>Known limitations</h4></div>
    <ul class="plain">{limits}</ul>
  </section>"""
