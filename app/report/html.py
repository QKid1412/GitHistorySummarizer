"""Renders a Portfolio as a self-contained HTML page.

The page carries every figure the analysis produced. Narrative sections are left
as clearly marked drafting prompts: nothing here invents prose about work it has
only seen the commit subjects for.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape

from app.analysis.portfolio import Portfolio, Proportion
from app.gitlog.collect import CLIENT, RELEASE, classify_branch
from app.gitlog.models import BACKEND, FRONTEND
from app.report.styles import CSS, FONT_LINK

_KIND_LABEL = {BACKEND: "Backend", FRONTEND: "Frontend", "unknown": "Other"}


DETAILED = "detailed"
SHAREABLE = "shareable"


def render(
    portfolio: Portfolio,
    title: str,
    subtitle: str | None = None,
    generated: date | None = None,
    mode: str = DETAILED,
    streams: list | None = None,
    guide=None,
    ai_used: bool = False,
    author_name: str | None = None,
) -> str:
    """Renders one of two versions.

    `detailed` keeps every real name and is for the author's eyes only.
    `shareable` carries the same figures with identifiers replaced, plus a guide
    to writing the parts a commit log cannot supply.
    """
    stamp = generated or date.today()
    parts = [
        f"<title>{escape(title)}</title>",
        FONT_LINK,
        f"<style>{CSS}</style>",
        '<div class="wrap">',
        _masthead(portfolio, title, subtitle, mode, author_name),
        _stats(portfolio),
        _guide_intro(guide) if mode == SHAREABLE else "",
        _proportions(portfolio),
        _years(portfolio),
        _branches(portfolio, mode),
        _themes(portfolio, mode),
        _streams(streams) if streams else _drafting(portfolio),
        _guide_prompts(guide) if guide else "",
        _guide_bullets(guide) if guide else "",
        _guide_checks(guide) if guide else "",
        _method(portfolio, mode, ai_used),
        f'<footer>Compiled from local git history &middot; {stamp.isoformat()}</footer>',
        "</div>",
    ]
    return "\n".join(p for p in parts if p)


# ----- sections -----------------------------------------------------


def _masthead(p: Portfolio, title: str, subtitle: str | None, mode: str = DETAILED,
              author_name: str | None = None) -> str:
    span = ""
    if p.first and p.last:
        span = f"{p.first.strftime('%b %Y')} &ndash; {p.last.strftime('%b %Y')}"
    repos = " &middot; ".join(
        f"{escape(r.label)} &middot; <strong>{_KIND_LABEL.get(r.kind, r.kind).lower()}</strong>" for r in p.repos
    )
    lede = escape(subtitle) if subtitle else (
        f"Contribution record across {len(p.repos)} "
        f"{'repository' if len(p.repos) == 1 else 'repositories'}, compiled from local git history."
    )
    eyebrow = "Shareable draft" if mode == SHAREABLE else "Contribution record"
    who = f"<span><strong>{escape(author_name)}</strong></span>" if author_name else ""
    return f"""
  <header class="masthead">
    <p class="eyebrow">{eyebrow}{f' &middot; {span}' if span else ''}</p>
    <h1>{escape(title)}</h1>
    <p class="standfirst">{lede}</p>
    <p class="byline">{who}<span>{repos}</span>{f'<span>{span}</span>' if span else ''}</p>
  </header>"""


def _stats(p: Portfolio) -> str:
    cells = [
        (_num(p.commits), "Commits authored"),
        (_num(p.pull_requests), "Pull requests"),
        (_num(p.distinct_files), "Distinct files"),
        (_compact(p.insertions), "Lines added"),
        (_compact(p.deletions), "Lines removed"),
    ]
    if p.offtrunk_commits:
        cells.insert(1, (_num(p.offtrunk_commits), "Off-trunk commits"))
    if p.release_cuts:
        cells.append((_num(p.release_cuts), "Releases cut"))
    if p.span_years >= 1:
        cells.append((f"{p.span_years:.0f}", "Years"))
    body = "".join(f'<div class="stat"><b>{v}</b><span>{escape(l)}</span></div>' for v, l in cells)
    return f'<div class="stats">{body}</div>'


def _proportions(p: Portfolio) -> str:
    kinds = p.kinds
    if len(kinds) < 2:
        return ""
    rows = "".join(_split_row(prop.label, prop, kinds) for prop in p.proportions if prop.total)
    key = "".join(
        f'<span><i class="dot" style="background:{c}"></i> {_KIND_LABEL.get(k, k)}</span>'
        for k, c in zip(kinds, ("var(--accent)", "var(--accent-soft);border:1px solid var(--accent)"))
    )
    return f"""
  <section>
    <h2>How the work splits</h2>
    <p class="lede">Commit counts and line counts disagree, and the gap is informative &mdash;
      compare the two before quoting either.</p>
    <div class="split">{rows}</div>
    <div class="split-key">{key}</div>
  </section>"""


def _split_row(label: str, prop: Proportion, kinds: list[str]) -> str:
    segs = []
    for index, kind in enumerate(kinds):
        share = prop.share(kind) * 100
        if share <= 0:
            continue
        text = f"{share:.0f}%" if share >= 8 else ""
        segs.append(f'<div class="seg seg-{"a" if index == 0 else "b"}" style="width:{share:.1f}%">{text}</div>')
    return (
        f'<div class="split-row"><span class="split-label">{escape(label)}</span>'
        f'<div class="split-bar">{"".join(segs)}</div></div>'
    )


def _years(p: Portfolio) -> str:
    if not p.years:
        return ""
    peak = max(y.total for y in p.years) or 1
    kinds = p.kinds

    rows = []
    for slice_ in p.years:
        width = slice_.total / peak * 100
        detail = ""
        if len(kinds) > 1:
            detail = " &middot; " + ", ".join(
                f"{_KIND_LABEL.get(k, k)} {slice_.share(k) * 100:.0f}%" for k in kinds if slice_.by_kind.get(k)
            )
        rows.append(f"""
        <div class="yr">
          <div class="yr-num">{slice_.year}</div>
          <div class="yr-body">
            <div class="bar"><i class="bar-track" style="width:{width:.0f}%"></i><span>{slice_.total}{detail}</span></div>
          </div>
        </div>""")

    return f"""
  <section>
    <h2>Year by year</h2>
    <p class="lede">Bar length is relative to the busiest year.</p>
    <div class="scroller"><div class="timeline">{"".join(rows)}</div></div>
  </section>"""


def _branches(p: Portfolio, mode: str = DETAILED) -> str:
    rows = [b for b in p.branches if b.mine > 0]
    if not rows:
        return ""
    body = []
    for branch in rows[:24]:
        share = branch.share * 100
        css = "share high" if share >= 25 else "share"
        span = ""
        if branch.first and branch.last:
            span = branch.first.strftime("%Y") if branch.first.year == branch.last.year else \
                f"{branch.first.strftime('%Y')}&ndash;{branch.last.strftime('%y')}"
        body.append(
            f"<tr><td class='br'>{escape(_short(branch.name))}</td>"
            f"<td class='num'>{branch.mine}</td>"
            f"<td class='num'>{branch.total}</td>"
            f"<td class='num {css}'>{share:.0f}%</td>"
            f"<td class='num'>{span}</td>"
            f"<td>{escape(_kind_label(branch))}</td></tr>"
        )
    more = ""
    if len(rows) > 24:
        more = f"<p style='font-family:var(--f-mono);font-size:0.68rem;color:var(--ink-faint);margin-top:0.9rem'>{len(rows) - 24} further branches omitted.</p>"

    return f"""
  <section>
    <h2>Branch ownership</h2>
    <p class="lede">Work that never reached trunk. Your share of each branch is the clearest
      available signal of how much of it you carried.</p>
    <div class="scroller">
      <table>
        <thead><tr><th>Branch</th><th>Yours</th><th>Branch total</th><th>Share</th><th>Span</th><th>Type</th></tr></thead>
        <tbody>{"".join(body)}</tbody>
      </table>
    </div>
    {more}
    <p style="font-family:var(--f-mono);font-size:0.68rem;color:var(--ink-faint);margin-top:0.9rem;letter-spacing:0.04em">
      Counted against trunk. A commit on several branches is attributed to one of them, so rows may
      overlap; the off-trunk total in the summary is de-duplicated.</p>
  </section>"""


def _themes(p: Portfolio, mode: str = DETAILED) -> str:
    if not (p.modules or p.tickets):
        return ""
    modules = "".join(f'<span class="chip"><b>{escape(m)}</b> {n}</span>' for m, n in p.modules[:18])
    tickets = "".join(f'<span class="chip"><b>{escape(t)}</b> {n}</span>' for t, n in p.tickets[:12])
    blocks = []
    if modules:
        blocks.append(f'<h3 style="margin-top:2rem">Most-touched areas</h3><div class="chips">{modules}</div>')
    if tickets:
        blocks.append(f'<h3 style="margin-top:2.5rem">Project prefixes</h3><div class="chips">{tickets}</div>')
    lede = (
        "Areas ranked by how often your commits touched them. The names are placeholders; "
        "the counts are real."
        if mode == SHAREABLE else
        "Directories and ticket prefixes ranked by how often your commits touched them. "
        "A reasonable starting point for naming your work streams."
    )
    return f"""
  <section>
    <h2>Where the work landed</h2>
    <p class="lede">{lede}</p>
    {"".join(blocks)}
  </section>"""


def _drafting(p: Portfolio) -> str:
    """The narrative scaffold. Deliberately empty of generated prose."""
    hints = "".join(
        f"<li><strong>{escape(m)}</strong> &mdash; {n} touches. What did you build here, and what was hard about it?</li>"
        for m, n in p.modules[:6]
    )
    return f"""
  <section>
    <h2>Work streams</h2>
    <div class="draft">
      <h3>Write this part yourself</h3>
      <p>This tool reads commit metadata, not code. It can tell you <em>where</em> you worked and
        <em>how much</em>, but it cannot say what a subsystem does or why a decision was hard &mdash;
        and inventing that is how a portfolio becomes indefensible in an interview.</p>
      <p>The areas below are your highest-volume directories. For each one worth including, write two
        or three sentences: what the subsystem does, what you specifically built, and the constraint
        that made it non-trivial.</p>
      <ul>{hints}</ul>
    </div>
  </section>"""


def _streams(streams: list) -> str:
    """Model-drafted work streams. Rendered with the same structure as the rest."""
    rows = []
    for stream in streams:
        rows.append(f"""
      <article class="stream">
        <div class="stream-meta">
          <span class="era">{escape(str(stream.era))}</span>
          <span class="where">{escape(str(stream.area))}</span>
        </div>
        <div class="stream-body">
          <h3>{escape(str(stream.title))}</h3>
          <p>{escape(str(stream.summary))}</p>
        </div>
      </article>""")
    return f"""
  <section>
    <h2>Work streams</h2>
    <p class="lede">Drafted from your commit subjects. Read every line before you use it &mdash;
      a model working from commit messages can be plausible and wrong, and you are the one who
      has to defend this in an interview.</p>
    <div class="streams">{"".join(rows)}</div>
  </section>"""


def _guide_intro(guide) -> str:
    if not guide:
        return ""
    items = "".join(f"<li><p>{escape(text)}</p></li>" for text in guide.placeholders)
    return f"""
  <section>
    <h2>How to use this draft</h2>
    <p class="lede">{escape(guide.intro)}</p>
    <ul class="checks">{items}</ul>
  </section>"""


def _guide_prompts(guide) -> str:
    if not guide or not guide.prompts:
        return ""
    rows = []
    for prompt in guide.prompts:
        evidence = f'<span class="ev">{escape(prompt.evidence)}</span>' if prompt.evidence else ""
        rows.append(
            f"<li><h4>{escape(prompt.heading)}</h4><p>{escape(prompt.ask)}</p>{evidence}</li>"
        )
    return f"""
  <section>
    <h2>Write these parts yourself</h2>
    <p class="lede">Each prompt is anchored to something measured in your history. Answer them in
      order and you will have the report; skip them and you will have a table of counts.</p>
    <ul class="prompts">{"".join(rows)}</ul>
  </section>"""


def _guide_bullets(guide) -> str:
    if not guide or not guide.bullets:
        return ""
    rows = "".join(f"<li>{_slots(text)}</li>" for text in guide.bullets)
    return f"""
  <section>
    <h2>CV bullets, half-written</h2>
    <p class="lede">The numbers are measured and correct. The bracketed slots are yours to fill.
      Delete any bullet whose claim you would not want examined.</p>
    <ul class="bullets">{rows}</ul>
  </section>"""


def _guide_checks(guide) -> str:
    if not guide or not guide.checks:
        return ""
    rows = "".join(f'<li><span class="box"></span><p>{escape(text)}</p></li>' for text in guide.checks)
    return f"""
  <section>
    <h2>Before you publish</h2>
    <p class="lede">Redaction is mechanical; judgement is not. Work through these once you have
      replaced the placeholders.</p>
    <ul class="checks">{rows}</ul>
  </section>"""


def _slots(text: str) -> str:
    """Escapes text, then marks up [bracketed slots] so they are visibly unfinished."""
    escaped = escape(text)
    return re.sub(r"\[([^\]]+)\]", r'<span class="slot">[\1]</span>', escaped)


def _method(p: Portfolio, mode: str = DETAILED, ai_used: bool = False) -> str:
    ranks = "".join(
        f"<p><span class='mono'>{escape(label)}</span>: ranked {rank} of {total} trunk contributors.</p>"
        for label, rank, total in p.ranks() if rank
    )
    mine, team = p.test_ratio()
    tests = ""
    if p.total_touches_available():
        comparison = f" Team-wide the same figure is {team * 100:.1f}%." if team else ""
        tests = (
            f"<p>Test-path touches account for {mine * 100:.1f}% of your changed paths.{comparison} "
            "Path names only &mdash; this measures whether test files were edited, not coverage.</p>"
        )
    subjects = ", ".join(f"<span class='mono'>{escape(s)}</span>" for s in p.subject)

    if mode == SHAREABLE:
        note = """
      <h3>Still your responsibility to check</h3>
      <p>Identifiers have been replaced with placeholders, but redaction is mechanical. It cannot
        know that a subsystem was named after a customer, or that your industry has few enough
        players that the domain alone identifies your employer. Read the page as a competitor
        would before publishing it.</p>"""
    else:
        note = """
      <h3>This version is not shareable</h3>
      <p>Repository names, branch names, ticket prefixes and directory paths are reproduced verbatim
        and may all be employer-internal. Keep this copy local. Use the shareable version for
        anything that leaves your machine.</p>"""

    if ai_used:
        provenance = (
            "<p>Figures were read from local git repositories. Nothing was uploaded except as follows: "
            "directory names, branch names and commit subjects were sent to a language model to draft "
            "the prose sections. No file contents or diffs were sent.</p>"
        )
    else:
        provenance = (
            "<p>Read from local git repositories only. Nothing was uploaded, no remote was contacted, "
            "and no language model saw any code or commit content.</p>"
        )

    return f"""
  <section>
    <h2>Method</h2>
    <div class="note">{note}
    </div>
    <details open>
      <summary>How this was compiled</summary>
      <div class="details-body">
        {provenance}
        <p>Commits are non-merge commits whose author matches {subjects}, de-duplicated by hash across
          trunk and every other branch.</p>
        {ranks}
        {tests}
        <p>Line and file counts come from <span class="mono">git log --numstat</span> and exclude merge
          commits, so refactors that moved code register as both additions and deletions.</p>
      </div>
    </details>
  </section>"""


# ----- helpers ------------------------------------------------------


def _short(name: str) -> str:
    return name[len("origin/"):] if name.startswith("origin/") else name


def _kind_label(branch) -> str:
    kind = getattr(branch, "kind", "") or classify_branch(branch.name)
    return {RELEASE: "Release line", CLIENT: "Client deployment"}.get(kind, "Feature or shared branch")


def _num(value: int) -> str:
    return f"{value:,}"


def _compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 10_000:
        return f"{value / 1000:.0f}k"
    return f"{value:,}"
