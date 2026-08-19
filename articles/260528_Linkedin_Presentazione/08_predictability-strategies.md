# Predictability is not a language feature — it's a layer you choose

Twice in this series, an honest admission got deferred: SOL cannot force anything. No parser compels a branch, no scheduler guarantees a `SPAWN` becomes a genuinely isolated session, no type checker enforces a contract. The spec says it plainly — contracts are *"honored by the agent's understanding, not by a runtime type checker,"* and `model` is *"a hint, not an imperative."*

That's not a gap to apologize for. It's what lets a `TODO` say *"identify the most likely root cause"* — something no deterministic engine could evaluate in the first place. The price is real, though: nothing in the language can force an agent to behave the way you want. So the right question was never *"how do I make SOL prescriptive?"* It's: *if I need a particular behavior to be predictable, at what layer do I inject that predictability, and what does it cost me?*

---

## What "predictable" actually means here

Not byte-identical output — natural-language leaves make that impossible by design. What we want is the **declared structure actually realized**: a `SPAWN` running in a genuinely isolated context rather than in-context role-play; a `model: "smart"` boundary actually landing on a stronger model; a contract actually checked at the boundary; a branch or an `ONERROR` actually firing as written. These are properties of *execution fidelity*. SOL expresses them; something outside SOL has to make them reliable.

---

## The asymmetry that shapes every choice

Not all intents are equally enforceable, and the reason matters more than any individual technique below.

**Context isolation is entailed by the contract itself.** SOL says an `AGENT` *"receives only what `SPAWN` passes via `with`, and returns only what `returns` describes."* That's a statement about information flow. Any layer that faithfully enforces "the callee sees only `with`" is *compelled* to create a clean context — there's no other way to satisfy that constraint. Isolation, in other words, can be pressured into existence just by taking the contract seriously.

**Model choice is entailed by nothing.** No information-flow property requires a specific model — that's exactly why `model` is *only* a hint. Forcing a particular model always needs a layer outside the agent's own judgment.

Practical consequence: you can pressure isolation from inside SOL's own discipline; you cannot pressure model selection without an external resolver. This single asymmetry decides most of what follows.

---

## Four layers, one principle

Every strategy injects predictability somewhere. The deeper the layer, the more authority moves out of the agent and into a deterministic executor — buying determinism at the cost of portability and engineering effort.

| Layer | Where | Strength | Portability | Effort |
|---|---|---|---|---|
| **L1 — Linguistic** | Inside the prompt | Low | Any model | Trivial |
| **L2 — Harness** | Platform features | Medium–High | Harness-specific | Low–Medium |
| **L3 — External runtime** | A deterministic helper beside SOL | High | Across models | Medium–High |
| **L4 — Foreign orchestrator** | SOL becomes node-spec only | Highest | Tool-specific | High |
| **L0 — Observability** | *(orthogonal)* measure, don't force | — | High | Low–Medium |

The rule that runs through all of it: **pick the shallowest layer that gives you the determinism you actually need.** Over-engineering predictability wastes exactly as much as ignoring it.

**L1, the cheapest lever**, is a directive placed above the SOL block — *"treat every `SPAWN` as a real boundary; start a clean sub-agent; honor `accepts` literally."* It costs nothing and works on any model, but it's still a request to a non-deterministic reader.

**L2 leans on the harness you're already running on.** The strongest single lever here is registering each SOL `AGENT` as a native sub-agent — in Claude Code, a file under `.claude/agents/` with a `model:` frontmatter. When the session reaches the matching `SPAWN`, the harness's own sub-agent mechanism opens it on the declared model, with genuine isolation as a side effect. Hooks and MCP-tool spawning sit nearby, each trading a bit more agent discretion for a bit more determinism.

**L3 is where predictability stops depending on goodwill.** A small external helper resolves a tier to a concrete model, launches an isolated session, validates the return against the contract — and the dispatching SOL step becomes a plain `RUN` of that helper instead of an in-context `SPAWN`. This is the only family of strategies that can force model selection, precisely because model choice isn't contract-entailed. It's also a partial departure from "the agent is the runtime": the boundary is now executed, not interpreted.

**L4 goes furthest:** embed SOL inside a foreign orchestrator (LangGraph and similar), where the framework owns control flow deterministically and SOL is reduced to describing what each node does. Highest determinism, but it inverts SOL's own premise — control returns to an external engine.

**L0 is orthogonal to all of them.** Don't force, measure: capture the trace, check after the fact whether a `SPAWN` was actually isolated, on the expected tier, with the contract honored. It's the only approach that tells you whether any of L1–L4 is actually working — predictability you can't observe is predictability you can't trust.

---

## A rough decision path

Start at L1 always — execution directives are free, and they raise the floor. If you need isolation but not a specific model, lean on strong contracts plus L2's native sub-agents; isolation is contract-entailed, so this is often enough on its own. If you need a *specific* model at a boundary, no amount of L1 prompting will guarantee it — go to L2's native sub-agent or to L3. If you need reproducible, auditable orchestration, consider L3's compilation step or L4, accepting that SOL's agent-led control flow steps aside. And whatever you pick, add L0 — instrument it so regressions are visible instead of silent.

---

## The honest center of the series

This closes a thread the series opened back in the article on delegation: SOL stays deliberately non-prescriptive, because that's what lets it speak in intent rather than in fixed transitions. Predictability isn't bought by distorting that — it's bought by injecting it, deliberately, at a layer you chose and can name. The language never stops being the layer of *what* a process means; everything in this article lives *around* it, not inside it.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
