# Git Contribution Analyzer

A local CLI and UI that read your `.git` folders and turn years of commit history into a portfolio report — as an HTML page, a Markdown draft and a JSON dataset.

It works across **multiple repositories at once**, which is the point: if your work is split across a backend and a frontend, neither repository tells the whole story on its own.

```text
local .git folders -> identity matching -> trunk + branch analysis -> detailed and shareable reports
```

## What it does and does not do

It reads commit **metadata**: authors, dates, subjects, changed paths, insertions and deletions, and which branches commits live on. From that it derives totals, backend/frontend proportions, a year-by-year trajectory, per-branch ownership shares, contributor ranking, release cadence and your most-touched directories.

It does **not** read your code. By default it does not use a language model either, so it cannot tell you what a subsystem does or why a decision was hard — those sections are left as drafting prompts. That is deliberate: an AI-written claim about work it never saw is exactly what collapses under one follow-up question in an interview. You can turn model assistance on (see below) if you would rather start from a draft than a blank page.

## Privacy

By default nothing leaves your machine. No network calls, no API keys, no telemetry. `git` is invoked read-only; no command mutates a repository. The UI binds to `127.0.0.1` only and requires a per-run token on every request.

Turning on AI drafting changes that, and the UI says so before you enable it: directory names, branch names and commit subjects are sent to your chosen provider. File contents and diffs are never sent. If those names are employer-confidential, check your policy first. The key is used for that run and never written to disk.

The **output** needs care regardless. That is what the shareable version is for.

## Setup

Requires Python 3.11 or later and `git` on your PATH.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

No `.env` and no credentials are needed.

## Usage

### The UI

```bash
python -m app.ui
```

Opens a page at `http://127.0.0.1:8765`. Add your repository folders, enter your name and email addresses — or click **Detect identities** to list every author found in the repositories — pick which versions you want, choose where to save, and generate.

Your name becomes the byline on both reports. Emails you type are matched in addition to anything you tick, so you can run it without detecting first.

### The command line

Same output, scriptable. Find your identities first — most people have committed under more than one name or email, and missing one silently undercounts your work:

```bash
python -m app.main authors --repo D:/code/backend --repo D:/code/frontend
```

Then analyze, passing every identity that is yours:

```bash
python -m app.main analyze --repo D:/code/backend --repo D:/code/frontend --author you@work.com --author you@personal.co
```

## Two versions

Each run writes a timestamped folder; nothing is ever overwritten.

```text
output/2026-08-27_182517/
├── detailed/           real names — keep this local
│   ├── report.html
│   ├── report.md
│   └── report.json
├── shareable/          identifiers replaced, plus a drafting guide
│   ├── report.html
│   ├── report.md
│   └── report.json
└── redaction-key.txt   maps placeholders back to real names — never share
```

**Detailed** reproduces branch names, ticket prefixes and directory paths verbatim. It is the version you work from, and it is not safe to publish.

**Shareable** carries exactly the same figures — counts, proportions, branch shares, year totals, none of which are sensitive — with every identifier replaced by a stable placeholder: `Client deployment A`, `Release line B`, `PROJ-C`. Placeholders are consistent across the page, so the branch named in the table is the same one referred to anywhere else.

It also carries a guide, which is the part worth reading: prompts anchored to your own measured evidence ("you wrote 20 of 22 commits on this branch — what was it for, and what would have gone wrong if it had been handled badly?"), and CV bullets with the real numbers already filled in and the claims left as blanks.

The two versions never share free text. The shareable one will not inherit your detailed title or standfirst, because a subtitle you wrote for yourself may name the product, and redaction cannot catch a name that never appeared in the git history.

`redaction-key.txt` holds both halves of the mapping. It is written outside the shareable folder on purpose. Delete it, or keep it somewhere the report is not stored.

### AI drafting

Optional, off by default, available in the UI and the CLI:

```bash
python -m app.main analyze --repo D:/code/backend --author you@work.com --api-key sk-...
```

It does two jobs. **Prose** drafts the work-stream sections from your commit subjects. **Redaction**
replaces the lettered placeholders with wording that keeps the professional signal — "a national logistics
operator" rather than "Client deployment A".

Any OpenAI-compatible endpoint works, including a local one. Point `--base-url` at
`http://localhost:11434/v1` and nothing leaves your machine.

#### A different provider per job

The two jobs have different needs. Redaction is short, structured, and sees the most sensitive
names, so it suits a cheap or locally hosted model. Prose drafting is where a stronger model earns
its cost. Blank fields inherit the shared `--api-key`, `--model` and `--base-url`:

```bash
python -m app.main analyze --repo ./api --author you@work.com --api-key sk-shared --prose-model gpt-4o --redact-base-url http://localhost:11434/v1 --redact-api-key ollama
```

A per-job key on its own is enough; the shared one is a convenience. If only one job has a key, the
other falls back to its offline behaviour and says so.

In the UI each job has a **"Use a different provider for this job"** toggle revealing its own key,
model and endpoint.

#### Your own instructions

Both prompts accept extra instructions, appended to the built-in one:

```bash
python -m app.main analyze --repo ./api --author you@work.com --api-key sk-... --prose-instructions "Write in first person. Two sentences per stream." --redact-instructions-file ./my-redaction-style.txt
```

The UI has a textarea per job, with the built-in prompt shown read-only underneath so you can see
exactly what you are adding to.

**The built-in rules are not editable, by design.** They are the guardrails: the prose prompt forbids
inventing metrics — no percentages or latencies unless they appear verbatim in your commit subjects
— and the redaction prompt is what stops the customer being named. Your text is appended *below*
those rules and framed as adjusting tone, emphasis, length and structure, with an explicit statement
that where the two conflict the rules win. An instruction saying "ignore all previous rules" does
not remove them. Instructions are capped at 2,000 characters.

Output shape is fixed by a JSON schema, so instructions change wording and emphasis, not structure.

Read the drafted prose before using it. A model working from commit subjects can be plausible and
wrong, and you are the one who has to defend it.

### Options

| Flag | Purpose |
|---|---|
| `--repo PATH` | A repository or its `.git` directory. Repeat for each one. **Required.** |
| `--author PATTERN` | An email or name fragment that is you. Repeat for each identity. **Required.** |
| `--version V` | `detailed`, `shareable`, `team`, `both` (default) or `all`. Repeatable. |
| `--top N` | Contributors to profile in the team report (default 8). |
| `--team-title` | Title for the team report. |
| `--api-key KEY` | Turn on AI drafting. Omit to stay fully offline. |
| `--model` / `--base-url` | Shared provider settings, used only with `--api-key`. |
| `--prose-*` / `--redact-*` | Per-job `api-key`, `model`, `base-url`, `instructions`, `instructions-file`. Blank fields inherit the shared ones. |
| `--label NAME` | Display name for a repository. Defaults to the directory name. |
| `--kind KIND` | `backend`, `frontend` or `unknown`. Auto-detected from build files. |
| `--trunk REF` | Trunk ref. Auto-detected from `origin/main`, `main`, `master`, `develop`. |
| `--title` / `--subtitle` | Heading and standfirst for the detailed version. |
| `--max-branches N` | Cap on ordinary feature branches measured (default 25). Release and client branches are always measured. |
| `--no-branches` | Skip off-trunk analysis entirely. Roughly twice as fast. |
| `--local-branches` | Use local branches instead of remote-tracking ones. |
| `--output PATH` | Parent directory for reports. Defaults to `output`. |

`--label`, `--kind` and `--trunk` align positionally with `--repo`. Give one value to apply it to every repository, or one per repository:

```bash
python -m app.main analyze --repo ./api --repo ./web --label API --label Web --kind backend --kind frontend --author you@work.com
```

## How branches are handled

Long-lived branches are where per-client and release work hides, and a trunk-only reading misses it. For every branch, the tool counts the commits **not reachable from trunk** and reports your share of them.

Branches are classified by name into three groups:

- **Release lines** — `RELEASE`, `release/2026-08`, `QE_Releases/Release_1.9`
- **Client deployments** — `Client/Northwind`, `Client/Contoso`
- **Everything else** — feature and topic branches

Release and client branches are always measured, because there are usually few of them and they carry the work that never merges. Ordinary feature branches are capped by `--max-branches`, since a repository can hold hundreds and each costs one `git log`.

Two things to know when reading the branch table:

- **Rows can overlap.** Branches that share ancestry contain the same commits, so a commit may be counted against several rows. Your share of each branch is still correct. The off-trunk total in the summary is de-duplicated by commit hash.
- **A high share on a small branch is not the same as a high share on a large one.** `23 of 26` on a release line during a go-live means something; `17 of 17` on a snapshot branch usually does not. Branches with fewer than three of your commits are dropped as noise.

## Reading the numbers honestly

**Commit counts and line counts disagree, and the gap is the interesting part.** SQL migrations and generated config land as very large single commits, so a backend can be a minority of commits and a majority of lines. The report shows both; quote both.

**Line counts include moved code.** A refactor registers as additions and deletions. Large deletion figures usually mean cleanup, not lost work.

**Pull request counts come from squash-merge subjects** — the `(#123)` a merge leaves behind. Work merged another way, or before a migration to GitHub, is in the commit totals but not the PR count.

**Contributor ranking merges your identities into one row** but leaves everyone else as-is, so a colleague who committed under several emails may be split across rows and ranked lower than they should be. Treat rank as approximate.

**The test ratio counts path names, not coverage.** It tells you whether test files were edited, nothing more. Compare it against the team-wide figure the report also prints before drawing a conclusion.

**Redaction is mechanical.** It replaces the names it knows about. It cannot know that a subsystem was named after a customer, or that your industry has few enough players that the domain alone identifies your employer. Read the shareable version as a competitor would before publishing it.

## Tests

```bash
pytest
```

The suite builds real repositories in temporary directories, so the subprocess layer, the log parsing and the branch selection are all exercised for real. It covers author matching, rename notation in `--numstat`, malformed log records, trunk detection, branch classification, the branch-selection caps, placeholder stability, and — checked against the rendered bytes in every output format — that no internal name survives into the shareable version.

## Project layout

```text
app/gitlog/     git subprocess wrapper, log parsing, branch attribution
app/analysis/   portfolio aggregation (proportions, years, branches, themes)
app/report/     redaction, drafting guide, optional AI narrative, renderers
app/ui/         loopback-only web UI
tests/          unit tests plus real temporary repositories
```

`app/github/` and the LLM-facing modules in `app/analysis/` are from the earlier GitHub-API version of this tool and are no longer on any code path. `app/llm/` is still used, by the optional AI drafting above.
