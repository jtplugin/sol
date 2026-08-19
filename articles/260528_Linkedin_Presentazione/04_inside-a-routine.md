# Inside a SOL Routine: Steps, Branches, Loops, and Knowing When to Stop

The first three articles in this series introduced SOL, walked through a real process line by line, and showed how to generate one from a plain-language description. Along the way, two words kept appearing — `TODO` and `RUN` — and a handful of others flashed by in the examples: `WHEN`, `IF`, `REPEAT`, `ONERROR`, `HALT`.

This article assembles the full vocabulary of a single routine. Everything here lives *inside one `ROUTINE`* and runs in *one context* — the leaves that do the work, the control flow that arranges them, and the constructs that end things deliberately. What happens when you need more than one agent is the subject of the next article. This one is about everything you can express before you get there.

It's longer than the others on purpose: by the end, you'll have read every construct you need to write a complete, non-trivial process by hand.

---

## Part 1 — The two leaves: TODO and RUN

Every routine bottoms out in leaves: individual units of work. There are exactly two kinds, and choosing between them comes down to a single question.

**Is the method specified, or only the outcome?**

If you can write the exact command — a shell invocation, a script call, an API endpoint with its parameters — and it must run verbatim, that is a `RUN`. The agent does not interpret it; it passes it through.

```json
{ "RUN": "python3 scripts/compute_velocity.py projects/" }
```

If you know what you want but the method is best left to the agent's judgment, that is a `TODO`. The agent reads the outcome and decides how to reach it.

```json
{
  "TODO": "Write the section for {{project}} in reports/weekly-summary.md: overall status (green / yellow / red), the three most relevant points of the week, and priorities for next week",
  "model": "smart"
}
```

The first is a `RUN` not because it's *simple* but because the command is *given* — there is nothing to decide about how. The second is a `TODO` not because it's *complex* but because only the outcome is specified; the method (which files to read, what counts as "relevant", how to phrase priorities) is the agent's to determine.

Notice the `TODO` is precise. Precision isn't what makes something a `RUN` — a fully specified *method* is. The practical test: if the text could be pasted into a terminal and run, it belongs in a `RUN`; if it could only be handed to a colleague as a brief, it's a `TODO`.

Two mistakes follow directly from getting this backwards:

- **Describing a command as a TODO** — `{ "TODO": "Run scripts/compute_velocity.py on projects/" }` names a verbatim command but delegates a choice that doesn't exist. The agent might paraphrase the call or pass different arguments. You lose determinism for nothing.
- **Forcing an outcome into a RUN** — `{ "RUN": "summarise the projects and flag the red ones" }` isn't a command; no binary accepts that invocation. Putting it in a `RUN` field doesn't make it deterministic, it makes it unexecutable.

`TODO` does not mean "vague" and `RUN` does not mean "important". The hardest, highest-stakes synthesis step in a process is often a `TODO` — precise about *what*, deliberately open about *how*.

---

## Part 2 — Arranging the leaves: control flow

A list of leaves runs top to bottom. Real processes branch and repeat — and the temptation is to write that logic *inside* a `TODO`: "for each project, if it's red, add an alert, otherwise…". 

That's the one thing SOL asks you not to do. Decisions and loops are structural facts, and each has a construct. When they're buried in prose, the agent has to re-derive the structure on every run — which is exactly the ambiguity SOL exists to remove. Lift them out.

### IF — a binary decision

```json
{
  "IF": {
    "when": "every evaluated entry passes",
    "then": [{ "TODO": "Set the review status to pass" }],
    "else": [{ "TODO": "Set the review status to fail and list the failing entries with their rationale" }]
  }
}
```

One condition, a `then`, an optional `else`. Note what `when` contains: *"every evaluated entry passes"* — not a computable predicate but a judgment, written in natural language because that's where the interpretation belongs. Lifting it into an `IF` doesn't turn it into code; it makes the branch point **explicit and inspectable** instead of hidden in a sentence.

### WHEN — mutually exclusive cases

```json
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
    { "else": [{ "TODO": "Note that nothing is overdue or imminent" }] }
  ]
}
```

`WHEN` is for a list of cases. The rule of thumb: **use `WHEN` when the branches are mutually exclusive**, like a switch. When conditions can overlap and you want each evaluated independently, use a sequence of separate `IF` blocks instead — each one stands alone and there's no ambiguity about which "wins".

### REPEAT — iteration

`REPEAT` has four forms, one key each:

| Key | Semantics |
|---|---|
| `foreach` | once per element of a collection |
| `while` | as long as a condition holds |
| `until` | until a condition becomes true |
| `for` | a fixed number of times |

```json
{
  "REPEAT": {
    "foreach": "project in the projects/ directory",
    "ROUTINE": [
      {
        "TODO": "Write the section for {{project}} in reports/weekly-summary.md",
        "model": "smart"
      },
      {
        "IF": {
          "when": "{{project}} has velocity below 0.3 or critical tasks blocked over 5 days",
          "then": [{ "TODO": "Append an explicit alert note to {{project}}'s section" }]
        }
      }
    ]
  }
}
```

This fragment shows why explicit constructs matter. The `IF` here lives *inside* the `REPEAT`, so it fires once per project. The same process has a second, near-identical condition — "if **at least one** project is red, prepend an alert to the email" — that lives *outside* the loop, evaluated once over all projects. Same words, "if red", but different scope and different meaning. Structure makes that distinction visible; prose buries it.

> **Why not just a prompt with a loop?** Because "for each project, decide if it's red, and separately decide if any project is red" is precisely the kind of instruction an LLM reads inconsistently across runs. The `REPEAT`/`IF` structure pins down *where* each judgment happens. You keep the natural-language judgment inside `when` — that's SOL's whole point — but you stop leaving the *control flow* to chance.

---

## Part 3 — Knowing when to stop

Most steps just finish and the next one runs. But a process also needs deliberate ways to *end* — and SOL distinguishes them sharply, because stopping for an error, stopping because you're done, and stopping the entire world are three different intentions.

### RETURN — "I'm done here"

`RETURN` ends the current process and hands control back up — to the parent process, the call site, or the human at the top level. The agent itself keeps going; only *this* routine is finished. It's the ordinary completion exit, and it's how a process satisfies a `returns` contract (more on that in the next article).

```json
{ "RETURN": "Draft approved — handing the result back to the caller." }
```

> **A caveat before the next two constructs.** Remember that SOL is *non-prescriptive*: the agent interprets the document rather than executing a fixed transition table. There are strategies to make execution more predictable — they're the subject of a future article. Two constructs are especially exposed to interpretation: `HALT` (below) and `WAITUSERINPUT` (further down). How a given runtime honors "stop everything" or "pause and wait for a human" can vary, so test both in your specific implementation context before relying on them. There are robust workarounds that avoid the question entirely: for `HALT`, structure the process so it simply *concludes naturally* at the end of its routine instead of forcing a hard stop; for `WAITUSERINPUT`, *split the process into two* — one part before the human input and one after, with different triggers and different I/O.

### HALT — the red button

`HALT` stops the **entire** run, agent session included. Control is *not* handed back up; everything ends. It's intentional and controlled, but global — reserve it for genuinely unrecoverable states, not ordinary completion.

```json
{ "HALT": "Cannot write the summary without velocity data — fix the script and re-run." }
```

The difference between `RETURN` and `HALT` is the difference between "this subtask is over, carry on above" and "stop, there is nothing sensible to continue to".

### ONERROR — the error path

`ONERROR` defines what to do when a step fails. Attach it to a single instruction (local) or declare it at the root (a global fallback); local wins when both exist.

```json
{
  "RUN": "python3 scripts/compute_velocity.py projects/",
  "ONERROR": [
    { "TODO": "Report that velocity computation failed and identify the cause" },
    { "HALT": "Cannot write the summary without velocity data — fix the script and re-run." }
  ]
}
```

Two things worth noticing. First, `HALT` has no built-in condition — it just stops when reached. The *condition* lives in the `ONERROR` that triggers it: two constructs, each doing one job. Second, the choice of recovery is yours and it's expressive — here the failure is fatal, so it diagnoses and halts; elsewhere it might log and carry on:

```json
{
  "RUN": "main.py vault-scan {{repository}}",
  "ONERROR": [
    { "TODO": "Log the error line by line and continue" }
  ]
}
```

Same construct, opposite intent: one stops the run, the other absorbs the failure and keeps going. An error is not automatically fatal — `ONERROR` is where you say which it is.

### WAITUSERINPUT — the human gate

Sometimes the process needs a person: an approval, a decision, a piece of input only a human has.

```json
{ "WAITUSERINPUT": "Review the draft above and type APPROVE to continue, or describe changes:" }
```

This pauses execution and makes the human's reply available to the steps that follow. But it carries one firm condition: **use it only in genuinely interactive contexts.** In a batch or scheduled run there's no one to answer, and the process will simply hang. The right pattern there is to *split the process in two*: the first part does its work and ends normally with what it has; the second starts fresh, with the human's input as its initial context. The human gate becomes a boundary between two processes rather than a pause inside one.

---

## The full vocabulary of a routine

That's it — the complete toolkit for a single routine:

- **`TODO` / `RUN`** — the work, delegated by judgment or executed verbatim
- **`IF` / `WHEN` / `REPEAT`** — branching and iteration, lifted out of prose into structure
- **`RETURN` / `HALT`** — finishing deliberately, locally or globally
- **`ONERROR`** — the error path, fatal or recoverable as you decide
- **`WAITUSERINPUT`** — the human gate, for interactive contexts only

With these you can hand-write any process that runs in one place, in one context. Everything is inspectable: every branch point, every loop, every error path is a visible construct rather than an instruction the agent has to reconstruct each time.

What you *can't* yet express is work that needs to run somewhere else — a clean context, a reusable specialist, a one-off side task with its own boundary. That's delegation, and it's where SOL goes from a script to a system. It's the subject of the next article: `CALL`, `SPAWN`, and `DELEGATE`.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
