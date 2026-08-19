# From Prose to Process: Writing SOL with the Translation Skill

In the first two articles I described what SOL is and walked through a real process line by line. The natural question that follows is: how do you write one from scratch?

The honest answer is that you don't have to. There is a skill for that.

## The starting point: a paragraph

You begin where you'd begin with any colleague — a description of what you want done.

> Every Friday afternoon, before 17:00, do a weekly closure of the active projects.
>
> Start by reading all the status files in `projects/` — each project has a `status.md` with the week's activity. Then run `scripts/compute_velocity.py`, passing `projects/` as an argument; the script calculates weekly velocity (closed tasks / open tasks) and writes the results to `reports/velocity.json`.
>
> Based on what you read and the velocity data, write a weekly summary to `reports/weekly-summary.md`. Each project gets a section: overall status (green / yellow / red), the three most relevant points of the week, and priorities for next week. If a project is red — velocity below 0.3 or critical tasks blocked for more than 5 days — add an explicit alert note.
>
> Then update the todo list: move all tasks that appear as closed in the status files to the "Completati" section of `todo.md`, and add the priorities you just identified to the top of "Questa settimana".
>
> Finally, send an email to `team@company.com` with subject `Weekly Summary — [today's date]` and body equal to the summary you just wrote. Before sending, if at least one project is red, prepend a bold alert line with the names of the critical projects.

No JSON, no syntax, no field names. Just intent.

You drop this into Claude Code with `/sol`, paste the description, and the skill goes to work.

## What makes this more than a formatter

A formatter takes structure in and emits structure out. The skill does something different: it reads for meaning.

It identifies that `scripts/compute_velocity.py projects/` is a verbatim command — that becomes a `RUN`, not a `TODO`. A `TODO` would ask the agent to decide how to compute velocity; a `RUN` says: execute exactly this. It also notices that if the script fails, the summary cannot be written — so it wraps the `RUN` in an `ONERROR` that reports the failure and halts the run cleanly.

It identifies that "for each project" is a loop — that becomes a `REPEAT`. It sees two separate conditions in the description: one per-project ("if this project is red, add an alert note") and one global ("if at least one project is red, prepend a line to the email"). It generates two distinct `IF` blocks in the right places — one inside the loop, one outside.

It also notices a step the description only implied: before you can conditionally prepend an alert to the email, you need to have an email body to prepend to. The skill adds an explicit "prepare email body" step that isn't literally in the prose, because without it the conditional has nothing to operate on.

Rather than guess on any of this, the skill surfaces genuine ambiguities as numbered questions before writing a single file. You answer, then it generates.

## The output, read the way an agent reads it

Here is the file the skill produces — `examples/weekly-closure.json`:

```json
{
  "name": "weekly-closure",
  "version": "1.0",
  "description": "Weekly project closure — run every Friday before 17:00. Reads all project status files, computes velocity, writes a per-project summary report, updates the todo list, and sends the summary by email to the team.",
  "role": "Project manager performing the weekly team reporting cycle.",
  "ROUTINE": [
    { "TODO": "Read all status.md files in projects/", "model": "fast" },
    {
      "RUN": "python3 scripts/compute_velocity.py projects/",
      "ONERROR": [
        { "TODO": "Report that velocity computation failed and identify the cause" },
        { "HALT": "Cannot write the summary without velocity data — fix scripts/compute_velocity.py and re-run." }
      ]
    },
    { "TODO": "Read reports/velocity.json", "model": "fast" },
    {
      "REPEAT": {
        "foreach": "project in the projects/ directory",
        "ROUTINE": [
          {
            "TODO": "Write the section for {{project}} in reports/weekly-summary.md: overall status (green / yellow / red), the three most relevant points of the week, and priorities for next week",
            "model": "smart"
          },
          {
            "IF": {
              "when": "{{project}} has velocity below 0.3 or has critical tasks blocked for more than 5 days",
              "then": [
                { "TODO": "Append an explicit alert note to {{project}}'s section in reports/weekly-summary.md" }
              ]
            }
          }
        ]
      }
    },
    { "TODO": "In todo.md, move all tasks that appear as closed in the status files to the Completati section", "model": "fast" },
    { "TODO": "In todo.md, add the priorities identified in the summary to the top of the Questa settimana section", "model": "fast" },
    { "TODO": "Prepare the email body from the content of reports/weekly-summary.md", "model": "fast" },
    {
      "IF": {
        "when": "at least one project has red status",
        "then": [
          { "TODO": "Prepend a bold alert line to the email body listing the names of all red-status projects" }
        ]
      }
    },
    {
      "TODO": "Send an email to team@company.com with subject 'Weekly Summary — {{today}}' and body equal to the prepared email body",
      "ONERROR": [
        { "TODO": "Save the prepared email body to reports/weekly-email-draft.md and report that the email could not be sent" }
      ]
    }
  ]
}
```

A few things worth noting.

**`RUN` vs `TODO` for the Python script.** The description names an exact command: `scripts/compute_velocity.py projects/`. That's a `RUN` — passed verbatim, no interpretation. If the description had said "calculate velocity for all projects", that would be a `TODO`: the agent would decide how. The distinction matters because `RUN` gives you a deterministic, auditable step; `TODO` delegates method to the agent. The skill applies this choice automatically based on whether the command is specified or only the outcome.

**`ONERROR` with `HALT` inside.** The velocity script can fail. Without its output, the summary would be incomplete — so the correct behavior is to stop cleanly, not silently skip. The `ONERROR` block first diagnoses (a `TODO` that identifies the cause), then halts with a readable message. `HALT` has no built-in predicate; it simply stops everything when reached. The condition lives in the `ONERROR` that triggers it — two constructs, each doing one thing.

**Two `IF` blocks, in different scopes.** The per-project alert ("if this project is red") lives inside the `REPEAT`, so it fires once per project. The email alert ("if at least one project is red") lives outside the loop, after all sections are written. The skill places each condition at the right level — not because you specified "inside vs. outside the loop" but because it read what each condition is evaluating.

**Model tiers are functional, not aesthetic.** Reading files and preparing the email body are I/O operations: `fast`. Writing the per-project summary sections — status assessment, selecting the three most relevant points, articulating next-week priorities — is synthesis: `smart`. You're not naming a model that will be obsolete next quarter; you're declaring how much reasoning each step deserves and letting the executing agent map that to whatever it has.

## What the skill also decides

Beyond the instructions themselves, the skill resolves two things you didn't have to think about.

**File structure.** A process this size — nine top-level nodes, no reusable agents — stays in a single file. If your description had contained two distinct agent behaviors invoked from a shared orchestrator, the skill would have split them: one file per agent under `agents/`, a main entry point importing them via `IMPORT`.

**Diagrams.** After writing the JSON, the skill asks if you want a visual. You can get a Mermaid flowchart (`.mmd`) — useful if you're on GitHub, VS Code, or Obsidian — or a draw.io file (`.drawio`) if you live in Confluence or Notion. Both use the same semantic color scheme: blue for `TODO`, green for `RUN`, yellow for control flow, red for errors. The same process reads consistently across both formats, and both are regeneratable from the JSON at any time.

## What this means in practice

The JSON the skill produces is immediately runnable. An agent can read it and execute it without any post-editing. But it's also inspectable and modifiable — you can read every field, change a model tier, add a step, restructure a branch. It's not a black box that generated something you can't reason about.

The skill lowers the barrier to getting started. It doesn't lower the level of control you have once you're there.

The full example lives at [`examples/weekly-closure.json`](https://github.com/jtplugin/sol/blob/main/examples/weekly-closure.json) in the repository.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
