# When to write a process in SOL, and when in prose

A short rationale, and the rule it produced. It also records *why this very skill*
(`SKILL.md`) is written as prose rather than as a SOL script.

---

## The principle

> **The format must follow where the complexity lives.**

SOL exists to externalize the complexity of **control flow** — decisions, branches,
iterations, error paths, agent orchestration — so the agent *executes* a structure instead of
re-deriving it from prose every run. That is what SOL buys you, and it is a lot when the
process actually has that structure.

When a process's complexity instead lives in **judgment and criteria** (what counts as good,
what to weigh, how to decide) and its control flow is a thin, mostly-linear pipeline, SOL adds
ceremony without adding executable structure. There, prose is the better representation: the
value was never in the skeleton, it was in the guidance.

| The hard part is… | Best format |
|---|---|
| Control flow / orchestration: dense or nested branching, loops over data, `SPAWN`, contracts | **SOL** |
| Judgment / criteria, with a thin near-linear flow and inherently non-deterministic steps | **prose** |
| Repeatable execution of a fixed structure | **SOL** |

---

## The format-fit detector (a happy side effect of the linter)

`scripts/sol-lint.py` was built to check SOL quality. It turns out to also detect when
something *should not be SOL at all*:

> If a script lints with **only** `todo-long` and `buried-flow` warnings, spread over a flat,
> near-linear sequence with almost no real constructs, it is not bad SOL — it is **prose
> written in SOL**. Rewrite it in prose.

A healthy SOL script shows *structure* the linter can check (loops with real collections,
mutually-exclusive `WHEN`s, contracts on `AGENT`s). A methodology shows a wall of long
declarative leaves. The fingerprints are different, and the linter makes them visible.

---

## The self-reference hazard (why this skill is prose)

This skill is a meta-document: it is a methodology *about writing SOL*. Every step
necessarily talks about `IF`, `WHEN`, `foreach`, contracts. Put that text inside a SOL `TODO`
and you create a **category confusion**: is "lift the control flow into the matching
construct" a piece of *flow to lift*, or *instruction about lifting*? When the same skill was
authored in SOL, the linter flagged ~40 `buried-flow`/`todo-long` warnings with zero
structural errors — the empirical signature above. The control flow was fine (a sequence of
passes, one clarify `IF`, one diagram `WHEN`, one lint `REPEAT`); the content was a judgment
methodology that read as buried flow because it *names constructs as its subject*.

Prose removes the hazard at the root: in prose, "lift control flow into a construct" is
unambiguously an instruction. So the skill body is prose; the heavy discipline lives in
`authoring.md`, `contracts.md`, `borderline-cases.md`, and `reference.md`, cited as binding.

This decision is **specific to meta/methodology processes** — judgment pipelines with thin
control flow. It is not a general retreat from SOL.

---

## Two things this is NOT

**It is NOT a reason to refuse SOL.** When the user asks for a SOL script, produce a SOL
script. If SOL looks like a poor fit for what they described (a pure judgment checklist, a
near-linear methodology), say so in one line and offer prose as an alternative — then do what
they decide. Default to honoring the request; advise, do not gatekeep.

**It is NOT a knock on JSON-inside-Markdown.** A SOL `json` fence hosted in a Markdown
document is an *excellent* pattern, not an antipattern. It lets one document hold, close
together yet cleanly distinct:

- the **flow logic** (the SOL fence),
- the **declarative knowledge** (criteria, specs, templates as labelled prose sections),
- the **context and data** (labelled JSON fences / tables the `foreach` walks),

while the surrounding prose states intent and files down nuance. Co-locating these — near
enough to read as one artifact, separated enough that each keeps its own nature — is exactly
the shape most good SOL scripts should take. The skill being prose is about *this skill's*
content being a methodology, not about the json-in-md container being wrong. It is right.
