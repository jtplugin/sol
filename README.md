# SOL — Simple Orchestration Language

A minimal JSON format for defining processes that AI agents can read and execute — no runtime required.

> Current spec: **line v0.6** — [spec/sol-0.6.md](spec/sol-0.6.md)

## What it is

SOL is a structured process definition format. You write a process as a JSON document. An AI agent reads it, understands the intent, and executes it — with full autonomy over parallelization, error handling, and model selection.

No interpreter. No SDK dependency. No graph to draw.

**The core premise:** the agent is the runtime. SOL expresses *what* a process does — execution strategy, parallelization, and model selection are concerns of the execution context.

## Quick example

```json
{
  "name": "daily-briefing",
  "version": "1.0",
  "description": "Generate a daily briefing from project status files.",
  "ref": "https://github.com/jtplugin/sol",
  "ROUTINE": [
    { "TODO": "Read all status files in projects/" },
    {
      "WHEN": [
        { "when": "any project has overdue tasks",
          "then": [{ "TODO": "List overdue items at the top with due date" }] },
        { "when": "any deadline within 3 days",
          "then": [{ "TODO": "Add upcoming deadlines section" }] },
        { "else": [{ "TODO": "Add a note: no urgent items" }] }
      ]
    },
    { "TODO": "Write briefing to output/daily-briefing.md", "model": "smart" }
  ]
}
```

## Core instructions

| Instruction | Purpose |
|---|---|
| `TODO` | Natural language instruction — the agent interprets and executes |
| `IF` | Binary conditional — `then` / optional `else` |
| `WHEN` | Multi-branch conditional with optional shared `else` — use with mutually exclusive conditions |
| `REPEAT` | Loops: `while`, `until`, `for`, `foreach` |
| `RUN` | Verbatim shell command; use `{{placeholder}}` for dynamic parts |
| `SUB` / `CALL` | Define and invoke a subroutine in the shared context |
| `AGENT` / `SPAWN` | Define and invoke a named agent in a separate, bounded context |
| `DELEGATE` | Inline one-off sub-agent in a bounded context |
| `IMPORT` | Import `SUB` and `AGENT` definitions from an external file |
| `ONERROR` | Error handler, local or global |
| `HALT` | Immediately stop the process; optional message |
| `WAITUSERINPUT` | Pause and prompt the user for input before continuing |

The `model` field (`"fast"` / `"balanced"` / `"smart"`) and `role` field (natural language persona) are available on root, `SUB`, `AGENT`, and `DELEGATE`; inner scope overrides outer.

### Input/output contracts

`accepts` and `returns` describe what crosses a context boundary between agents — on the root process, `AGENT`, `SPAWN`, and `DELEGATE` (a `SUB` shares context and has none). A contract is either a natural-language string (open) or a structured map of fields with composable constraints (`required`, `anyof`, `number`, `json`, plus `desc`):

```json
"accepts": {
  "env":      { "anyof": ["coding", "staging", "production"], "required": true },
  "git_diff": { "required": true, "desc": "diff vs the merge-base with main" }
}
```

See [doc/io-contracts.md](doc/io-contracts.md) for the rationale.

### `TODO` vs `RUN`

- **`TODO`** — the agent interprets the instruction and decides how to fulfill it, including what commands to run and with what arguments.
- **`RUN`** — verbatim execution. What you write is what runs. Use `{{placeholder}}` only where the agent must fill in a value from context.

If you need the agent to figure out the full invocation, use `TODO`.

## Spec

Current line: **0.6** → [spec/sol-0.6.md](spec/sol-0.6.md) (patch version in the spec header / CHANGELOG)

## Why SOL

See [doc/DESIGN.md](doc/DESIGN.md) for the reasoning behind every design choice — including a comparison with AWS Strands Agent SOPs and Serverless Workflow.

## Does it actually work?

SOL has been measured, not just argued for. A pre-registered campaign put the same process
in front of six local models on a single 8 GB GPU and three hosted ones, in seven different
renderings — the SOL document with increasing amounts of surrounding explanation, and two
prose translations of it — and asked one question: *under what conditions is a process
written once actually executed?* 5,421 completed runs, hypotheses deposited before the first
run, and the git history to prove the plan preceded the results.

The short version: for a commercial model the bare document is enough and adding explanation
buys nothing. Below that frontier there is no single best form — the best rendering is a
property of the *(model, task)* pair, and it does not carry over to the next task, which is
why the answer is a bench rather than a table.

| where to look | what you get |
|---|---|
| [`articles/260603_bizanalysis_SOL-orchestrazione/`](articles/260603_bizanalysis_SOL-orchestrazione/) | Three long-form pieces (Italian): what SOL is for, what the numbers say, and fifteen ways a bench flatters whoever built it |
| [`report/analysis/FACTSHEET.md`](report/analysis/FACTSHEET.md) | Every fact with its N and its interval — generated, not written |
| [`report/analysis/`](report/analysis/) | The dataset and the notebook: recompute any number yourself |
| [`doc/experiment-minimum-context.md`](doc/experiment-minimum-context.md) | The pre-registered protocol, amendments included |
| [`doc/measures.md`](doc/measures.md) | What each number means and how it is computed |

The issue reports the fixtures run on come from a third-party dataset and are not
redistributed here: the fixtures ship dehydrated, with references, labels and hashes, and
[`tests/scripts/hydrate.py`](tests/scripts/hydrate.py) rebuilds them from the source.

## Examples

See [examples/](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
