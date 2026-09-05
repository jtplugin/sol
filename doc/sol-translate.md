# sol-translate — Skill Reference

> A Claude Code skill that converts any document written in natural language, pseudocode, YAML, or XML into a valid SOL process.

---

## Overview

`sol-translate` bridges the gap between how people describe processes (prose, diagrams, pseudocode, configuration files) and the precise, executable structure that SOL requires.

You give it a document. It gives you back one or more SOL JSON files — with the right constructs, the right model tiers, and the right file structure for the complexity of what you described.

It also ships three standalone Python scripts that render any SOL file as a derived view: `sol2mermaid.py` for Mermaid flowcharts, `sol2drawio.py` for draw.io XML, and `sol2prose.py` for a narrative rendering in plain language — the return trip, used to check that the generated SOL says what you meant.

---

## Installation

The skill follows the standard Claude Code directory convention. It works at two scopes:

### Personal install (available in all your projects)

```bash
mkdir -p ~/.claude/skills/sol-translate
cp -r .claude/skills/sol-translate/. ~/.claude/skills/sol-translate/
```

### Project install (this project only)

Clone or copy the repository. The skill is already in `.claude/skills/sol-translate/` — no further setup required.

### Requirements

- Claude Code (any recent version)
- Python 3.8+ for `sol2mermaid.py` and `sol2drawio.py` (no third-party packages required)

---

## Usage

Invoke the skill from Claude Code:

```
/sol-translate
```

Then either paste the source document inline or specify a file path when prompted.

You can also pass the input directly as an argument:

```
/sol-translate path/to/my-process.yaml
/sol-translate path/to/flow-description.md
```

---

## What the skill does

The skill runs in five phases:

### 1. Parse

Reads the input and identifies its format: natural language, pseudocode, YAML, or XML. Mixed or ambiguous inputs are treated as natural language.

### 2. Analyze

Extracts the semantic structure of the process:

- Sequential vs. parallelizable steps
- Loops (`for`, `foreach`, `while`, `until`)
- Conditions (binary `IF`, exclusive `WHEN`)
- Error paths and recovery steps
- Human checkpoints or approval gates
- The cognitive role the AI plays in each phase (executive, analytical, creative, supervisory)

### 3. Resolve ambiguities

When a translation decision cannot be made confidently — whether a step is sequential or parallelizable, whether conditions are mutually exclusive, how error paths should behave — the skill pauses and asks.

You answer before any file is written. No guessing behind your back.

### 4. Generate SOL

Produces the SOL file(s) using the right constructs:

| Source pattern | SOL construct used |
|---|---|
| "do X" with agent judgment | `TODO` |
| Exact shell command | `RUN` |
| if / else | `IF` |
| switch with exclusive branches | `WHEN` |
| loop / repeat / for each | `REPEAT` |
| helper called multiple times | `SUB` + `CALL` |
| isolated task with input/output contract | `AGENT` + `SPAWN` |
| one-off isolated sub-task | `DELEGATE` |
| human review / approval gate | `WAITUSERINPUT` |
| "stop if nothing to do" | `HALT` |

Model tiers are assigned automatically:

| Tier | Assigned when |
|---|---|
| `fast` | Mechanical steps, formatting, simple I/O |
| `smart` | Analysis, synthesis, ambiguous decisions |
| `balanced` | Everything else (default) |

### 5. File structure

The skill decides how many files to generate:

- **Single file** — process has fewer than ~15 top-level instructions and no reusable cross-process components
- **Multi-file** — two or more named `AGENT` definitions (each goes to `agents/<name>.json`), or `SUB` blocks reusable across processes (go to `shared/<name>.json`); a main entry point imports them via `IMPORT`

### 6. Derived view (optional)

After the SOL files are written, the skill asks whether you want a derived view and in which
format:

```
python3 sol2mermaid.py <process.json>   # Mermaid flowchart (.mmd)
python3 sol2drawio.py  <process.json>   # draw.io XML (.drawio)
python3 sol2prose.py   <process.json>   # narrative prose (.prose.md)
```

The two diagram scripts use the same semantic color scheme, so diagrams look consistent across
formats. The prose script closes the loop the translation opened: you described the process in
plain language, and you get it back in plain language to check against what you meant.

---

## sol2mermaid.py

A self-contained Python script. No dependencies beyond the standard library.

### Usage

```bash
# writes process.mmd next to the input file
python3 sol2mermaid.py process.json

# writes to a specific path
python3 sol2mermaid.py process.json diagrams/process.mmd

# prints to stdout
python3 sol2mermaid.py process.json --stdout
```

### What it renders

Every SOL 0.6 construct is supported:

| Construct | Rendered as |
|---|---|
| `TODO` | Blue rectangle |
| `RUN` | Green rectangle (monospace label) |
| `IF` | Yellow diamond with yes/no branches and merge node |
| `WHEN` | Chain of yellow diamonds with shared merge node |
| `REPEAT` | Yellow diamond with continue/exit edges and back-loop |
| `SUB` definition | Deferred subgraph; inline "define SUB" marker in main flow |
| `CALL` | Subroutine shape; dashed link to the SUB subgraph |
| `AGENT` definition | Deferred subgraph with accepts/returns labels |
| `SPAWN` | Purple parallelogram; dashed link to the AGENT subgraph |
| `DELEGATE` | Purple parallelogram |
| `IMPORT` | Cylinder node |
| `RETURN` | Grey terminal node (yields to caller) |
| `HALT` | Dark red terminal node |
| `WAITUSERINPUT` | Orange parallelogram |
| `ONERROR` (inline) | Red node connected with a dashed error edge |
| Global `ONERROR` | Standalone red node at end of diagram |

### Rendering the output

The `.mmd` file can be rendered in any of these:

- **[mermaid.live](https://mermaid.live)** — paste and preview instantly
- **VS Code** — with the [Mermaid Preview](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) extension
- **GitHub** — Mermaid blocks in Markdown files are rendered natively
- **Obsidian** — natively supported in preview mode
- **Any Markdown renderer** that supports fenced Mermaid blocks

To embed in a Markdown document, wrap the output in a code fence:

````markdown
```mermaid
flowchart TD
    ...
```
````

---

## sol2drawio.py

A self-contained Python script that converts any SOL file into a `.drawio` XML file. No dependencies beyond the standard library.

### Usage

```bash
# writes process.drawio next to the input file
python3 sol2drawio.py process.json

# writes to a specific path
python3 sol2drawio.py process.json diagrams/process.drawio

# prints to stdout
python3 sol2drawio.py process.json --stdout
```

### Rendering the output

The `.drawio` file can be opened in any of these:

- **[app.diagrams.net](https://app.diagrams.net)** — open directly in the browser, no account required
- **draw.io desktop app** (Windows, Mac, Linux)
- **Confluence / Notion** — via the draw.io plugin
- Export to PNG, SVG, or PDF from within draw.io

After opening, apply **Ctrl+Shift+H** (Arrange → Layout → Vertical Tree) to get a clean automatic layout.

Node colors match the Mermaid convention exactly — the same semantic color scheme applies to both formats.

---

## sol2prose.py

A self-contained Python script that renders any SOL file — or the `json` code fences inside a
markdown host document — as narrative prose in execution order. No dependencies beyond the
standard library.

### Usage

```bash
# writes process.prose.md next to the input file
python3 sol2prose.py process.json

# writes to a specific path
python3 sol2prose.py process.json docs/process.md

# prints to stdout
python3 sol2prose.py process.json --stdout

# renders every SOL fence inside a markdown host document
python3 sol2prose.py process.md

# scaffolding in Italian (default: en)
python3 sol2prose.py process.json --lang it
```

The default output is `<stem>.prose.md`, never `<stem>.md`: a bare `.md` would overwrite the
markdown document that hosts the SOL fences.

### What it renders

| Construct | Rendered as |
|---|---|
| Root | Title, description, version / `model` / `role` / `env`, and the `accepts` / `returns` contracts field by field |
| `TODO` | The instruction text, verbatim |
| `RUN` | "Run exactly: `<command>`", verbatim |
| `IF` | "If …, then:" with an indented body, plus "Otherwise:" |
| `WHEN` | "Depending on the case:" with one "When …:" block per branch; a `WHEN` with no `else` says so explicitly |
| `REPEAT` | "For each …:" / "While …, repeat:" / "Repeat until …:" / "Repeat N times:" |
| `SUB` / `AGENT` definitions | A marker in the flow; the body in a *Subroutines* / *Agents* appendix |
| `CALL` | "Call the subroutine «…», which sees everything this process sees." |
| `SPAWN` / `DELEGATE` | The hand-off to a clean context, with what is passed and what is expected back |
| `IMPORT` | "Load the definitions from …" |
| `RETURN` | "End this process and hand control back to whoever invoked it…" |
| `HALT` | "Stop the entire run…" |
| `WAITUSERINPUT` | "Pause and ask the human: …" |
| `ONERROR` | "If that fails:" nested under the step it guards; the global handler gets its own section |
| `model` / `role` | Trailing markers on the step — intent a flowchart cannot show |
| `{{placeholder}}` | Flagged as a value coming from context, not from the document |

### Two rules

- **It never translates.** `--lang` templates only the connective scaffolding. Leaves are quoted
  verbatim in the language the author wrote them, so the comparison against the source is exact.
- **It renders, it does not judge.** Correctness findings stay with `sol-lint.py`.


---

## Example

Given this natural language description:

> Every morning, read all the project status files. If any project has overdue tasks, list them at the top. Summarize progress since yesterday for each active project, then write the briefing to a file.

The skill produces something close to the `daily-briefing.json` example already in this repository — with `WHEN` for the conditional sections, `model: "fast"` on the summary step, and `model: "smart"` on the synthesis step.

Running `sol2mermaid.py` on it produces a Mermaid flowchart with a chain of condition diamonds (overdue, deadline-soon, inactive) converging to the summary and write steps. Running `sol2drawio.py` on the same file produces an equivalent draw.io diagram with identical color conventions.

---

## File layout

```
.claude/skills/sol/
├── SKILL.md              ← skill definition (the refinement passes and the reference tables)
├── spec/
│   └── reference.md      ← full SOL 0.6 specification
├── guides/               ← binding authoring guides (authoring, contracts, borderline cases,
│                            translation, sol-vs-prose)
├── scripts/
│   ├── sol-lint.py       ← deterministic linter (Python, no external dependencies)
│   ├── sol2mermaid.py    ← Mermaid generator (Python, no external dependencies)
│   ├── sol2drawio.py     ← draw.io XML generator (Python, no external dependencies)
│   └── sol2prose.py      ← narrative prose renderer (Python, no external dependencies)
└── LICENSE               ← MIT
```

---

## License

MIT License — Copyright (c) 2026 Gianni Tommasi.
See [LICENSE](../.claude/skills/sol/LICENSE).
