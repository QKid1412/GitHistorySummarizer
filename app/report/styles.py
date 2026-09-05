"""The report's visual system.

Light and dark are modelled on marine chart displays, which carry day and night
palettes for the same chart. Tokens are defined three times so the page resolves
correctly whether the viewer picked a theme explicitly or left it on system.
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&"
    'family=Spectral:ital,wght@0,500;0,600;1,500&display=swap">'
)

DARK_TOKENS = """
      --ground:      #060D13;
      --surface:     #0C1720;
      --surface-2:   #111F2A;
      --ink:         #C6D6DE;
      --ink-soft:    #7B94A2;
      --ink-faint:   #5A7383;
      --accent:      #4CBAD6;
      --accent-soft: #102C38;
      --flag:        #E07BA6;
      --flag-soft:   #2A1622;
      --rule:        #1B2C38;
      --rule-soft:   #142330;
"""

CSS = """
  :root {
    --ground:      #EEF1EE;
    --surface:     #FFFFFF;
    --surface-2:   #F6F9F7;
    --ink:         #101F29;
    --ink-soft:    #4E6573;
    --ink-faint:   #7C93A0;
    --accent:      #00637F;
    --accent-soft: #DEECF1;
    --flag:        #A83562;
    --flag-soft:   #F4E3EA;
    --rule:        #D2DAD8;
    --rule-soft:   #E4EAE7;

    --f-display: "Spectral", Georgia, "Times New Roman", serif;
    --f-body:    "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    --f-mono:    "IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;

    --measure: 68ch;
    --pad: clamp(1.25rem, 4vw, 3rem);
  }

  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {__DARK__}
  }

  :root[data-theme="dark"] {__DARK__}

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: var(--f-body);
    font-size: 16px;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }

  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 var(--pad) 6rem; }
  .col { max-width: var(--measure); }

  .masthead { padding: clamp(3rem, 8vw, 5.5rem) 0 0; display: flex; flex-direction: column; gap: 1.75rem; }

  .eyebrow {
    font-family: var(--f-mono); font-size: 0.7rem; font-weight: 500;
    letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent); margin: 0;
  }

  h1 {
    font-family: var(--f-display); font-weight: 600;
    font-size: clamp(2.5rem, 7vw, 4.25rem); line-height: 1.04;
    letter-spacing: -0.02em; text-wrap: balance; margin: 0;
  }

  .standfirst {
    font-family: var(--f-display); font-size: clamp(1.075rem, 2.2vw, 1.3rem);
    line-height: 1.6; color: var(--ink-soft); margin: 0; max-width: 60ch;
  }

  .byline {
    display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem;
    font-family: var(--f-mono); font-size: 0.775rem; color: var(--ink-faint);
    margin: 0; padding-top: 0.25rem;
  }
  .byline strong { color: var(--ink-soft); font-weight: 500; }

  .stats {
    margin: 3.5rem 0 0; display: grid;
    grid-template-columns: repeat(auto-fit, minmax(158px, 1fr));
    gap: 1px; background: var(--rule); border: 1px solid var(--rule);
  }
  .stat { background: var(--surface); padding: 1.15rem 1.25rem; display: flex; flex-direction: column; gap: 0.3rem; }
  .stat b {
    font-family: var(--f-mono); font-variant-numeric: tabular-nums;
    font-size: 1.6rem; font-weight: 600; line-height: 1;
    letter-spacing: -0.02em; color: var(--ink);
  }
  .stat span {
    font-family: var(--f-mono); font-size: 0.66rem; letter-spacing: 0.11em;
    text-transform: uppercase; color: var(--ink-faint); line-height: 1.4;
  }

  section { padding-top: 4.5rem; }

  h2 {
    font-family: var(--f-display); font-weight: 600;
    font-size: clamp(1.6rem, 3.6vw, 2.15rem); line-height: 1.2;
    letter-spacing: -0.015em; text-wrap: balance; margin: 0 0 0.4rem;
    padding-bottom: 0.75rem; border-bottom: 2px solid var(--ink);
  }
  h3 {
    font-family: var(--f-body); font-weight: 600; font-size: 1.03rem;
    line-height: 1.35; margin: 0; text-wrap: balance;
  }

  p { margin: 0 0 1rem; }
  p:last-child { margin-bottom: 0; }

  .lede {
    font-family: var(--f-display); font-size: 1.1rem; line-height: 1.6;
    color: var(--ink-soft); margin: 1.25rem 0 0; max-width: 62ch;
  }

  a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }

  code, .mono {
    font-family: var(--f-mono); font-size: 0.855em; background: var(--surface-2);
    border: 1px solid var(--rule-soft); border-radius: 3px;
    padding: 0.08em 0.34em; color: var(--ink-soft);
  }

  .split {
    margin-top: 2rem; display: flex; flex-direction: column; gap: 1px;
    background: var(--rule); border: 1px solid var(--rule);
  }
  .split-row {
    background: var(--surface); display: grid; grid-template-columns: 7.5rem 1fr;
    gap: 0 1.25rem; align-items: center; padding: 0.85rem 1.25rem;
  }
  .split-label {
    font-family: var(--f-mono); font-size: 0.72rem; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink-faint);
  }
  .split-bar { display: flex; height: 26px; border-radius: 3px; overflow: hidden; background: var(--surface-2); }
  .seg {
    display: flex; align-items: center; padding: 0 0.5rem;
    font-family: var(--f-mono); font-variant-numeric: tabular-nums;
    font-size: 0.7rem; font-weight: 500; white-space: nowrap; min-width: 0;
  }
  .seg-a { background: var(--accent); color: var(--surface); justify-content: flex-end; }
  .seg-b { background: var(--accent-soft); color: var(--accent); justify-content: flex-start; }
  :root[data-theme="dark"] .seg-a, :root:not([data-theme="light"]) .seg-a { color: #06131A; }

  .split-key {
    display: flex; gap: 1.25rem; margin-top: 1rem; font-family: var(--f-mono);
    font-size: 0.68rem; letter-spacing: 0.07em; text-transform: uppercase; color: var(--ink-faint);
  }
  .split-key span { display: inline-flex; align-items: center; gap: 0.45rem; }
  .dot { width: 11px; height: 11px; border-radius: 2px; flex: none; }

  @media (max-width: 620px) { .split-row { grid-template-columns: 1fr; gap: 0.45rem; } }

  .scroller { overflow-x: auto; }

  table { width: 100%; border-collapse: collapse; margin-top: 2rem; font-size: 0.885rem; min-width: 560px; }
  th, td { text-align: left; padding: 0.62rem 0.9rem; border-bottom: 1px solid var(--rule-soft); vertical-align: top; }
  thead th {
    font-family: var(--f-mono); font-size: 0.64rem; letter-spacing: 0.11em;
    text-transform: uppercase; color: var(--ink-faint); font-weight: 500;
    border-bottom: 1.5px solid var(--rule); white-space: nowrap;
  }
  td.num { font-family: var(--f-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.br { font-family: var(--f-mono); font-size: 0.8rem; color: var(--ink); white-space: nowrap; }
  tbody tr:hover { background: var(--surface-2); }
  .share { color: var(--ink-faint); }
  .share.high { color: var(--flag); font-weight: 500; }

  .timeline { margin-top: 2.25rem; display: flex; flex-direction: column; }
  .yr {
    display: grid; grid-template-columns: 5.5rem 1fr; gap: 0 1.75rem;
    padding: 1.15rem 0; border-top: 1px solid var(--rule-soft); align-items: start;
  }
  .yr:first-child { border-top: none; }
  .yr-num {
    font-family: var(--f-mono); font-variant-numeric: tabular-nums;
    font-size: 1.05rem; font-weight: 600; color: var(--ink); padding-top: 0.1rem;
  }
  .yr-body { display: flex; flex-direction: column; gap: 0.5rem; }
  .bar {
    display: flex; align-items: center; gap: 0.6rem; font-family: var(--f-mono);
    font-size: 0.68rem; color: var(--ink-faint); font-variant-numeric: tabular-nums;
  }
  .bar-track { height: 5px; background: var(--accent); border-radius: 3px; min-width: 3px; opacity: 0.85; }
  @media (max-width: 620px) { .yr { grid-template-columns: 1fr; gap: 0.5rem; } }

  .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 1.5rem; }
  .chip {
    font-family: var(--f-mono); font-size: 0.75rem; padding: 0.28rem 0.6rem;
    border: 1px solid var(--rule); border-radius: 3px; color: var(--ink-soft); background: var(--surface);
  }
  .chip b { color: var(--ink); font-weight: 600; }

  .draft {
    margin-top: 2rem; border: 1px dashed var(--rule); background: var(--surface-2);
    padding: 1.35rem 1.5rem; display: flex; flex-direction: column; gap: 0.6rem;
  }
  .draft h3 { color: var(--ink-soft); }
  .draft p { margin: 0; font-size: 0.93rem; color: var(--ink-faint); line-height: 1.62; }
  .draft ul { margin: 0.2rem 0 0; padding-left: 1.1rem; color: var(--ink-faint); font-size: 0.9rem; }
  .draft li { margin-bottom: 0.3rem; }

  .note {
    margin-top: 2rem; border: 1px solid var(--flag); border-left-width: 3px;
    background: var(--flag-soft); padding: 1.15rem 1.35rem;
    display: flex; flex-direction: column; gap: 0.55rem;
  }
  .note h3 { color: var(--ink); }
  .note p { margin: 0; font-size: 0.925rem; color: var(--ink-soft); line-height: 1.62; }

  details { margin-top: 2rem; border: 1px solid var(--rule); background: var(--surface); }
  summary {
    cursor: pointer; padding: 0.95rem 1.25rem; font-family: var(--f-mono);
    font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-soft);
  }
  .details-body {
    padding: 0 1.25rem 1.25rem; font-size: 0.9rem; color: var(--ink-soft);
    display: flex; flex-direction: column; gap: 0.75rem;
  }
  .details-body p { margin: 0; line-height: 1.6; }

  .prompts, .bullets, .checks {
    margin: 2rem 0 0; padding: 0; list-style: none;
    display: flex; flex-direction: column; gap: 1px;
    background: var(--rule); border: 1px solid var(--rule);
  }
  .prompts li, .checks li { background: var(--surface); padding: 1.15rem 1.35rem; display: flex; flex-direction: column; gap: 0.4rem; }
  .prompts h4 {
    margin: 0; font-family: var(--f-body); font-weight: 600; font-size: 0.99rem; color: var(--ink);
  }
  .prompts p, .checks p { margin: 0; font-size: 0.93rem; line-height: 1.62; color: var(--ink-soft); }
  .prompts .ev {
    font-family: var(--f-mono); font-size: 0.7rem; color: var(--accent);
    letter-spacing: 0.03em; margin-top: 0.15rem;
  }

  .bullets li {
    background: var(--surface); padding: 1rem 1.25rem 1rem 2.75rem; position: relative;
    font-size: 0.945rem; line-height: 1.6; color: var(--ink-soft);
  }
  .bullets li::before {
    content: ""; position: absolute; left: 1.25rem; top: 1.5rem;
    width: 8px; height: 8px; border: 1.5px solid var(--accent); border-radius: 50%;
  }
  .slot {
    font-family: var(--f-mono); font-size: 0.86em; color: var(--flag);
    background: var(--flag-soft); border-radius: 3px; padding: 0.05em 0.3em;
  }

  .checks li { flex-direction: row; gap: 0.85rem; align-items: flex-start; }
  .checks .box {
    flex: none; width: 13px; height: 13px; margin-top: 0.32rem;
    border: 1.5px solid var(--ink-faint); border-radius: 2px;
  }

  footer {
    margin-top: 4.5rem; padding-top: 1.5rem; border-top: 1px solid var(--rule);
    font-family: var(--f-mono); font-size: 0.7rem; letter-spacing: 0.06em; color: var(--ink-faint);
  }

  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
""".replace("__DARK__", DARK_TOKENS)
