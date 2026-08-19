# Why SOL Works: A Design Rationale from First Principles

*This document explains the reasoning behind SOL's design choices from the perspective of how large language models actually work. It is not a specification — the spec lives in `spec/sol-0.6.md`. This is the "why" behind the "what."*

---

## The Question We Started From

When we began designing SOL, we asked a question that sounds deceptively simple: *what does it mean to write a process for an AI agent?*

The existing answers were all variations of the same idea: write a process the way you would for a deterministic machine — define states, transitions, conditions, and let a runtime engine interpret them. The agent, in these models, is a tool that the engine calls when it needs to perform a specific step. Intelligence is a plugin; control belongs to the engine.

We went the other way. We made the agent the runtime.

This document explains why that inversion is not just a philosophical preference, but a decision grounded in how large language models actually work — what they are good at, where they struggle, and what happens when you design *with* those properties instead of against them.

---

## 1. The Central Inversion: The Agent Is the Runtime

Every other process format we surveyed — Serverless Workflow, AWS Step Functions, LangGraph, BPMN — shares a common architecture: a deterministic engine reads the process definition and orchestrates execution. The LLM, if present at all, is invoked for specific tasks within a larger mechanically-controlled flow.

This architecture has real virtues: reproducibility, auditability, predictable cost. But it has a fundamental cost: it requires that the process definition be expressed in a vocabulary that the engine can parse deterministically. Every branching condition must be a computable predicate. Every action must map to a registered function. The space of things you can say is bounded by the grammar of the engine.

We noticed that the most capable agents we worked with were already doing something different. When given a well-written description of a task — even in plain prose — they could decompose it, order it, parallelize where safe, recover from errors, and produce correct outputs. The bottleneck was not the agent's ability to understand. The bottleneck was the expressiveness of the format we were using to give it instructions.

SOL is built on a different premise: **the agent has enough understanding to be the runtime.** The process definition expresses *what* needs to happen and *under what conditions*. The agent decides *how* — including sequencing, parallelization, error recovery, and model selection. This is not a limitation. It is the source of SOL's expressive power.

The practical consequence is that SOL processes can say things that no deterministic engine could evaluate:

```json
{ "TODO": "Identify the most likely root cause and write a one-paragraph explanation" }
```

This instruction is not computable in the traditional sense. There is no parser that can resolve "most likely root cause" into an executable predicate. But a capable LLM can fulfill it — and fulfill it better than any hand-coded heuristic would.

---

## 2. Why JSON as the Structural Layer

If the agent is the runtime, the process definition needs to be something the agent can read. This sounds obvious, but it has significant design implications.

We considered three alternatives:

**YAML** is more readable than JSON for humans, which is why it dominates configuration files. But it has well-documented failure modes: implicit type coercion (the "Norway problem," where `NO` becomes boolean `false`), indentation sensitivity, and multiple syntaxes for the same construct. More importantly, YAML's readability comes precisely from its looseness — it is designed to let humans write quickly, not to be unambiguous. When a process breaks, you want the format to be the least likely source of confusion.

**A custom DSL** — something like `WHEN <condition> THEN <action>` — would give us the most control over syntax. But it would require a parser, which reintroduces a runtime dependency. More subtly, it would require the agent to learn a grammar it has not seen before. Every SOL-specific construct would need to be explained in the system prompt or inferred from examples.

**JSON** has the properties we needed. It is universally parseable without special instructions. It is the native format of almost every tool-calling protocol in modern AI systems — when LLMs interact with external tools, they already do so via JSON-encoded function calls. It is strict enough to be unambiguous (no implicit typing, no indentation rules) and flexible enough to represent arbitrarily nested structures. And crucially, LLMs have seen enormous quantities of JSON during pretraining — configuration files, API responses, package definitions, schema files. They do not need to be taught JSON; they already know it.

We also want to be honest about what JSON costs: it is more verbose than YAML and less readable at a glance. A complex SOL process looks like a lot of curly braces. We accept this cost deliberately. The benefits — unambiguity, parsability, tool ecosystem compatibility — outweigh the readability tax, especially because SOL processes are read primarily by agents, not humans.

---

## 3. Natural Language at the Leaves: The TODO Philosophy

The most distinctive choice in SOL is what we put at the leaves of the tree.

Most structured formats, when they reach the level of individual actions, switch to a fixed vocabulary. LangChain has tools with typed signatures. AWS Step Functions have Lambda function ARNs. Even prose-friendly formats like GitHub Actions YAML eventually resolve to `run:` with a shell command or `uses:` with a registered action.

We use natural language:

```json
{ "TODO": "Read all status files in projects/ and identify which ones have overdue tasks" }
```

This is not laziness. It is a considered choice based on what LLMs are actually good at.

A fixed vocabulary for actions is a leaky abstraction. If you enumerate ten verbs — READ, WRITE, SEARCH, SUMMARIZE, ANALYZE, COMPARE, TRANSFORM, VALIDATE, NOTIFY, EXECUTE — you will immediately encounter tasks that don't fit. So you add more verbs. Then you need to document them, maintain them, teach them to users, and update them as capabilities evolve. The vocabulary becomes a second language that sits between the author's intent and the agent's execution.

Natural language has no such problem. The author writes what they mean, using words they already know, at whatever level of specificity is appropriate. The agent — which has been trained on vast quantities of human instruction — understands what to do. Not because we defined a protocol, but because instruction-following in natural language is what LLMs are fundamentally trained for.

This does have a cost: natural language is not deterministic. Two different agents, or the same agent in two different runs, may interpret the same TODO differently. We acknowledge this honestly in the design documentation. For tasks where exact reproducibility is required, SOL is not the right tool at the leaf level — RUN is, because RUN is verbatim.

But for the vast majority of agentic tasks — the kind of tasks where you would actually use an AI agent rather than a shell script — the slight non-determinism of natural language instructions is acceptable, and the expressiveness gain is enormous.

---

## 4. The TODO/RUN Boundary: Precision Where It Matters

SOL has exactly two types of leaf instruction: TODO and RUN. Understanding the difference between them is central to understanding SOL.

**TODO** delegates interpretation entirely to the agent. The agent decides what commands to run, what files to read, what tools to invoke. The instruction is a statement of desired outcome, not a prescription of method.

**RUN** is verbatim. What you write is what gets executed. The agent does not reinterpret it, does not substitute commands, does not decide a better approach. The only flexibility is in `{{placeholder}}` markers, which the agent fills from context before executing.

```json
{ "RUN": "python main.py vault-scan {{repository}} --max-files {{max_files}}" }
```

Here, `python main.py vault-scan` is fixed. The agent fills in `{{repository}}` and `{{max_files}}` from context, but does not touch the rest.

Why does this boundary matter?

Because there are tasks where the agent's judgment is the whole point — analyzing code, synthesizing a report, identifying patterns — and tasks where exactness is the whole point — invoking a specific script, running a specific test suite, committing with a specific format. Conflating the two creates problems in both directions.

If TODO were used for everything, authors would have no way to express "run exactly this command." Agents might paraphrase, optimize, or substitute — appropriate for reasoning tasks, dangerous for infrastructure tasks.

If RUN were used for everything, authors would have to anticipate every detail of every command at process-writing time. This defeats the purpose of using an AI agent.

The TODO/RUN distinction is also honest about where trust lives. TODO says: "I trust the agent's judgment on how to accomplish this." RUN says: "I have specified this precisely; execute it precisely." Both are legitimate stances. SOL makes the stance explicit.

The `{{placeholder}}` syntax in RUN is worth explaining. Without it, RUN would be pure verbatim — useful for fixed commands but awkward for commands that need runtime context. With it, RUN becomes "verbatim except for these clearly marked substitutions." The double-brace syntax is distinctive enough to be unambiguous both to agents and to human readers.

Seen against §1, RUN is where the central inversion becomes concrete. The other formats put a deterministic engine in charge and let it call an AI step where judgment is needed; intelligence is a plugin inside a mechanical pipeline. SOL reverses the direction of the call: the agent is the orchestrator, and RUN is the deterministic, algorithmic operation it reaches *down* to when exactness matters. Determinism is no longer the engine that calls the AI — it is what the AI calls. So TODO and RUN are not two interchangeable kinds of leaf; they are the two directions control can flow, with the agent always holding the orchestration and dropping into verbatim execution deliberately, at the points it chooses.

---

## 5. Reading Before Acting: Global Context as a Feature

A LLM reading a SOL process does not have an instruction pointer. It does not execute instructions one at a time as it encounters them. It reads the entire document first, forming a complete picture of what the process does, before it begins executing anything.

We designed SOL explicitly for this property, and it has significant consequences.

**Forward references work.** A CALL can precede its corresponding SUB definition, because by the time the agent executes the CALL, it has already read the SUB. This is why we say definition order does not matter in SOL. The agent has global knowledge of the document; there is no parse-time vs. runtime distinction.

**Parallelization is inferrable.** The agent can look at a sequence of TODO instructions and determine which ones are independent — which can run concurrently, which must wait for prior results. We deliberately do not encode this in the process definition, because the agent can infer it correctly from context and because encoding it would require the process author to reason about execution strategy, which is not their concern.

**Context propagates naturally.** When one instruction produces output, subsequent instructions can reference it in natural language: "using the findings from the previous step." The agent carries context across instructions, just as a human would carry context across steps of a task.

**Errors can be caught early.** If the agent identifies an inconsistency or ambiguity while reading the process — a condition that can never be true, a CALL to a non-existent SUB — it can flag it before executing anything, rather than failing mid-process.

This is qualitatively different from deterministic runtimes, which typically execute instructions sequentially and can only identify problems as they are encountered. The agent's ability to read globally and reason before acting is not a workaround for a missing feature — it is the execution model SOL is designed around.

---

## 6. Semantic Model Tiers: Expressing Intent, Not Identity

SOL processes can specify which model tier to use for each instruction or scope:

```json
{ "TODO": "Summarize progress since yesterday for each active project", "model": "fast" }
{ "TODO": "Write the final briefing to output/daily-briefing.md", "model": "smart" }
```

We deliberately did not use model identifiers like `"claude-opus-4-8"` or `"gpt-4o"`. We use three semantic tiers: `fast`, `balanced`, and `smart`.

The reason is that model identifiers express *which model*, while tiers express *what kind of reasoning is needed*. These are different things, and the second is more stable.

A process that says `"model": "claude-opus-4-7"` will be outdated the moment a better model is released. The author's intent — "use the most capable reasoning available" — becomes coupled to a specific artifact that will be superseded. Worse, the process becomes provider-coupled: it cannot run on a different agent that uses a different model family.

A process that says `"model": "smart"` expresses the same intent in a form that remains valid across model generations, providers, and capability improvements. The executing agent resolves `smart` to whichever model best fits that tier in its current configuration. The process stays correct.

This also makes the `model` field a useful signal for a different reason: it communicates cognitive load. A SOL process where some steps are `fast` and others are `smart` is self-documenting about where the hard work is. A reader — human or agent — can see at a glance that the fast steps are mechanical and the smart steps require careful reasoning.

The `model` field is also, implicitly, a sub-agent hint. When a SOL process has sections with different model tiers and different `role` definitions, an agent may choose to spawn dedicated sub-agents for those sections rather than handling them inline. The agent makes this decision; the process just declares the intent.

---

## 7. Control Flow as Structural Grammar

SOL provides four control flow constructs: IF, WHEN, REPEAT, and the family of invocation mechanisms (CALL, SPAWN, DELEGATE). These sit at the branch nodes of the tree, while TODO and RUN sit at the leaves. This separation — structure at the branches, language at the leaves — is central to why SOL is readable by both agents and humans.

### IF and WHEN

IF is a binary conditional: when/then/else, exactly as in every programming language. Its semantics are unambiguous.

WHEN is a multi-branch conditional, and here we want to be honest about something we learned during development.

The temptation with a multi-branch conditional is to make it handle overlapping conditions elegantly — like a pattern-matching construct that fires all matching branches, or a priority-ordered dispatch. We explored both. We eventually settled on a simpler and more honest design: WHEN is predictable only when conditions are mutually exclusive.

```json
{
  "WHEN": [
    { "when": "any project has overdue tasks", "then": [...] },
    { "when": "any deadline within 3 days", "then": [...] },
    { "else": [...] }
  ]
}
```

These conditions can overlap — a project might simultaneously have overdue tasks and a deadline within 3 days. What does an agent do? It depends on how it interprets the construct. Different agents, or the same agent in different runs, may handle this differently.

We document this limitation explicitly in the spec, and our recommendation is clear: use WHEN only when conditions are mutually exclusive. When conditions can overlap, use sequential IF blocks instead — the behavior is unambiguous by construction.

This is an example of a broader principle in SOL's design: we prefer honest acknowledgment of limitations over false promises of determinism. SOL is not a programming language. Agents are not compilers. When a construct's behavior depends on the agent's interpretation, we say so.

### REPEAT

REPEAT provides four loop variants: `while`, `until`, `for`, and `foreach`. These express iteration intent without prescribing execution strategy.

Notice what REPEAT does not say: it does not say whether iterations run sequentially or in parallel. This is intentional. Whether a `foreach` iterates sequentially or in parallel depends on whether the iterations are independent, what resources are available, and what the agent's execution context supports. These are not things the process author knows at writing time. They are things the agent can determine from context.

We removed explicit parallelization control from REPEAT (it was present in an earlier version) because it created a false sense of prescription. Writing `"parallel": true` in a process definition does not make iterations run in parallel — it makes the agent *try* to run them in parallel, subject to whatever constraints exist. This is better expressed as a general instruction to the agent ("parallelize iterations when they are independent") than as a per-instruction flag.

---

## 8. The Subroutine Hierarchy: Three Kinds of Delegation

SOL v0.5 provides three mechanisms for delegating work within a process: CALL (invoking a SUB), SPAWN (invoking an AGENT), and DELEGATE (inline delegation). They differ along two dimensions: whether the context is shared or bounded, and whether the routine is explicit or implicit.

**CALL / SUB** shares context. The subroutine can see everything the caller can see — all prior outputs, all variables in scope. It is the right choice when the subroutine is a factored-out sequence of instructions that naturally belongs to the same execution context as the caller.

**SPAWN / AGENT** creates a bounded context. The calling process explicitly states what information to pass (`with`) and what to expect back (`returns`). The agent executes in a fresh context. This is the right choice when the delegated work is conceptually independent — a security audit, a specialized analysis — and when you want explicit control over the interface.

**DELEGATE** is like SPAWN but inline — no pre-defined AGENT, just an anonymous one-off delegation. The right choice for tasks that are logically isolated but don't warrant a named, reusable AGENT definition.

This hierarchy reflects how we actually think about delegation: sometimes we hand work to a colleague with full context ("you know the situation, handle this"), sometimes we hand work to a specialist with a defined brief ("here are the files, here is what I need back"), and sometimes we just assign a one-off task without formalizing it. SOL makes all three patterns explicit.

The `accepts` and `returns` fields on AGENT are worth noting specifically. They are contracts — not type signatures, not JSON schemas. In their simplest form they are plain descriptions:

```json
{
  "AGENT": {
    "name": "security-auditor",
    "accepts": "Modified files and their diffs.",
    "returns": "Findings with severity, file path, line range, and suggested fix."
  }
}
```

When the descriptor is the interface between two agents that must agree without a human in the loop, prose alone leaves too much to interpretation. SOL 0.6.0 therefore lets a contract also take a **structured form** — a map of field name to a few optional, composable constraints (`required`, `anyof`, `number`, `json`, plus `desc` for the meaning):

```json
{
  "AGENT": {
    "name": "security-auditor",
    "accepts": {
      "files":    { "required": true, "desc": "modified files and their diffs" },
      "severity": { "anyof": ["all", "high+"], "desc": "minimum severity to report" }
    },
    "returns": {
      "findings": { "json": true, "required": true, "desc": "list of {severity, file, line_range, fix}" }
    }
  }
}
```

The structure pins down only what would *break the machine* if misread — a closed set of values, a required field, a parseable payload — while meaning still lives in prose, where an LLM reads it best. Neither form is machine-enforced: enforcement is the agent's understanding of the contract, not a runtime type checker. This is consistent with SOL's overall philosophy: express intent clearly, trust the agent to honor it. The full reasoning — and the alternatives weighed — is in `io-contracts.md`.

---

## 9. HALT and ONERROR: Distinguishing Failure from Intent

Most process formats have a single concept for "stop": an error. If something goes wrong, the process fails. SOL has two concepts: ONERROR (something went wrong) and HALT (stopping is the correct outcome).

This distinction reflects something real about process semantics.

Consider a process that processes items from a queue. When the queue is empty, the process should stop. This is not an error — it is the expected completion condition. Using ONERROR to handle this would conflate an expected outcome with a failure mode, which makes monitoring, logging, and recovery more difficult.

```json
{
  "IF": {
    "when": "queue is empty",
    "then": [{ "HALT": "Queue is empty — nothing left to process." }]
  }
}
```

HALT is also useful for human-in-the-loop processes where the human decides not to continue. The right way to design this depends on the execution context.

In an interactive session where the harness supports mid-process pausing, `WAITUSERINPUT` creates an explicit structural checkpoint:

```json
{ "WAITUSERINPUT": "Review the draft above. Type APPROVE to continue or CANCEL to stop." }
```

If the user types CANCEL, the agent should HALT — not because something failed, but because the human made a decision.

In any other context — scheduled runs, API-invoked agents, automated pipelines — `WAITUSERINPUT` is not the right tool. The correct pattern is **process decomposition**: the first process produces its output and halts normally at the end of its routine; the human reviews the output and invokes a second process with their decision as initial context. This works everywhere, because it requires nothing from the runtime beyond the ability to execute a process. `WAITUSERINPUT` is a context-dependent shortcut valid only when the execution context is guaranteed to be interactive. When in doubt, decompose.

ONERROR is the complement: it handles situations where something actually went wrong and recovery is possible. ONERROR can be local (attached to a specific instruction) or global (at the root level). Local ONERROR takes precedence over global, which allows fine-grained recovery strategies for known failure modes while maintaining a global fallback for unexpected errors.

---

## 10. What SOL Deliberately Refuses to Do

Understanding SOL also means understanding what it does not do, and why.

**SOL has no true variables.** There is no `x = 5` or `$result = previous_output` — no assignment, no scoping, no mutation. But this does not mean a process cannot *refer* to things: it can name the fields declared in an `accepts` contract, point to data and references in the containing Markdown document, draw on context elements it knows are available, and use `{{placeholder}}` markers (in `RUN` and in loop bindings) to fill specific values from that context. What is absent is the variable *mechanism*, not the ability to reference. Context otherwise flows between instructions through the agent's working memory — it tracks what it has done and what it has learned, and references this context in natural language. This is a design choice, not a missing feature: SOL is a process format, not a programming language, and the agent carries context the way a human does when executing a checklist.

**SOL does not prescribe execution strategy.** The process definition expresses what to do, not when relative to other things. Parallelization, scheduling, and sequencing are inferred by the agent from the structure of the process and its execution context. This is intentional: the agent has information the process author doesn't (what resources are available, which operations are independent, what the current system load is).

**SOL is not a replacement for code.** When a task requires precise computation, data transformation with exact semantics, or behavior that must be reproducible byte-for-byte, the right answer is a script called via RUN. SOL handles the orchestration — the "what and when" — while code handles the implementation — the "exactly how."

**SOL does not guarantee determinism.** Two runs of the same SOL process may produce different outputs, because the agent makes judgments that vary. We are honest about this. For tasks where determinism is required, SOL is not the right choice at the leaf level. For the vast majority of agentic workflows — the ones where you want the agent to understand and adapt, not merely to execute mechanically — the slight non-determinism is the price of expressiveness, and it is worth paying.

---

## Conclusion

SOL works because it is designed for what LLMs actually do, not for what deterministic machines do.

LLMs read global context before acting. SOL is designed to be read globally, with definition order that doesn't matter and forward references that resolve at execution time.

LLMs understand natural language instructions. SOL puts natural language exactly where the cognitive load is — at the leaf level, in TODO — and uses structure only for control flow.

LLMs struggle when they must simultaneously reason and generate structured output under rigid constraints. SOL separates these concerns: the structure is JSON (read by the agent, not generated under constraint), and the content is natural language (where the agent is most capable).

LLMs make judgments. SOL lets them. The agent decides how to parallelize, which specific tool to invoke, how to recover from an unexpected state. The process expresses intent; the agent expresses competence.

This is not a design that works for every kind of automation. If you need exact reproducibility, use a deterministic runtime. If you need millisecond latency, use compiled code. SOL is designed for a specific sweet spot: processes complex enough to benefit from an agent's understanding, but structured enough that the agent needs guidance on what to do and when.

Within that sweet spot, SOL is — we believe — the most direct path from human intent to agent execution.
