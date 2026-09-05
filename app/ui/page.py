"""The UI page. Shares the report's visual system so the tool and its output match."""

from __future__ import annotations

from app.report.styles import FONT_LINK

UI_CSS = """
  :root {
    --ground:#EEF1EE; --surface:#FFFFFF; --surface-2:#F6F9F7;
    --ink:#101F29; --ink-soft:#4E6573; --ink-faint:#7C93A0;
    --accent:#00637F; --accent-soft:#DEECF1;
    --flag:#A83562; --flag-soft:#F4E3EA;
    --rule:#D2DAD8; --rule-soft:#E4EAE7;
    --f-display:"Spectral",Georgia,serif;
    --f-body:"IBM Plex Sans",-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
    --f-mono:"IBM Plex Mono",Consolas,monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground:#060D13; --surface:#0C1720; --surface-2:#111F2A;
      --ink:#C6D6DE; --ink-soft:#7B94A2; --ink-faint:#5A7383;
      --accent:#4CBAD6; --accent-soft:#102C38;
      --flag:#E07BA6; --flag-soft:#2A1622;
      --rule:#1B2C38; --rule-soft:#142330;
    }
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--ground); color:var(--ink);
    font-family:var(--f-body); font-size:15px; line-height:1.6;
    -webkit-font-smoothing:antialiased;
  }
  .wrap { max-width:820px; margin:0 auto; padding:clamp(2rem,5vw,3.5rem) clamp(1.25rem,4vw,2rem) 5rem; }

  h1 {
    font-family:var(--f-display); font-weight:600; font-size:clamp(1.9rem,5vw,2.6rem);
    line-height:1.1; letter-spacing:-0.02em; margin:0 0 0.5rem;
  }
  .sub { color:var(--ink-soft); margin:0 0 2.5rem; max-width:58ch; }
  .eyebrow {
    font-family:var(--f-mono); font-size:0.68rem; letter-spacing:0.16em;
    text-transform:uppercase; color:var(--accent); margin:0 0 0.6rem;
  }

  fieldset {
    border:1px solid var(--rule); background:var(--surface);
    padding:1.4rem 1.5rem; margin:0 0 1.25rem; border-radius:2px;
  }
  legend {
    font-family:var(--f-mono); font-size:0.66rem; letter-spacing:0.12em;
    text-transform:uppercase; color:var(--ink-faint); padding:0 0.5rem;
  }
  .hint { font-size:0.86rem; color:var(--ink-faint); margin:0 0 1rem; }

  label { display:block; font-size:0.9rem; margin-bottom:0.35rem; color:var(--ink-soft); }

  input[type=text], input[type=password], select {
    width:100%; padding:0.55rem 0.7rem; font-family:var(--f-mono); font-size:0.85rem;
    background:var(--surface-2); color:var(--ink);
    border:1px solid var(--rule); border-radius:3px;
  }
  input:focus-visible, select:focus-visible, button:focus-visible {
    outline:2px solid var(--accent); outline-offset:2px;
  }

  .row { display:flex; gap:0.5rem; margin-bottom:0.5rem; align-items:center; }
  .row input { flex:1; }

  button {
    font-family:var(--f-body); font-size:0.86rem; font-weight:500;
    padding:0.5rem 0.9rem; border-radius:3px; cursor:pointer;
    background:var(--surface-2); color:var(--ink-soft); border:1px solid var(--rule);
  }
  button:hover:not(:disabled) { border-color:var(--accent); color:var(--accent); }
  button:disabled { opacity:0.45; cursor:not-allowed; }
  button.primary {
    background:var(--accent); color:var(--surface); border-color:var(--accent);
    font-size:0.95rem; padding:0.7rem 1.6rem;
  }
  :root:not([data-theme="light"]) button.primary { color:#06131A; }
  button.primary:hover:not(:disabled) { opacity:0.9; color:var(--surface); }
  :root:not([data-theme="light"]) button.primary:hover:not(:disabled) { color:#06131A; }
  button.ghost { padding:0.4rem 0.6rem; font-size:0.8rem; }

  .choices { display:flex; flex-direction:column; gap:0.7rem; }
  .choice {
    display:flex; gap:0.7rem; align-items:flex-start; padding:0.85rem 1rem;
    border:1px solid var(--rule); border-radius:3px; cursor:pointer; background:var(--surface-2);
  }
  .choice:hover { border-color:var(--accent); }
  .choice input { margin-top:0.25rem; flex:none; }
  .choice strong { display:block; font-size:0.92rem; font-weight:600; color:var(--ink); }
  .choice span { display:block; font-size:0.84rem; color:var(--ink-faint); margin-top:0.15rem; }

  .ids { display:flex; flex-direction:column; gap:1px; background:var(--rule); border:1px solid var(--rule); max-height:260px; overflow-y:auto; }
  .id {
    display:flex; gap:0.7rem; align-items:center; background:var(--surface);
    padding:0.5rem 0.8rem; font-size:0.85rem; cursor:pointer;
  }
  .id:hover { background:var(--surface-2); }
  .id code { font-family:var(--f-mono); font-size:0.78rem; color:var(--ink-soft); }
  .id .n {
    margin-left:auto; font-family:var(--f-mono); font-size:0.75rem;
    color:var(--ink-faint); font-variant-numeric:tabular-nums;
  }

  .warn {
    border:1px solid var(--flag); border-left-width:3px; background:var(--flag-soft);
    padding:0.9rem 1.1rem; margin-top:1rem; font-size:0.86rem; color:var(--ink-soft);
  }
  .warn strong { color:var(--ink); }

  .status { margin-top:1.25rem; font-size:0.88rem; color:var(--ink-soft); min-height:1.4rem; }
  .status.err { color:var(--flag); }

  .files { margin-top:1.25rem; display:flex; flex-direction:column; gap:1px; background:var(--rule); border:1px solid var(--rule); }
  .file {
    background:var(--surface); padding:0.7rem 1rem; display:flex; gap:0.8rem;
    align-items:center; font-family:var(--f-mono); font-size:0.78rem;
  }
  .file .tag {
    flex:none; font-size:0.62rem; letter-spacing:0.1em; text-transform:uppercase;
    padding:0.15rem 0.45rem; border-radius:2px; border:1px solid var(--rule); color:var(--ink-faint);
  }
  .file .tag.keep { border-color:var(--flag); color:var(--flag); }
  .file .p { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink-soft); }
  .file .go { margin-left:auto; flex:none; }

  .spin { display:inline-block; width:11px; height:11px; border:2px solid var(--rule); border-top-color:var(--accent); border-radius:50%; animation:sp 0.7s linear infinite; vertical-align:-1px; margin-right:0.5rem; }
  @keyframes sp { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spin { animation:none; } }

  textarea {
    width:100%; padding:0.55rem 0.7rem; font-family:var(--f-mono); font-size:0.82rem;
    background:var(--surface-2); color:var(--ink); border:1px solid var(--rule);
    border-radius:3px; resize:vertical; line-height:1.5;
  }
  textarea:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }

  .job { margin-top:1.5rem; padding-top:1.3rem; border-top:1px solid var(--rule); }
  .job h4 {
    margin:0 0 0.25rem; font-family:var(--f-mono); font-size:0.66rem; letter-spacing:0.11em;
    text-transform:uppercase; color:var(--accent); font-weight:500;
  }
  details { margin-top:0.7rem; }
  summary {
    cursor:pointer; font-size:0.82rem; color:var(--ink-faint);
    font-family:var(--f-mono); letter-spacing:0.03em;
  }
  summary:hover { color:var(--accent); }
  pre {
    margin:0.6rem 0 0; padding:0.85rem 1rem; background:var(--surface-2);
    border:1px solid var(--rule); border-radius:3px; font-family:var(--f-mono);
    font-size:0.75rem; line-height:1.55; color:var(--ink-soft);
    white-space:pre-wrap; max-height:260px; overflow-y:auto;
  }
  .split-body { display:none; margin-top:0.8rem; }
  .split-body.on { display:block; }

  .ai-body { margin-top:1rem; display:none; }
  .ai-body.on { display:block; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:0.8rem; }
  @media (max-width:600px) { .grid2 { grid-template-columns:1fr; } }
"""


def render(token: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contribution Report Builder</title>
{FONT_LINK}
<style>{UI_CSS}</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">Local &middot; offline by default</p>
  <h1>Contribution Report Builder</h1>
  <p class="sub">Reads your local git repositories and writes a portfolio report. Nothing leaves this
    machine unless you turn on AI drafting below.</p>

  <fieldset>
    <legend>Repositories</legend>
    <p class="hint">Add each repository folder, or its <code>.git</code> directory. Backend and
      frontend are detected from the build files.</p>
    <div id="repos"></div>
    <div class="row" style="margin-top:0.75rem">
      <button type="button" class="ghost" id="addRepo">Add repository</button>
      <button type="button" class="ghost" id="detect">Detect identities</button>
    </div>
  </fieldset>

  <fieldset>
    <legend>You</legend>
    <div class="grid2">
      <div>
        <label for="authorName">Your name</label>
        <input type="text" id="authorName" placeholder="Jane Okafor">
      </div>
      <div>
        <label for="manual">Your email addresses</label>
        <input type="text" id="manual" placeholder="you@work.com, you@personal.com">
      </div>
    </div>
    <p class="hint" style="margin:0.8rem 0 0">Your name appears as the byline on both versions.
      Emails typed here are matched in addition to anything ticked below, so you can run this
      without detecting first. Separate several with commas.</p>
  </fieldset>

  <fieldset>
    <legend>Detected identities</legend>
    <p class="hint">Most people have committed under more than one email, and some under a machine
      name they never chose. Tick every one that is yours &mdash; missing one silently undercounts
      your work.</p>
    <div class="ids" id="ids"><div class="id" style="color:var(--ink-faint)">Add a repository, then
      click Detect identities.</div></div>
  </fieldset>

  <fieldset>
    <legend>Versions</legend>
    <p class="hint">Pick any combination. Each is written to its own folder.</p>
    <div class="choices">
      <label class="choice">
        <input type="checkbox" class="ver" value="detailed" checked>
        <span><strong>Detailed</strong><span>Your record, with real branch names, ticket prefixes and paths. For your eyes only.</span></span>
      </label>
      <label class="choice">
        <input type="checkbox" class="ver" value="shareable" checked>
        <span><strong>Shareable + guide</strong><span>Your record with identifiers replaced by placeholders, plus prompts for the parts you write yourself.</span></span>
      </label>
      <label class="choice">
        <input type="checkbox" class="ver" value="team" id="verTeam">
        <span><strong>Team report</strong><span>Profiles the whole contributor list, ranked by weighted seniority signals with the evidence behind each. Needs no identity of your own.</span></span>
      </label>
    </div>
    <div class="ai-body" id="teamBody">
      <div class="warn">
        <strong>This report names your colleagues.</strong> It reads seniority from commit metadata,
        which cannot see code review, mentoring, design work or incident response. It is useful for
        understanding how the codebase is divided; it is not a performance assessment and should not
        be used as one.
      </div>
      <div class="grid2" style="margin-top:1rem">
        <div>
          <label for="top">Contributors to profile</label>
          <input type="text" id="top" value="8" inputmode="numeric">
        </div>
        <div>
          <label for="teamTitle">Team report title</label>
          <input type="text" id="teamTitle" placeholder="Contributor record">
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Titles</legend>
    <div class="grid2">
      <div>
        <label for="title">Detailed title</label>
        <input type="text" id="title" placeholder="Contribution record">
      </div>
      <div>
        <label for="shareTitle">Shareable title</label>
        <input type="text" id="shareTitle" placeholder="Engineering contribution record">
      </div>
    </div>
    <div style="margin-top:0.8rem">
      <label for="subtitle">Detailed standfirst (optional)</label>
      <input type="text" id="subtitle" placeholder="One line under the title">
    </div>
    <p class="hint" style="margin:0.8rem 0 0">The shareable version never inherits the detailed title
      or standfirst &mdash; free text you wrote for yourself may name the product or employer, and
      redaction cannot catch a name it never saw in the git history.</p>
  </fieldset>

  <fieldset>
    <legend>AI drafting</legend>
    <label class="choice" style="background:var(--surface)">
      <input type="checkbox" id="useAi">
      <span><strong>Use a model to draft prose and generic wording</strong>
      <span>Writes the work-stream sections from your commit subjects, and turns internal names into
      neutral descriptions such as &ldquo;a national logistics operator&rdquo; instead of
      &ldquo;Client deployment A&rdquo;.</span></span>
    </label>
    <div class="ai-body" id="aiBody">
      <div class="warn">
        <strong>This sends data off your machine.</strong> Directory names, branch names and commit
        subjects are sent to the provider. File contents and diffs are never sent. If those names are
        employer-confidential, check your policy before enabling this. The key is used for this run
        only and is never written to disk.
      </div>
      <div style="margin-top:1rem">
        <label for="key">API key</label>
        <input type="password" id="key" placeholder="sk-..." autocomplete="off">
      </div>
      <div class="grid2" style="margin-top:0.8rem">
        <div><label for="model">Model</label><input type="text" id="model" value="gpt-4o-mini"></div>
        <div><label for="baseUrl">Endpoint</label><input type="text" id="baseUrl" value="https://api.openai.com/v1"></div>
      </div>
      <p class="hint" style="margin:0.7rem 0 0">Any OpenAI-compatible endpoint works, including a
        local model &mdash; point it at <code>http://localhost:11434/v1</code> and nothing leaves
        this machine. The key is used for this run only and is never written to disk.</p>

      <div class="job">
        <h4>Work-stream prose</h4>
        <p class="hint">Turns your commit subjects into the narrative sections. Worth a stronger
          model.</p>
        <label for="proseExtra">Your instructions (appended to the built-in prompt)</label>
        <textarea id="proseExtra" rows="3" placeholder="e.g. Write in first person. Two sentences per stream. Emphasise the constraint that made each one hard."></textarea>
        <details>
          <summary>Built-in prompt this is added to</summary>
          <pre id="prosePrompt">loading…</pre>
          <p class="hint" style="margin:0.6rem 0 0">These rules stay in force. Your instructions are
            appended below them and framed as adjusting tone and emphasis, so they cannot switch off
            the &ldquo;never invent metrics&rdquo; rule.</p>
        </details>
        <label class="choice" style="margin-top:0.9rem;background:var(--surface)">
          <input type="checkbox" class="split" data-for="prose">
          <span><strong>Use a different provider for this job</strong></span>
        </label>
        <div class="split-body" id="proseSplit">
          <div><label for="proseKey">API key</label><input type="password" id="proseKey" autocomplete="off" placeholder="defaults to the key above"></div>
          <div class="grid2" style="margin-top:0.6rem">
            <div><label for="proseModel">Model</label><input type="text" id="proseModel" placeholder="defaults to above"></div>
            <div><label for="proseUrl">Endpoint</label><input type="text" id="proseUrl" placeholder="defaults to above"></div>
          </div>
        </div>
      </div>

      <div class="job">
        <h4>Redaction wording</h4>
        <p class="hint">Turns &ldquo;Client deployment A&rdquo; into &ldquo;a national logistics
          operator&rdquo;. Short and structured &mdash; a cheap or local model is usually enough,
          and this job sees the most sensitive names.</p>
        <label for="redactExtra">Your instructions (appended to the built-in prompt)</label>
        <textarea id="redactExtra" rows="3" placeholder="e.g. Prefer sector over geography. Never mention a country or region at all."></textarea>
        <details>
          <summary>Built-in prompt this is added to</summary>
          <pre id="redactPrompt">loading…</pre>
          <p class="hint" style="margin:0.6rem 0 0">The rule that stops the customer being named
            lives here and stays in force.</p>
        </details>
        <label class="choice" style="margin-top:0.9rem;background:var(--surface)">
          <input type="checkbox" class="split" data-for="redact">
          <span><strong>Use a different provider for this job</strong></span>
        </label>
        <div class="split-body" id="redactSplit">
          <div><label for="redactKey">API key</label><input type="password" id="redactKey" autocomplete="off" placeholder="defaults to the key above"></div>
          <div class="grid2" style="margin-top:0.6rem">
            <div><label for="redactModel">Model</label><input type="text" id="redactModel" placeholder="defaults to above"></div>
            <div><label for="redactUrl">Endpoint</label><input type="text" id="redactUrl" placeholder="defaults to above"></div>
          </div>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Save to</legend>
    <div class="row">
      <input type="text" id="out" placeholder="C:/Users/you/reports">
      <button type="button" class="ghost" id="browseOut">Browse</button>
    </div>
    <p class="hint" style="margin:0.7rem 0 0">Each run creates its own timestamped folder. Nothing is
      ever overwritten.</p>
  </fieldset>

  <div style="margin-top:1.75rem">
    <button type="button" class="primary" id="go">Generate report</button>
  </div>
  <div class="status" id="status"></div>
  <div id="out-files"></div>
</div>

<script>
const TOKEN = {token!r};
const $ = (id) => document.getElementById(id);

async function api(path, body) {{
  const res = await fetch(path, {{
    method: "POST",
    headers: {{ "Content-Type": "application/json", "X-Token": TOKEN }},
    body: JSON.stringify(body || {{}}),
  }});
  const data = await res.json().catch(() => ({{ error: "The server returned a malformed response." }}));
  if (!res.ok) throw new Error(data.error || ("Request failed: " + res.status));
  return data;
}}

function repoRow(value) {{
  const row = document.createElement("div");
  row.className = "row";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "repo";
  input.placeholder = "D:/code/my-repo";
  if (value) input.value = value;
  const browse = document.createElement("button");
  browse.type = "button"; browse.className = "ghost"; browse.textContent = "Browse";
  browse.onclick = async () => {{
    try {{
      const r = await api("/api/browse", {{ kind: "folder" }});
      if (r.path) input.value = r.path;
    }} catch (e) {{ setStatus(e.message, true); }}
  }};
  const remove = document.createElement("button");
  remove.type = "button"; remove.className = "ghost"; remove.textContent = "\\u00d7";
  remove.title = "Remove";
  remove.onclick = () => row.remove();
  row.append(input, browse, remove);
  return row;
}}

function repoPaths() {{
  return Array.from(document.querySelectorAll(".repo"))
    .map((i) => i.value.trim()).filter(Boolean);
}}

function setStatus(text, isError) {{
  const el = $("status");
  el.className = "status" + (isError ? " err" : "");
  el.innerHTML = text;
}}

$("addRepo").onclick = () => $("repos").append(repoRow(""));
$("useAi").onchange = (e) => $("aiBody").classList.toggle("on", e.target.checked);
$("verTeam").onchange = (e) => $("teamBody").classList.toggle("on", e.target.checked);

document.querySelectorAll(".split").forEach((box) => {{
  box.onchange = () => $(box.dataset.for + "Split").classList.toggle("on", box.checked);
}});

// Show the built-in prompts so authors can see exactly what they are adding to.
(async () => {{
  try {{
    const p = await api("/api/prompts", {{}});
    $("prosePrompt").textContent = p.prose;
    $("redactPrompt").textContent = p.redaction;
  }} catch (e) {{
    $("prosePrompt").textContent = "Could not load: " + e.message;
    $("redactPrompt").textContent = "Could not load: " + e.message;
  }}
}})();

$("browseOut").onclick = async () => {{
  try {{
    const r = await api("/api/browse", {{ kind: "folder" }});
    if (r.path) $("out").value = r.path;
  }} catch (e) {{ setStatus(e.message, true); }}
}};

$("detect").onclick = async () => {{
  const repos = repoPaths();
  if (!repos.length) return setStatus("Add at least one repository first.", true);
  setStatus('<span class="spin"></span>Reading repositories...');
  try {{
    const data = await api("/api/detect", {{ repos }});
    const box = $("ids");
    box.innerHTML = "";
    if (!data.identities.length) {{
      box.innerHTML = '<div class="id" style="color:var(--ink-faint)">No commits found.</div>';
    }}
    data.identities.forEach((identity, index) => {{
      const row = document.createElement("label");
      row.className = "id";
      // Nothing is ticked by default. In a team repository the most frequent
      // committers are your colleagues, and a pre-ticked list would quietly
      // produce a report about someone else.
      row.innerHTML =
        '<input type="checkbox" class="ident" value="' + identity.email.replace(/"/g, "&quot;") + '">' +
        '<span>' + identity.name.replace(/</g, "&lt;") + '</span>' +
        '<code>' + identity.email.replace(/</g, "&lt;") + '</code>' +
        '<span class="n">' + identity.commits.toLocaleString() + '</span>';
      box.append(row);
    }});
    const kinds = data.repos.map((r) => r.label + " \\u2014 " + r.kind).join(", ");
    setStatus("Found " + data.identities.length + " identities across " + kinds +
      ". They are listed most active first, which is the whole team \\u2014 tick only your own.");
  }} catch (e) {{ setStatus(e.message, true); }}
}};

function allAuthors() {{
  const ticked = Array.from(document.querySelectorAll(".ident:checked")).map((i) => i.value);
  const typed = $("manual").value.split(/[,;\\n]/).map((s) => s.trim()).filter(Boolean);
  return Array.from(new Set(ticked.concat(typed)));
}}

$("go").onclick = async () => {{
  const repos = repoPaths();
  const authors = allAuthors();
  const versions = Array.from(document.querySelectorAll(".ver:checked")).map((i) => i.value);
  const personal = versions.filter((v) => v !== "team");
  if (!repos.length) return setStatus("Add at least one repository.", true);
  if (!versions.length) return setStatus("Pick at least one version to generate.", true);
  if (personal.length && !authors.length) {{
    return setStatus("The detailed and shareable versions need your identity. Type your email above, "
      + "tick one below, or generate only the team report.", true);
  }}
  if (!$("out").value.trim()) return setStatus("Choose a folder to save into.", true);
  const anyKey = [$("key"), $("proseKey"), $("redactKey")].some((i) => i.value.trim());
  if ($("useAi").checked && !anyKey) {{
    return setStatus("AI drafting is on but no API key was entered.", true);
  }}

  $("go").disabled = true;
  $("out-files").innerHTML = "";
  setStatus('<span class="spin"></span>Reading history and writing the report. On large repositories this takes about a minute.');

  try {{
    const data = await api("/api/generate", {{
      repos, authors,
      versions,
      top: parseInt($("top").value, 10) || 8,
      teamTitle: $("teamTitle").value.trim(),
      authorName: $("authorName").value.trim(),
      title: $("title").value.trim(),
      subtitle: $("subtitle").value.trim(),
      shareableTitle: $("shareTitle").value.trim(),
      output: $("out").value.trim(),
      useAi: $("useAi").checked,
      apiKey: $("key").value,
      model: $("model").value.trim(),
      baseUrl: $("baseUrl").value.trim(),
      prose: {{
        apiKey: $("proseKey").value,
        model: $("proseModel").value.trim(),
        baseUrl: $("proseUrl").value.trim(),
        instructions: $("proseExtra").value,
      }},
      redaction: {{
        apiKey: $("redactKey").value,
        model: $("redactModel").value.trim(),
        baseUrl: $("redactUrl").value.trim(),
        instructions: $("redactExtra").value,
      }},
    }});

    let note = data.summary;
    if (data.warnings.length) {{
      note += "<br><br>" + data.warnings.map((w) => "Note: " + w).join("<br>");
    }}
    setStatus(note);

    const box = $("out-files");
    data.files.forEach((file) => {{
      const row = document.createElement("div");
      row.className = "file";
      const keep = file.sensitive;
      row.innerHTML =
        '<span class="tag' + (keep ? " keep" : "") + '">' + (keep ? "keep local" : file.version) + '</span>' +
        '<span class="p">' + file.path.replace(/</g, "&lt;") + '</span>';
      if (file.openable) {{
        const open = document.createElement("button");
        open.className = "ghost go"; open.textContent = "Open";
        open.onclick = () => api("/api/open", {{ path: file.path }}).catch((e) => setStatus(e.message, true));
        row.append(open);
      }}
      box.append(row);
    }});
  }} catch (e) {{
    setStatus(e.message, true);
  }} finally {{
    $("go").disabled = false;
  }}
}};

$("repos").append(repoRow(""));
</script>
</body>
</html>
"""
