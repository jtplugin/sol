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

## Two ready-made converters

The `sol-translate` skill ships two Python 3 scripts (no external dependencies):

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

## Color conventions

Both converters use the same semantic color scheme:

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
           ↓  sol-translate skill
        SOL JSON  (.json)
           ↓                    ↓
    sol2mermaid.py         sol2drawio.py
           ↓                    ↓
    Mermaid (.mmd)        draw.io (.drawio)
           ↓                    ↓
  PNG / SVG / embed      PNG / SVG / PDF / embed
```

Each step in this chain is a lossless or near-lossless transformation. The SOL JSON remains the single source of truth; the visual formats are derived views, regeneratable at any time.

---

## Invoking the converters from the skill

When using `/sol-translate`, after generating the SOL files the skill asks:

```
SOL files generated. Would you like a diagram? Reply:
  MERMAID [filename] — Mermaid flowchart (.mmd)
  DRAWIO [filename]  — draw.io XML (.drawio)
  NO                 — finish without a diagram
```

Both scripts are also usable standalone, outside the skill, on any SOL JSON file.

---

## Portability guarantees

Both scripts are:
- **Pure Python 3** — no external packages, no pip install
- **Self-contained** — a single file, copyable anywhere
- **Offline** — no network calls, no API keys
- **Deterministic** — same input always produces the same output
- **Fast** — convert even large processes in under a second

This means diagrams can be generated in CI pipelines, pre-commit hooks, documentation build steps, or any scripting environment without any setup beyond Python 3.
