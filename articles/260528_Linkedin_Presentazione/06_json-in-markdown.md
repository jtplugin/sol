# SOL inside Markdown: why the file format is not an afterthought

So far this series has talked about SOL as if it were just JSON: leaves, control flow, delegation, contracts. All true, and all independent of where the JSON actually lives. But in practice, a SOL document is rarely a bare `.json` file. It's a JSON block embedded inside a Markdown document — and that choice is not packaging. It's what makes several things possible that a standalone JSON file couldn't give you.

---

## The pattern

A SOL file looks like this:

```markdown
# Process: weekly-closure

**Trigger:** scheduled, every Friday 18:00.
**Owner:** ops team.

## Source tables

| env        | endpoint                      |
|------------|--------------------------------|
| staging    | https://stg.api.internal/close |
| production | https://prod.api.internal/close |

## Process

​```json
{
  "name": "weekly-closure",
  "ROUTINE": [
    {
      "REPEAT": {
        "foreach": "row in Source tables",
        "ROUTINE": [
          { "RUN": "curl -X POST {{endpoint}}/close" },
          { "TODO": "Record the response status against {{env}}" }
        ]
      }
    },
    { "TODO": "Summarize successes and failures by environment" }
  ]
}
​```

## Notes

- `staging` failures are non-blocking; `production` failures halt the run.
```

Prose around the block, a table above it, the executable JSON in the middle. Nothing exotic — it's the same Markdown anyone already writes for documentation. The only difference is that part of it is also the program.

---

## What this single fact enables

**Documentation and code stop drifting apart.** There's no separate spec file that describes what the JSON does and goes stale the week after someone edits the `ROUTINE`. The trigger, the owner, the caveats — they live in the same file, next to the steps they describe. Read the file once and you have both views.

**Configuration tables become first-class inputs.** The `foreach` above doesn't need an inline array buried in the JSON; it can point at a Markdown table sitting right above it, with one row per environment. Adding a new environment is editing a table, not touching the routine. The agent reads the document as a whole — table and JSON together — so the reference resolves naturally.

**Diffs stay readable.** Change a TODO's wording and the diff shows one line. Add an environment and the diff shows one row. Compare that to a single-purpose binary format or a heavily nested YAML where a one-line conceptual change can ripple through indentation. A reviewer — human or agent — sees exactly what moved.

**Skills become self-explanatory.** The previous article in this series already showed this pattern under a different name: a Claude Code skill with a Markdown wrapper (trigger, prerequisites, notes) and a SOL block carrying the executable logic. That's not a special case bolted onto SOL — it's the same JSON-in-Markdown pattern, just applied to a skill file instead of a standalone process.

**Visualization comes for free.** Because the JSON is a self-contained block, tooling can extract it and project it onto something else — a Mermaid flowchart, a draw.io diagram — without touching the surrounding prose. SOL's own tooling does exactly this (`sol2mermaid.py`, `sol2drawio.py`): every construct maps onto a standard flowchart primitive, so a process can be *read* by an agent and *seen* by a human from the same source, with no second file to keep in sync.

---

## Generated, not just written

Everything above describes a file someone authors by hand. The same pattern holds, with no extra machinery, when the file is produced on the fly.

Markdown is trivial to generate dynamically: pull data from a database, an API response, a config file, the output of a previous step — drop it into headings, tables, prose — and append the SOL block that operates on it. The result is one document that carries both the context and the instructions for acting on it, assembled in a single pass, with nothing to keep in sync afterwards because there's no "afterwards" — context and process are generated together.

This is what makes the pattern fit naturally as a target for tools, scripts, or other agents that need to brief an agent with something more structured than a one-line prompt: a detailed spec assembled from live data, a handoff document with the exact rows a `foreach` should walk, a generated report that ends in "and here's what to do about it." Nothing about this requires SOL-specific generation logic — it's the same templating anyone already uses to produce a Markdown report, with a JSON block appended at the end.

---

## Why this couldn't be "just JSON"

None of this depends on a feature of JSON itself — it depends on JSON living *inside* something that already has a place for prose, tables, and structure: Markdown. A bare `.json` file has no comments, no headings, no tables, nothing to attach a rationale to. You'd end up maintaining a second file for the why, and the two files would drift the moment one of them got edited without the other. Embedding the JSON in the Markdown collapses that into one file, one diff, one read.

This is also why the pattern costs nothing extra to adopt: any tool that already parses fenced code blocks — a Markdown renderer, a static site generator, a vault tool, a Claude Code skill loader — gets the SOL block for free. SOL doesn't ask for a custom file extension or a bespoke parser. It asks to be a code block in a format everyone already reads.

---

## What's left

The vocabulary, the delegation model, and now the file shape are all on the table. One thing remains: this is an open source project, MIT licensed, and the series ends by saying plainly what that means in practice — what's there, what's still missing, and how to contribute.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
