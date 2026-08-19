# A SOL Process, Live: Reading Orchestration Line by Line

In the first article I made a claim that deserves a demonstration: with SOL, the agent reads a minimal JSON document and executes it directly — no SDK, no orchestration engine, no runtime to install. Claims are cheap. Let's look at a real process and follow what actually happens when an agent reads it.

## The scenario, in one sentence

Every morning, before starting work, I want a briefing that reads the status of my projects, surfaces what's overdue or approaching a deadline, and writes me a summary.

This is the kind of thing you'd hand to a capable colleague in a sentence. The question is how little you have to write to hand it to an agent instead. Here is the entire process:

```json
{
  "name": "daily-briefing",
  "version": "1.0",
  "description": "Generate a daily briefing from project status files. Run each morning before starting work.",
  "ROUTINE": [
    { "TODO": "Read all status files in projects/" },
    {
      "WHEN": [
        {
          "when": "any project has overdue tasks",
          "then": [{ "TODO": "List overdue items at the top with owner and original due date" }]
        },
        {
          "when": "any project has a deadline within 3 days",
          "then": [{ "TODO": "Add an upcoming deadlines section" }]
        },
        {
          "when": "any project has been inactive for more than 7 days",
          "then": [{ "TODO": "Flag stale projects for review" }]
        }
      ]
    },
    { "TODO": "Summarize progress since yesterday for each active project", "model": "fast" },
    { "TODO": "Write the final briefing to output/daily-briefing.md", "model": "smart" }
  ]
}
```

That's all of it. No imports, no class definitions, no glue code. The point of showing the whole thing is precisely that there is nothing to hide off-screen.

## Reading it the way the agent does

**The first step is an instruction, not a command.**

```json
{ "TODO": "Read all status files in projects/" }
```

Notice what isn't here: no file glob, no parser choice, no format assumption. A `TODO` states the desired outcome and lets the agent decide *how* — which files count as status files, how to read them, what to do if one is malformed. You're delegating method, not abdicating control.

**The conditions are judgments, not predicates.**

```json
{ "when": "any project has overdue tasks", "then": [ ... ] }
```

"Any project has overdue tasks" is not something a traditional workflow engine could evaluate — there's no computable predicate behind it. But it's exactly the kind of thing a capable model reads and resolves correctly against the actual content of those files. The branch conditions live in natural language because that's where the interpretation belongs.

**The model tier expresses intent, not identity.**

```json
{ "TODO": "Summarize progress...", "model": "fast" }
{ "TODO": "Write the final briefing...", "model": "smart" }
```

The mechanical summarization runs on `fast`; the final write-up — where the quality of reasoning actually shows — runs on `smart`. You're not naming a model that will be obsolete next quarter. You're declaring how much thinking each step deserves and letting the executing agent map that to whatever it has.

## What isn't in the file

This is the part worth dwelling on. There is no state graph. No registered functions. No runtime engine to interpret transitions. No explicit sequencing or parallelism declarations. The process says *what* should happen and *under what conditions*; everything about *how to run it* — read order, what can overlap, how to recover — is left to the agent, which reads the whole document before acting and reasons about it as a unit.

That inversion is the entire idea. Other formats describe a machine for an engine to drive. SOL describes intent for an agent to fulfill.

## The honest caveat

This expressiveness has a price, and it's worth stating plainly: two runs of the same process can differ, because the agent exercises judgment rather than executing a fixed transition table. For the steps where that's unacceptable — invoke exactly this command, run exactly this suite — SOL has a verbatim counterpart to `TODO`. That's `RUN`, and it's the subject of the next article.

## One level up

The briefing above is deliberately simple. Real processes layer in literal commands, loops, subroutines, and error handling — like this fragment from a heavier example in the repo:

```json
{
  "REPEAT": {
    "foreach": "entry in queue (max 5, sorted by detected desc)",
    "ROUTINE": [{ "CALL": "process-entry" }]
  }
}
```

Same philosophy, more structure. We'll get there.

The runnable examples live in [`examples/`](https://github.com/jtplugin/sol/tree/main/examples) — clone the repo and read them the way the agent would.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
