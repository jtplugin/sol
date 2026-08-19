# SOL Across Models: What to Feed, and What to Expect

> A SOL document is only ever as good as the environment that reads it. This document explains
> what kinds of SOL processes you can hand to a given model + execution environment *with
> confidence*, and where — and how — execution degrades when the environment is thinner.

---

## The variable that actually matters

It is tempting to ask *"can model X run SOL?"* That is the wrong question. SOL is plain JSON
embedded in Markdown; almost any instruction-following model can *read* it. What varies is
whether the model **plus its execution environment** can faithfully *carry out* what a given
SOL document demands.

So the real question is a **match** between two things:

1. **What the SOL document demands** — pure reasoning? shell execution? branching? genuine
   multi-agent isolation with model tiers?
2. **What the environment provides** — just a single text completion? a tool-calling loop? a
   full agentic harness with sub-agents, hooks, and permissions?

Hand a document to an environment that meets its demands and you get reliable execution. Hand
it to a thinner one and specific features silently degrade. The skill is knowing which is which.

---

## Axis 1 — SOL workload classes

SOL documents are not a monolith. They form a ladder of increasing demand on the environment:

| Class | Shape | Constructs typically used | Needs from environment |
|---|---|---|---|
| **W0 — Self-contained transform** | All input is in the prompt; produce a response | `TODO`, `IF`/`WHEN`, `returns` | Nothing but the model |
| **W1 — Linear tool process** | Read/run things on a real system, step by step | + `RUN`, `REPEAT` | A tool loop (shell/file tools) |
| **W2 — Branching workflow** | Conditionals and loops over real state | + nested `IF`/`WHEN`/`REPEAT`, `SUB`/`CALL` | A tool loop + reliable control-flow following |
| **W3 — Multi-agent orchestration** | Isolated agents, contracts, model tiers | + `AGENT`/`SPAWN`/`DELEGATE`, `model`, `accepts`/`returns` | A harness with real sub-agents + (for tiers) the predictability layers |

The jump that matters most is **W2 → W3**: everything up to W2 can be honored by a single
context. W3 asks for *bounded contexts that the caller does not share* and, often, *different
models per boundary* — and those are exactly the properties a bare model cannot provide (see
`predictability-strategies.md` for why model selection in particular needs an external layer).

---

## Axis 2 — Execution environments

| Env | What it is | What it can honor |
|---|---|---|
| **E0 — Bare API call** | One request to a base model (e.g. Qwen on Ollama), no tools, no loop | W0 only |
| **E1 — Tool loop** | Model + function/shell tools, run in a loop (small agent frameworks) | W0–W2 |
| **E2 — Agentic harness** | Claude Code & peers: tools, sub-agents, hooks, permissions, long runs | W0–W3 |
| **E2+ — Harness + predictability layers** | E2 plus the strategies in `predictability-strategies.md` | W3 *deterministically* (isolation + model tiers enforced) |

---

## The matching matrix

| | E0 bare API | E1 tool loop | E2 harness | E2+ |
|---|---|---|---|---|
| **W0 transform** | reliable | reliable | reliable | reliable |
| **W1 linear+RUN** | fails (no tools) | reliable | reliable | reliable |
| **W2 branching** | partial (reasoning only) | reliable | reliable | reliable |
| **W3 multi-agent** | collapses to role-play | weak isolation, tiers ignored | works (isolation real; tiers best-effort) | works + tiers enforced |

Read it as: **stay on or above the diagonal.** A W0 document is safe everywhere; a W3 document
is only safe on E2 and truly predictable on E2+.

---

## Concrete profiles

### Profile A — Qwen on Ollama, single API call (E0)

This is the "no harness at all" case, and it is more useful than it looks. With a single
completion you can reliably run a **W0 self-contained transform**, provided you respect three
rules:

1. **Everything is in the prompt.** The SOL document *and* the data it operates on are both in
   the request. There is no file system to read, no tool to call.
2. **Leaves are pure reasoning.** Use `TODO` for classify / extract / summarize / transform.
   Avoid `RUN` (no shell), avoid real `SPAWN` (no sub-agent mechanism — it would just be
   role-played in the same context), avoid `WAITUSERINPUT` (non-interactive).
3. **The output contract is explicit.** A structured `returns` tells the model exactly what
   shape to emit, which is what makes the response machine-usable.

This is exactly your "feed it an `.md` with a SOL block plus a document/dataset, and let the
SOL say what to do and what to return" intuition — and it works well, because it stays inside
W0/E0.

**Example document handed to the model:**

````markdown
# Task

Execute the SOL process below on the data in the "Input data" section.
Return only the JSON described by the process's `returns`.

## Process

```json
{
  "name": "triage-feedback",
  "version": "1.0",
  "description": "Classify each feedback item and extract the actionable request, if any.",
  "returns": {
    "items": { "json": true, "required": true,
               "desc": "list of {id, sentiment in [positive,neutral,negative], category, action_request|null}" }
  },
  "ROUTINE": [
    { "TODO": "For each row in the input data, read the free-text comment." },
    {
      "WHEN": [
        { "when": "the comment reports a bug or broken behavior",
          "then": [{ "TODO": "category = 'bug'; extract the action_request as a one-line fix summary" }] },
        { "when": "the comment asks for a new capability",
          "then": [{ "TODO": "category = 'feature'; action_request = the requested capability" }] },
        { "else": [{ "TODO": "category = 'other'; action_request = null" }] }
      ]
    },
    { "TODO": "Assign sentiment to each item from its tone." },
    { "TODO": "Emit the items array exactly per the returns contract." }
  ]
}
```

## Input data

| id | comment |
|----|---------|
| 1  | "Login throws a 500 after the latest update."          |
| 2  | "Would love a dark mode."                              |
| 3  | "Thanks, the new dashboard is great."                  |
````

The model reads the whole thing, follows the branches, and returns the contracted JSON. No
harness required. Note what we did *not* use: no `RUN`, no `SPAWN`, no `model` tiers — those
would be noise here, or worse, silently unmet.

### Profile B — Model with a tool loop (E1)

Add a function-calling/shell loop (a thin agent framework, an SDK harness) and you climb to
**W1–W2**: `RUN` can execute because there is a shell tool; `REPEAT`/`IF`/`WHEN` over real
state become dependable because the loop lets the model act, observe, and continue;
single-context `SUB`/`CALL` works because it is all one context anyway. What is still shaky is
**W3**: a `SPAWN` here tends to become "the same model role-playing the agent in the same
context" — the contract is *described* but isolation and model tiers are not really enforced.

### Profile C — Full agentic harness (E2 / E2+)

A harness like Claude Code is the first environment where **W3 is genuinely safe**: sub-agents
run in their own context, so `SPAWN`/`AGENT` isolation is real; `accepts`/`returns` are
honored across a true boundary; long multi-phase runs, hooks, and permissions are available.
The one residual is **model tiers**: by default the harness may not map `model: "smart"` onto a
specific stronger model automatically. That last mile is what the **predictability strategies**
(native sub-agents with `model:` frontmatter, a spawn helper, relaunch-per-phase) close — that
is the step from E2 to E2+. See `predictability-strategies.md`.

---

## How execution degrades (know your failure modes)

When a document outruns its environment, the failure is usually **silent** — the model does
*something* plausible rather than erroring. The common degradations:

- **`SPAWN` on E0/E1** → in-context role-play. The "agent" sees the caller's context; the
  `accepts`/`returns` boundary is cosmetic; isolation is fictional.
- **`model` tiers below E2+** → ignored. Every step runs on the one model in play. A
  `model: "smart"` leaf gets the base model's reasoning, no more.
- **`RUN` on E0** → cannot execute. With no shell tool the model may *describe* the command or,
  worse, *hallucinate* its output. Only use `RUN` where a tool loop exists.
- **`WAITUSERINPUT` non-interactively** → undefined. The model either invents an answer or
  stalls. Decompose into separate invocations instead (see `why-sol-works.md`).

The defense is not to fight the environment but to **author to its class**: if you are
targeting E0, write a W0 document.

---

## Practical guidance: authoring for a target environment

- **Targeting a bare API model (E0):** keep it W0. Inline the data, make every leaf a `TODO`
  the model can satisfy by reasoning alone, and pin the output with a structured `returns`. No
  `RUN`, no `SPAWN`, no tiers, no waits.
- **Targeting a tool loop (E1):** W1–W2 are fair game. Use `RUN` for the deterministic parts,
  keep delegation to `SUB`/`CALL` (shared context), and treat any `SPAWN` as best-effort —
  prefer not to depend on real isolation.
- **Targeting a harness (E2):** W3 is available. Draw real contracts on every `SPAWN`; the
  contract is what makes isolation meaningful and is itself a pressure toward it. If you need
  *specific* models per boundary, move to E2+ via `predictability-strategies.md`.
- **Always:** add a short execution-directive block above the SOL fence telling the reader how
  to treat the constructs (L1 in `predictability-strategies.md`). It costs nothing and raises
  the floor on any environment.

---

## The takeaway

SOL's portability is real but conditional: the *same* document means the same *intent*
everywhere, but the *realized behavior* depends on the environment. Match the workload class to
the environment class, author down to your target when the environment is thin, and reserve the
heavy constructs (`SPAWN`, `model` tiers, long orchestration) for environments that can actually
honor them.

---

## See also

- `SOL-and-harness.md` — which engines expose enough surface to host SOL well.
- `predictability-strategies.md` — closing the last mile (isolation, model tiers) on a harness.
- `why-sol-works.md` — why natural-language leaves trade determinism for expressiveness.
- `testing-sol.md` — measuring fidelity per (workload × environment × model) configuration.
