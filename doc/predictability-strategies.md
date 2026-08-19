# Predictability Strategies for SOL

> SOL is non-prescriptive by design. When you need the *intent* of a SOL process to be
> reliably *realized* at runtime, you do not change the language — you inject predictability
> at a chosen layer. This document maps those layers and the concrete strategies available
> at each, with their strength, cost, and trade-offs.

---

## The premise: SOL cannot force anything

The first line of the spec is not a slogan, it is a constraint:

> *No external runtime is required — the agent is the runtime.* (`spec/sol-0.6.md`)

SOL describes a process; an agent reads it and decides how to honor it. There is no parser
that compels a branch to be taken, no scheduler that guarantees a `SPAWN` becomes an isolated
session, no type checker that enforces a contract. The spec says so explicitly: contracts are
*"honored by the agent's understanding, not by a runtime type checker"*, and `model` is *"a
hint, not an imperative."*

This is a deliberate stance, not a gap. It is what lets a `TODO` say *"identify the most
likely root cause"* — something no deterministic engine could evaluate. The price is that
**nothing in the language can force an agent to behave the way you want.**

So the question is never *"how do I make SOL prescriptive?"* It is: *"if I need a particular
behavior to be predictable, at what layer do I inject that predictability, and what does it
cost me?"*

---

## What "predictability" means here

We are not asking for byte-identical outputs (natural-language leaves make that impossible;
see `why-sol-works.md`). We are asking that the **declared structure is actually realized**:

- a `SPAWN` runs in a genuinely isolated context, not as in-context role-play;
- a `model: "smart"` boundary actually runs on a stronger model;
- a contract (`accepts` / `returns`) is actually respected at the boundary;
- a branch, a loop, an `ONERROR` actually fires as written;
- a `WAITUSERINPUT` actually pauses for a human and resumes with their answer — rather than degrading to a stop because the context turned out to be non-interactive.

These are *execution-fidelity* properties. The language expresses them; some external layer
has to make them reliable.

---

## A distinction that decides what is forceable

Not all SOL intents are equally enforceable, and the reason is instructive.

- **Context isolation is entailed by the contract.** SOL says an `AGENT` *"receives only what
  `SPAWN` passes via `with`, and returns only what `returns` describes. It does not share the
  calling agent's context."* This is a statement about *information flow*. Any layer that
  faithfully enforces *"the callee sees only `with`"* is **compelled** to create a fresh
  context — there is no other way to guarantee the callee cannot see the caller's state. So
  isolation can be pressured into existence simply by taking the contract seriously.

- **Model choice is entailed by nothing.** There is no information-flow property that requires
  a different model. That is precisely why `model` is *only* a hint: it is orthogonal to the
  contract. Forcing a specific model therefore always requires a layer *outside* the agent's
  own judgment.

Practical consequence: **you can pressure isolation from inside SOL's own discipline; you
cannot pressure model selection without an external resolver.** Keep this asymmetry in mind
when choosing a strategy.

---

## The layering principle

Every strategy below injects predictability at a different layer. The deeper you go, the more
authority moves *out* of the agent and *into* a deterministic executor — buying determinism
at the cost of portability and engineering effort.

| Layer | Where predictability is injected | Strength | Portability | Effort |
|---|---|---|---|---|
| **L1 — Linguistic** | Inside the model's reasoning (prompt) | Low | High (any model) | Trivial |
| **L2 — Harness** | Platform features (Claude Code, etc.) | Medium–High | Harness-specific | Low–Medium |
| **L3 — External runtime** | A deterministic executor beside SOL | High | Portable across models | Medium–High |
| **L4 — Foreign orchestrator** | SOL becomes node-spec only | Highest | Tool-specific | High |
| **L0 — Observability** | *(orthogonal)* measure, don't force | n/a | High | Low–Medium |

The right choice is the **shallowest layer that gives you the determinism you actually need.**
Over-engineering predictability is as wasteful as lacking it.

---

## L1 — Linguistic: steer from inside the prompt

**What it is.** The Markdown wrapper around the SOL JSON (or a header block) explicitly
instructs the executing agent how to treat the constructs — for example: *"When you reach a
`SPAWN`, open a fresh sub-agent with the declared `model`; do not role-play it inline. Honor
every `accepts` field literally."*

**Strength.** Low. It raises the probability the agent behaves as intended, but it is still a
request to a non-deterministic reader. A capable model with a good harness will often comply;
a weak one will not.

**Cost / portability.** Trivial to write, works on any model, no infrastructure. The cheapest
lever and the right first step — but never a guarantee.

**Example.** A directive block placed above the SOL fence:

```markdown
## Execution directives (read before executing the process below)

- Treat every `SPAWN` as a real context boundary: start a clean sub-agent that sees ONLY the
  `with` payload. Do not carry this conversation's context into it.
- Where a `SPAWN` or `AGENT` declares `model`, use a model of that tier for that sub-agent.
- Validate each `accepts` field at the start of the agent; on violation, follow the contract's
  error path rather than improvising.
```

---

## L2 — Harness: use the platform's own machinery

The harness (Claude Code, Cursor, etc.) is already the de-facto runtime for SOL. It is the
most leveraged place to add predictability without leaving the agentic model. See
`SOL-and-harness.md` for how SOL maps onto each engine; here are the specific levers.

### L2a — Harness configuration

**What it is.** Configure the harness to make agentic behavior more deterministic — permission
modes, tool availability, settings that nudge or constrain when sub-agents and tools are used.

**Strength / cost.** Medium; low effort. Bounded by what the harness exposes.

### L2b — Native sub-agents (the strongest L2 lever for *model*)

**What it is.** Register each SOL `AGENT` as a first-class harness sub-agent. In Claude Code
this is a file under `.claude/agents/` with a `model:` frontmatter and a `description`. When
the session reaches the corresponding `SPAWN`, the harness's own sub-agent mechanism opens it
*on the model declared in the frontmatter*.

**Why it matters.** This is the cleanest way to make `model` real *without* an external
runtime: the SOL tier (`smart`/`balanced`/`fast`) is mapped onto a mechanism the harness
honors natively. It also gives genuine context isolation for free, since native sub-agents run
in their own context.

**Strength / cost.** High for both isolation and model; low–medium effort (you maintain a thin
agent file per SOL `AGENT`, mirroring the agent's routine).

**Example.**

```markdown
---
name: specialist
model: opus
description: Produce the spec and test plan from a card brief. Use in the SPEC phase.
---

(body = the AGENT's SOL routine, or a pointer to it)
```

### L2c — Hooks

**What it is.** Lifecycle hooks (`SessionStart`, `PreToolCall`, `Stop`, …) let you attach a
deterministic action to an event rather than asking the model to perform it. A hook can fire a
script when a particular marker appears, enforce a setup sequence, or gate a transition.

**Strength / cost.** Medium; low effort. You do not *ask* the agent — you *bind* behavior to
an event. Limited to what the hook lifecycle can observe and trigger.

### L2d — Spawning as an MCP tool

**What it is.** Expose "spawn an agent of type X on tier Y" as an MCP tool the model is
strongly nudged to call. It sits between L1 (asking) and L3 (an external executor): the
mechanism is deterministic once invoked, but invocation still depends on the model choosing the
tool.

**Strength / cost.** Medium–High; medium effort.

---

## L3 — External deterministic runtime

Here predictability stops depending on the agent's goodwill. A deterministic executor sits
beside SOL and *materializes* the constructs. This is the only family that can force **model**
selection, because (per the asymmetry above) model is not contract-entailed.

### L3a — A spawn helper (`SPAWN` becomes `RUN`)

**What it is.** A small script (e.g. `spawn.py`) that, given an agent name and a `with`
payload, resolves the tier to a concrete model, launches an isolated model session
(`some-cli --model <X> -p …`), validates the return against the contract, and prints the
compact signal back. The dispatching SOL step becomes a `RUN` of that helper instead of an
in-context `SPAWN`.

**Strength.** High and deterministic: the parent no longer decides the model — the helper does,
from the declared tier. The orchestrating session can even be a *weak* model, because choosing
and escalating the model is no longer its job.

**Cost / portability.** Medium–high engineering. It is also a partial departure from "the agent
is the runtime": the boundary is now executed, not interpreted. Portable across model providers
(the helper picks the CLI/model).

**Example (the dispatch step in SOL).**

```json
{ "RUN": "python spawn.py --agent specialist --model smart --with '<payload>'" }
```

### L3b — Hybrid: prompt directive + helper

**What it is.** Keep the `SPAWN` construct in the SOL for clarity, and add an L1 directive that
says *"to execute a `SPAWN`, invoke `spawn.py --agent <name> --model <tier> …`."* The language
stays clean; the determinism comes from the helper the agent is told to call.

**Strength / cost.** High once the agent follows the directive; lower engineering than fully
rewriting every dispatch to `RUN`. The residual risk is the L1 part (the agent must obey the
directive).

### L3c — Compilation / transpilation

**What it is.** Treat SOL as an *authoring* layer and **compile** it into the target's native,
deterministic form ahead of time: `.claude/agents` + a driver, a graph for a foreign
orchestrator, or a plain script of model invocations. Nothing is interpreted at runtime; the
orchestration is "baked."

**Strength.** High — predictability comes from precompiled structure, not runtime judgment.

**Cost.** Medium–high (you build and maintain a compiler per target). SOL remains the single
source of truth, which is the appeal.

### L3d — Orchestration by relaunch (align phases to session boundaries)

**What it is.** If a single session cannot change model mid-flight, make each *model regime* its
own session, launched from the outside. A thin launcher runs phase 1 on one model, reads the
result, then launches phase 2 on another. The natural session boundary becomes the model-switch
point.

**Why it matters.** You often have this for free: a step-by-step launcher (one invocation per
phase) already gives clean isolation and per-phase model selection without any in-session
spawning. It pairs naturally with SOL's own advice to **decompose** rather than rely on
mid-process pausing (`why-sol-works.md`, §HALT/WAITUSERINPUT).

**Strength / cost.** High for isolation and per-phase model; low–medium effort when a launcher
already exists.

---

## L4 — Foreign orchestrator

**What it is.** Embed SOL inside an external orchestration framework (LangGraph and similar):
the framework owns control flow and node execution deterministically, while SOL is used to
specify *what each node does*. SOL's own agentic constructs (`SPAWN`, control flow) are largely
set aside in favor of the framework's graph.

**Strength.** Highest determinism for orchestration — it is a real engine.

**Cost / trade-off.** High, and it inverts SOL's premise: control returns to a deterministic
engine, and SOL is demoted from "the runtime is the agent" to "node description language." Use
this when reproducibility/auditability of the *orchestration* outweighs the expressiveness of
agent-led control flow.

---

## L0 — Observability instead of coercion (orthogonal)

**What it is.** Do not force — **measure**. Capture the execution trace (structured logs,
return signals, session metadata about which model ran each boundary, tool-call records) and
verify after the fact that each `SPAWN` produced an isolated session, on the expected tier, with
the contract respected. Deviations are reported, not prevented.

**Why it matters.** It is the only approach that tells you *whether* any of L1–L4 is actually
working, and it is the foundation of structured testing (see `testing-sol.md`). Predictability
you cannot observe is predictability you cannot trust.

**Strength / cost.** It does not increase determinism directly; it makes determinism *visible*
and regressions *detectable*. Low–medium effort, high diagnostic value. Pair it with whatever
forcing layer you choose.

---

## Choosing a strategy

A rough decision path:

1. **Start at L1.** Always add execution directives — they are free and raise the floor.
2. **Need isolation, not specific models?** Lean on contracts (make `accepts`/`returns` strong,
   let the linter require them) and L2b native sub-agents. Isolation is contract-entailed, so
   this is often enough.
3. **Need a *specific* model at a boundary?** You need L2b (native sub-agent with a `model:`) or
   L3 (a helper / relaunch). No amount of L1 prompting guarantees it.
4. **Need reproducible, auditable orchestration?** Consider L3c (compile) or L4 (foreign
   orchestrator) — accepting that SOL's agent-led control flow steps aside.
5. **Always add L0.** Whatever you pick, instrument it so you can verify it and catch
   regressions.

The recurring rule: **pick the shallowest layer that meets your real determinism need.** SOL
stays the layer of intent; predictability is a deployment decision made around it, not a
property bolted into the language.

---

## See also

- `why-sol-works.md` — why SOL is non-prescriptive on purpose.
- `SOL-and-harness.md` — how SOL maps onto Claude Code, Cursor, Windsurf, Copilot.
- `SOL-and-models.md` — which SOL workloads run with confidence on which model + environment.
- `testing-sol.md` — measuring execution fidelity across configurations.
