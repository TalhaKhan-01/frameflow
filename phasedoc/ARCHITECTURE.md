# Frameflow: architecture

The top row is the groundwork. The two rows below are the daily pipeline, from an idea to a posted video and back into learning. Each box is coloured live from the task tree: grey = not started, amber = in progress, green = done and verified.

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 470" width="980" height="470" font-family="system-ui, sans-serif" font-size="14">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor" opacity="0.6"/>
    </marker>
  </defs>
  <text x="20" y="22" fill="currentColor" opacity="0.7" font-size="12">GROUNDWORK</text>
  <g id="comp-setup"><rect x="20" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Setup</text>
    <text x="105" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">accounts, keys, repo, vault</text></g>
  <g id="comp-research"><rect x="210" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Research</text>
    <text x="295" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">niche + deep study</text></g>
  <g id="comp-quality"><rect x="400" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Quality bar</text>
    <text x="485" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">targets + script rules</text></g>
  <g id="comp-scenes"><rect x="590" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Scene library</text>
    <text x="675" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">templates + identity</text></g>
  <g id="comp-assets"><rect x="780" y="32" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Assets</text>
    <text x="870" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">stock, music, licences</text></g>

  <text x="20" y="148" fill="currentColor" opacity="0.7" font-size="12">DAILY PIPELINE</text>
  <g id="comp-ideas"><rect x="20" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Ideas</text>
    <text x="105" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">collect + rank</text></g>
  <g id="comp-script"><rect x="210" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Script</text>
    <text x="295" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">script + scene plan</text></g>
  <g id="comp-voice"><rect x="400" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Voice</text>
    <text x="485" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">local text-to-speech</text></g>
  <g id="comp-captions"><rect x="590" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Captions</text>
    <text x="675" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">word timings, word-pop</text></g>
  <g id="comp-render"><rect x="780" y="158" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Render</text>
    <text x="870" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">one command → MP4</text></g>

  <g id="comp-qa"><rect x="780" y="284" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Checks + approval</text>
    <text x="870" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">auto QA, AI review, Talha</text></g>
  <g id="comp-publish"><rect x="590" y="284" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Publish</text>
    <text x="675" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">pack + manual upload</text></g>
  <g id="comp-feedback"><rect x="400" y="284" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Feedback</text>
    <text x="485" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">48 h stats, weekly lessons</text></g>
  <g id="comp-launch"><rect x="20" y="284" width="360" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="200" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Launch</text>
    <text x="200" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">3 pilots → 7-day cadence → retrospective</text></g>

  <g stroke="currentColor" stroke-opacity="0.55" stroke-width="1.6" fill="none" marker-end="url(#arrow)">
    <path d="M190,190 H208"/><path d="M380,190 H398"/><path d="M570,190 H588"/><path d="M760,190 H778"/>
    <path d="M870,222 V282"/><path d="M780,316 H762"/><path d="M590,316 H572"/><path d="M400,316 H382"/>
    <path d="M485,348 V400 H8 V190 H16" stroke-dasharray="5 4"/>
    <path d="M485,96 V156" stroke-dasharray="3 3"/><path d="M675,96 V156" stroke-dasharray="3 3"/><path d="M870,96 V156" stroke-dasharray="3 3"/>
  </g>
  <text x="300" y="424" fill="currentColor" opacity="0.7" font-size="12">learning loop: results feed the next ideas and the quality bar</text>
</svg>

## Components
| Key | What it is | Phase |
|---|---|---|
| `setup` | Accounts, keys, repository, vault, secrets | P0 |
| `research` | Niche study and deep study | P1 |
| `quality` | Quality bar targets and script rules | P1 |
| `voice` | Local text-to-speech and the voice step | P2 |
| `scenes` | Renderer, scene-plan contract, visual identity, templates | P3 |
| `captions` | Word-pop caption layer and word timings | P3, P6 |
| `ideas` | Idea collector and ranking | P4 |
| `script` | Script and scene-plan writer, source checks | P4 |
| `assets` | Keyless stock, licence ledger, music and sound effects | P5 |
| `render` | One-command render | P6 |
| `qa` | Automatic checks, AI review, approval gate | P6 |
| `publish` | Publish pack, post log | P7 |
| `feedback` | 48-hour stats and weekly learning | P7 |
| `launch` | Pilot, cadence week, retrospective | P8 |
| `writer` | shorts-writer skill: persona, hooks, beat sheet, slop linter, voice markup | P9 |
| `director` | shorts-director skill: storyboard, metaphor bank, compiler | P9 |
| `sound` | SFX library v2, cue-sheet mix, energy-curve beds | P9 |
| `pilot` | Black October pilot video | P9 |
