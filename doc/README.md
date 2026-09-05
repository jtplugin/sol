# SOL Documentation — Annotated Index

> A reasoned map of the `doc/` folder. Each entry says *what the document contains* and *which
> questions it answers*, so you can find the right one without opening all of them.
>
> English is the language of this folder, with two declared exceptions, both marked in their
> entry below: `howto-testing_IT.md` is a translation of its English original, and
> `experiment-kv-quantization.md` exists only in Italian.

The canonical specification lives in [`../spec/sol-0.6.md`](../spec/sol-0.6.md). Everything here
is rationale, guidance, positioning, or research *around* the spec — never a substitute for it.

---

## Suggested reading paths

- **New to SOL?** → `DESIGN.md` → `why-sol-works.md` → the spec.
- **Authoring SOL processes?** → `io-contracts.md` → `sol-translate.md` → `sol-convertibility.md`.
- **Deploying SOL on a real engine?** → `SOL-and-harness.md` → `SOL-and-models.md` → `predictability-strategies.md`.
- **Embedding SOL in Claude Code skills?** → `SOL-and-skills.md`.
- **Evaluating or comparing SOL?** → `sol-comparison.md` → `llm-research-annotated-bibliography.md` → `testing-sol.md`.
- **Running the minimum-context campaign?** → `testing-strategy.md` → `testing-runners.md` → `experiment-minimum-context.md` → `experiment-minimum-context-pilot.md` → `experiment-kv-quantization.md` → `experiment-frontier-reference.md`.
- **Reading its results?** → `measures.md` → [`../report/analysis/FACTSHEET.md`](../report/analysis/FACTSHEET.md) → the notebook beside it.

---

## 1. What SOL is, and why it is built this way

### [`DESIGN.md`](DESIGN.md)
The canonical design rationale: every major choice in the spec, with the reasoning behind it.
- *Why is the agent the runtime, and what follows from that?*
- *Why `TODO` vs `RUN`, and why does `{{}}` appear only on `RUN`?*
- *Why JSON instead of YAML or a custom DSL? Why is `WHEN` not `CASE`?*
Read it when you want to understand, extend, or challenge a decision in the spec.

### [`why-sol-works.md`](why-sol-works.md)
The first-principles companion to `DESIGN.md`, argued from how LLMs actually behave.
- *Why does "the agent is the runtime" exploit LLM strengths instead of fighting them?*
- *Why natural language at the leaves, global "read before execute", semantic model tiers?*
- *What does SOL deliberately refuse to do (variables, execution strategy, determinism), and why?*
Read it when you want the "why it works", not just the "what".

---

## 2. Authoring: getting intent into SOL, and SOL back out

### [`io-contracts.md`](io-contracts.md)
Why `accepts`/`returns` gained an optional structured form in 0.6.
- *When is a prose contract not enough, and what minimal structure fixes it?*
- *What is the test for adding structure? ("Keep it only if getting it wrong breaks the machine, not the conversation.")*
Read it before designing contracts between agents.

### [`think2proc.md`](think2proc.md)
The concept piece for the skill that turns human intent into SOL.
- *Can I describe a process in plain language (or import YAML/XML) and get valid SOL back?*
- *How should the skill handle ambiguity and contradictions instead of guessing?*
Read it for the vision of authoring SOL without writing JSON by hand.

### [`sol-translate.md`](sol-translate.md)
Reference for the `sol-translate` Claude Code skill (the practical counterpart to `think2proc`).
- *How do I install and invoke the skill? What inputs (prose, pseudocode, YAML, XML) does it accept?*
- *What does it produce, and how does it choose constructs, model tiers, and file structure?*
Read it when you actually want to run the translator.

### [`sol-convertibility.md`](sol-convertibility.md)
SOL out: turning a SOL process into diagrams and into prose.
- *How does each SOL construct map onto standard flowchart primitives?*
- *How do `sol2mermaid.py` / `sol2drawio.py` work, and why is this possible with no runtime?*
- *How does `sol2prose.py` read a process back in plain language, and why is that the round-trip
  check on what you wrote in JSON?*
Read it when you need to show a process to non-JSON readers — or to verify that the SOL you
generated says what you meant.

---

## 3. SOL in the execution ecosystem

### [`SOL-and-harness.md`](SOL-and-harness.md)
Where SOL fits among agentic coding engines (Claude Code, Cursor, Windsurf, Copilot).
- *What is an "agentic harness", and why is SOL not one?*
- *Which engine exposes enough surface (skills, hooks, permissions) to host SOL well, and why?*
Read it to understand SOL's place in the tooling landscape.

### [`SOL-and-skills.md`](SOL-and-skills.md)
The focused case of using SOL to define Claude Code skills.
- *When should a skill be SOL vs prose vs a hybrid?*
- *What does the Markdown-wrapper-plus-SOL-block pattern look like in practice?*
Read it when writing a Claude Code skill with real control flow.

### [`SOL-and-models.md`](SOL-and-models.md)
What kind of SOL you can hand to a given model + environment *with confidence*.
- *What can a bare API model (e.g. Qwen on Ollama) run, versus a tool loop, versus a full harness?*
- *Which constructs degrade silently where (`SPAWN` → role-play, `model` tiers ignored, `RUN` with no shell)?*
- *How do I author a self-contained SOL for a modest model?*
Read it before targeting a specific runtime, especially a thin one.

### [`predictability-strategies.md`](predictability-strategies.md)
How to make a SOL intent (isolation, model tier) *reliably realized*, since the language cannot force it.
- *Why can SOL pressure context isolation but not model selection from inside the language?*
- *At which layer do I inject predictability (prompt, harness, external runtime, foreign orchestrator), and what does each cost?*
Read it when "the agent usually does it" is not good enough.

---

## 4. Positioning and research

### [`sol-comparison.md`](sol-comparison.md)
SOL's strategic positioning against other orchestration approaches.
- *How does SOL differ from LangGraph, CrewAI, AutoGen, integrated data platforms, and hybrid enterprise patterns?*
- *Where does SOL sit as an "intermediate layer" of automation?*
Read it for the elevator pitch and the competitive map.

### [`research/multiagent-infrastructure.md`](research/multiagent-infrastructure.md)
Research notes on how multi-agent infrastructure works in practice.
- *How do real frameworks manage state, routing, and especially token cost?*
- *Which patterns (history windowing, structured inter-agent output, RAG, summarization nodes) are actually used?*
Read it for grounding on the engineering realities SOL coexists with.

### [`research/a2a-protocol.md`](research/a2a-protocol.md)
Research notes on the Agent-to-Agent (A2A) protocol.
- *What is A2A, how is it governed, and how does it relate to MCP?*
- *How do agents discover and delegate to each other over it?*
Read it when thinking about cross-agent interoperability beyond a single harness.

### [`llm-research-annotated-bibliography.md`](llm-research-annotated-bibliography.md)
The published research behind SOL's claims about LLMs, with honest gaps flagged.
- *What evidence supports "the agent is the runtime", the `TODO`/`RUN` split, reading before acting?*
- *Which claims are well-supported, which are indirect, and which are not yet studied?*
Read it to check the empirical footing of the design.

---

## 5. Quality and evolution

### [`testing-sol.md`](testing-sol.md)
A method (not yet an implemented suite) for evaluating SOL across configurations.
- *How do you test something non-deterministic — and why separate execution fidelity from outcome quality?*
- *What is the language × harness × model test matrix, and what is a realistic first step?*
Read it when you want evidence, not opinions, about which setup runs SOL faithfully.

### [`testing-strategy.md`](testing-strategy.md)
The strategy and materials around the method: how the testing effort is structured.
- *What are the three rings (toolchain, fixture conformance, execution) and why that order?*
- *How is a bespoke fixture different from an example, and why is the `W0–W3` class the spine?*
Read it to see the overall plan and the fixture catalogue under [`../tests/`](../tests).

### [`testing-runners.md`](testing-runners.md)
The execution architecture for Ring R3: what a *runner* is and how results flow.
- *What invariants must every runner obey, and why is one session-based executor enough (emulation by restriction)?*
- *Why is interactivity an orthogonal modifier, not a new context? How are results monitored, catalogued, and analyzed?*
Read it before building or extending the runners and the results pipeline.

### [`howto-testing.md`](howto-testing.md) — *also as [`howto-testing_IT.md`](howto-testing_IT.md)*
The practical companion to the three documents above: how to actually run tests, add fixtures, and read results.
- *How do I run a fixture with the session runner (`executor.py`) or the API runner (`api_executor.py`)?*
- *How do I add a new input, configure expectations, and follow the probe workflow?*
- *How do I filter `index.jsonl` by runner type, model, or fixture? What do degradation modes mean?*
Read it when you want to do things, not understand them.

### [`experiment-minimum-context.md`](experiment-minimum-context.md)
The **pre-registered protocol** for the first full R3 campaign: how much context, which model, and how much input preparation SOL needs to run predictably *without* a frontier model in a rich harness.
- *What is the minimum sufficient configuration, and what does it cost?*
- *What is deliberately not tested, and why are those exclusions decisions rather than omissions?*
- *How are comprehension, control-flow fidelity, and end-to-end outcome scored apart from each other?*
- *What is frozen before the first run, and in what order must the sealed replication set be opened?*
Read it before running the campaign — and note that its git history is the evidence the plan preceded the results.

### [`measures.md`](measures.md)
What every number the campaign records means, and how it is computed. The single prose
statement of the measures: `scripts/dashboard.py` renders this file into the glossary on the
dashboard, so the page and this document cannot say different things.
- *What is the difference between a rate of zero and a rate that is absent?*
- *Why can `quality` never read `pass` on `support-intake`, and why is that deliberate?*
- *What does conditional fidelity isolate that sequence fidelity does not?*
- *What does each degradation mode actually mean?*
Read it before reading a chart. The authority remains `tests/runner/checker.py`, which each
entry names.

### [`experiment-minimum-context-build-log.md`](experiment-minimum-context-build-log.md)
Dated, factual build log for the campaign's infrastructure (fixture, checker extension, dataset
pipeline, runner backend, verification tooling) — written from verified command output during
the build session, not reconstructed afterward.
- *Exactly which commits, which numbers, which decisions — and on what evidence?*
- *What deviated from plan, and why? What remains blocked, and on what?*
Read it when writing the methods section, or when you need to know precisely what existed when.

### [`experiment-minimum-context-pilot.md`](experiment-minimum-context-pilot.md)
The technical pilot: what it took to make the campaign actually **run on local hardware** (a single
8 GB GPU), and what the instrument turned out to get wrong once exercised.
- *What is the executable envelope of this hardware — and why is the KV cache, not the weights or the
  context size, the binding constraint?*
- *How do these models really fail (non-terminating reasoning, looping traces, plain wrong answers),
  and which failures are data rather than noise?*
- *Why is a runaway run kept instead of retried, and what does that require of the oracle?*
- *What does a run cost, after the estimate was rebuilt twice?*
Read it before configuring a cell, before trusting a rate computed on a small sample, or when you
need the measured basis for the campaign's cost model.

### [`experiment-kv-quantization.md`](experiment-kv-quantization.md) — *in Italian*
Does quantising the KV cache to `q8_0` change what the models produce? The cache is
not optional -- three cells of five do not fit on the card without it -- so the answer decides
whether 450 runs of the main campaign carry a caveat.
- *Does the cache perturb the computation at all, and how would you know without a thousand runs?*
- *Why did the first attempt fail by design, and why did the second and third fail the same way?*
- *What does a pass/fail oracle throw away, and what does the continuous metric recover?*
- *What can n=10 exclude, and what stays invisible no matter how the arms are compared?*
Read it before trusting a per-cell result in the campaign, or before designing any A/B on this
fixture: it documents which subjects are measurable at all, and why.

### [`experiment-frontier-reference.md`](experiment-frontier-reference.md)
The frontier reference cell: the untracked per-item arm run a second time through
`claude -p --model claude-haiku-4-5`, to put a scale under the campaign's ratios. Registered in the
protocol before it ran, and kept outside the analysis plan on purpose.
- *Is 0.392 close to the ceiling of this task, or far from it?*
- *What has to be held fixed for a hosted model to be comparable at all — and which three CLI flags
  decide whether you are measuring the model or the operator's shell?*
- *Does the flat `L` curve survive on a model thirty times larger? Does prose beat JSON there?*
- *When a hosted model fails this fixture, what exactly is it failing at?*
Read it when you need the scale behind a campaign number, or before driving a coding agent as if it
were a bare model.

### Working notes of the pilot — *not published*
The pilot's contemporaneous session notes, unedited and including the conclusions later reversed,
are kept with the campaign's private working record and are deliberately not published: they are
written in the shorthand of the internal workflow, and out of that context they answer no question
a reader of this folder would ask. Everything they establish about the campaign is carried, with
its evidence, by `experiment-minimum-context-pilot.md` and
`experiment-minimum-context-build-log.md`.

### [`../report/analysis/`](../report/analysis/) — the results
Where the campaign's numbers live. `FACTSHEET.md` is the generated sheet of facts, each with
its N and its interval; `01_fatti.ipynb` is what generates it, and `tidy.csv` is the one table
it reads. Start from [`../report/analysis/README.md`](../report/analysis/README.md).
- *Where does a number quoted in an article come from, and how do I recompute it?*
- *What does the design allow me to average, and what does it forbid?*
Read it after `measures.md` and before disagreeing with a result.

### [Test README](../tests/README.md)
A README on testing

---
## Other info and tools
### Articles
- [Articoli pubblicati o in corso di pubblicazione](../articles/README.md)


---
## Related material outside `doc/`

- [`../spec/`](../spec) — the versioned SOL specifications (current: `sol-0.6.md`).
- [`../tests/`](../tests) — the testing library: R1 toolchain tests and the bespoke fixtures.
- [`../.claude/skills/sol/`](../.claude/skills/sol) — the `sol` skill and its binding guides
  (`authoring.md`, `contracts.md`, `borderline-cases.md`, `sol-vs-prose.md`) plus `sol-lint.py`.
- [`../articles/`](../articles) — long-form / presentation pieces (some with Italian `_IT` variants).
