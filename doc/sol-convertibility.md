# SOL Convertibility and Human Readability

SOL processes are plain JSON. That single design choice makes them trivially convertible to any visual or textual format without any runtime dependency, custom parser, or proprietary tooling.

---

## Why convertibility matters

A process description is only as good as its audience can read it. An AI agent reads JSON natively. A developer reads JSON with reasonable effort. A project manager, a client, or a non-technical stakeholder needs a diagram. A documentation system may need embedded flowcharts. A presentation tool needs slides.

SOL's structure — a flat list of typed instructions with explicit control-flow constructs — maps directly onto standard diagram primitives:

| SOL construct | Diagram primitive |
|---|---|
| `TODO`, `RUN` | Rectangle node |
| `IF`, `WHEN`, `REPEAT` | Diamond (decision) |
| `WAITUSERINPUT` | Parallelogram (I/O) |
| `HALT` | Terminal node |
| `SUB`, `AGENT` | Subgraph or subprocess shape |
| `SPAWN`, `DELEGATE` | Parallelogram with dashed link |
| `IMPORT` | Cylinder (data source) |
| Edge (sequential) | Solid arrow |
| Edge (ONERROR, CALL ref) | Dashed arrow |

This correspondence is complete and unambiguous. There is no SOL construct that cannot be rendered as a standard flowchart element.

---

## Three ready-made converters

The `sol` skill ships three Python 3 scripts (no external dependencies):

### `sol2mermaid.py` — Mermaid flowchart

Converts a SOL JSON file into a `.mmd` Mermaid flowchart definition.

```bash
python3 sol2mermaid.py process.json              # writes process.mmd
python3 sol2mermaid.py process.json output.mmd   # custom output path
python3 sol2mermaid.py process.json --stdout     # print to stdout
```

The `.mmd` output can be:
- Rendered live at **https://mermaid.live**
- Embedded in any Markdown file as a fenced code block (GitHub, GitLab, Obsidian, Notion, VS Code preview all render Mermaid natively)
- Piped into the `mmdc` CLI to produce PNG or SVG

Because Mermaid is text, the diagram is version-controllable alongside the SOL source: a single `git diff` shows both process logic and diagram changes together.

### `sol2drawio.py` — draw.io XML

Converts a SOL JSON file into a `.drawio` file (XML format).

```bash
python3 sol2drawio.py process.json               # writes process.drawio
python3 sol2drawio.py process.json output.drawio # custom output path
python3 sol2drawio.py process.json --stdout      # print to stdout
```

The `.drawio` file can be:
- Opened directly in **https://app.diagrams.net** (no account required)
- Opened in the **draw.io desktop app** (Windows, Mac, Linux)
- Embedded in Confluence, Notion, and other tools via the draw.io plugin
- Exported to PNG, SVG, or PDF from within draw.io

After opening the file, apply **Ctrl+Shift+H** (Arrange → Layout → Vertical Tree) to get a clean automatic layout. All node colors match the Mermaid output convention so diagrams look consistent across both formats.

---

### `sol2prose.py` — narrative prose

Converts a SOL file into a `.prose.md` document: the process restated in plain language in
execution order — what happens, in what sequence, with which decisions, loops, error paths and
human gates. It is the inverse of *Pass 0 — Narrative* in the skill's authoring discipline.

```bash
python3 sol2prose.py process.json               # writes process.prose.md
python3 sol2prose.py process.json out.md        # custom output path
python3 sol2prose.py process.json --stdout      # print to stdout
python3 sol2prose.py process.md                 # renders each json fence in a markdown host
python3 sol2prose.py process.json --lang it     # scaffolding in Italian (default: en)
```

Unlike the two diagram converters it also accepts a **markdown host document**, rendering every
`json` code fence that parses to a SOL object — the json-in-md pattern most real scripts use.

Two rules define what it does and does not do:

- **It never translates.** Only the connective scaffolding (*"For each…"*, *"Otherwise:"*) is
  templated per language via `--lang`. Every leaf — `TODO` text, `RUN` command, conditions,
  contract descriptions — is quoted **verbatim**, in whatever language the author wrote it. That
  is what makes a leaf-by-leaf comparison against the source exact.
- **It renders, it does not judge.** None of `sol-lint.py`'s rules are reproduced: no severities,
  no findings, no verdicts. Rendering and linting are separate jobs.

The output surfaces what a flowchart cannot show: the leaf texts themselves, the `accepts` /
`returns` contracts field by field, the `model` and `role` intent, and every `{{placeholder}}`
marked as a value that is *not* in the document. A `WHEN` with no `else` is stated as such.
Because the default output is `<stem>.prose.md` and never `<stem>.md`, running it on a markdown
host document cannot overwrite the source.

#### Why it exists: round-trip validation

The diagram shows the *shape* of a process; the prose shows its *content*. The intended use is to
read back, in plain language, what you wrote in JSON, and check that it says what you meant. If
the narrative reads wrong, the SOL is wrong — fix the script and regenerate. The prose is a
derived view like the diagrams: never edited by hand.

```
prose → (the `sol` skill) → SOL → (sol2prose.py) → prose
```


---

## Color conventions

The two diagram converters use the same semantic color scheme:

| Color | Construct |
|---|---|
| Blue | `TODO` — agent judgment |
| Green | `RUN` — exact shell command |
| Yellow | `IF` / `WHEN` / `REPEAT` — control flow |
| Purple | `AGENT` / `SPAWN` / `DELEGATE` — sub-agents |
| Dark slate | `START` / `END` / `HALT` — terminals |
| Red | `ONERROR` — error paths |
| Orange | `WAITUSERINPUT` — human interaction |
| Light green | `SUB` / `CALL` — subroutines |
| Light slate | `IMPORT` — external files |

---

## Human readability of raw SOL

Before reaching any diagram tool, a SOL file is already highly readable to anyone familiar with JSON:

```json
{
  "name": "daily-briefing",
  "version": "1.0",
  "description": "Generate daily briefing from project status files. Run each morning.",
  "ROUTINE": [
    { "TODO": "Read all status files in projects/" },
    {
      "WHEN": [
        { "when": "any project has overdue tasks",
          "then": [ { "TODO": "List overdue items and flag urgency" } ] },
        { "when": "any deadline within 3 days",
          "then": [ { "TODO": "Highlight upcoming deadlines" } ] }
      ]
    },
    { "TODO": "Write briefing to output/daily-briefing.md", "model": "smart" }
  ]
}
```

The uppercase keywords (`TODO`, `WHEN`, `ROUTINE`) are intentionally loud — they make the control structure scannable without a diagram tool. A reader can parse the process semantics by eye in under a minute for any real-world process.

---

## The convertibility chain

```
Natural language / pseudocode / YAML / XML
           ↓  sol skill
        SOL JSON  (.json / json fence in .md)
           ↓                 ↓                 ↓
    sol2mermaid.py      sol2drawio.py      sol2prose.py
           ↓                 ↓                 ↓
    Mermaid (.mmd)    draw.io (.drawio)   prose (.prose.md)
           ↓                 ↓                 ↓
  PNG / SVG / embed  PNG / SVG / PDF     read it back and
                                          check it says what
                                          you meant
```

The prose branch closes the loop: the chain now returns to the register it started from, so a
process can be checked against the intent that produced it.

Each step in this chain is a lossless or near-lossless transformation. The SOL JSON remains the single source of truth; the visual formats are derived views, regeneratable at any time.

---

## Invoking the converters from the skill

When using `/sol`, after generating the SOL files the skill asks:

```
SOL files generated. Would you like a derived view? Reply:
  MERMAID [filename] — Mermaid flowchart (.mmd)
  DRAWIO [filename]  — draw.io XML (.drawio)
  PROSE [filename]   — narrative rendering (.prose.md)
  NO                 — finish without one
```

All three scripts are also usable standalone, outside the skill, on any SOL file.

---

## Portability guarantees

All three scripts are:
- **Pure Python 3** — no external packages, no pip install
- **Self-contained** — a single file, copyable anywhere
- **Offline** — no network calls, no API keys
- **Deterministic** — same input always produces the same output
- **Fast** — convert even large processes in under a second

This means diagrams can be generated in CI pipelines, pre-commit hooks, documentation build steps, or any scripting environment without any setup beyond Python 3.
