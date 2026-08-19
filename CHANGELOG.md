# Changelog

## [0.6.1] — 2026-06

### Added
- `RETURN` instruction — ends the current process cleanly and yields control back to its invoker (parent process, `CALL` site, or the human at top level) without ending the executing agent. The intuitive, self-evident exit for "this process is done": unlike `HALT`, the word itself implies an "above" to return to. Optional value is the result yielded; when a structured `returns` is declared, the `RETURN` value mirrors that contract's shape (a non-matching shape is the caller's off-contract signal). Reverses the 0.6.0 decision to omit a `RETURN` construct — the earlier rejection assumed it would duplicate the contract; scoping it as an *early-exit / yield-upward* verb, distinct from the contract, removes that overlap

### Changed
- `HALT` clarified as a **global** stop — the red button that ends the *entire run*, agent session included, with no hand-off upward. Behavior unchanged; the spec now states the scope explicitly to remove the ambiguity that made agents read it as "end the whole session" even where only a local exit was meant
- Contract-violation guards now use `RETURN` (yield back to the invoker), not `HALT`: a failed `accepts` guard in one callee must end only *that* process and report upward, never abort the whole run. Spec, `reference.md`, `authoring.md`, and `contracts.md` updated accordingly

---

## [0.6.0] — 2026-05

### Added
- Structured input/output contracts — `accepts` and `returns` now accept, in addition to a natural-language string, a structured object mapping field names to a small set of composable constraints: `required`, `anyof` (closed value set), `number`, `json`, plus `desc` for the meaning
- `accepts`/`returns` added at the **root process** level — the outer contract toward whoever invokes the process; same form as `AGENT`
- `SPAWN.returns` and `DELEGATE.returns` accept the structured form as well as a string
- `doc/io-contracts.md` — design rationale for the contract model and the alternatives considered and rejected (full type system, `type`-valued constraints, `mode`/`fields` wrapper, conditional `when`, a `RETURN` construct, a `VARS` path registry)
- Spec section "Input/output contracts" and an "Agent behavior" note on how structured contracts are honored

### Changed
- Contracts are scoped explicitly to **context boundaries**: root process, `AGENT`, `SPAWN`, `DELEGATE`. `SUB` has no contract — it shares the caller's context. Invocation summary table updated accordingly
- String form of `accepts`/`returns` remains fully valid (open contract); the structured form is opt-in

---

## [0.5.0] — 2026-05

### Added
- `AGENT` instruction — declares a named agent with an explicit context boundary; fields: `name`, `description`, `model`, `role`, `accepts`, `returns`, `ROUTINE`; `accepts` and `returns` form the natural language contract between caller and agent
- `SPAWN` instruction — invokes an `AGENT` defined in the same file or imported via `IMPORT`; `with` seeds the agent's context, `returns` overrides the agent-level default for the specific call
- `IMPORT` updated — now makes both `SUB` definitions (available via `CALL`) and `AGENT` definitions (available via `SPAWN`) available after declaration
- Invocation summary table added to spec — compares `CALL`, `SPAWN`, and `DELEGATE` across context scope, definition style, and return semantics

---

## [0.4.0] — 2026-05

### Added
- `DELEGATE` instruction — spawns a sub-agent with an explicit context boundary; `with` describes what to extract from the current context and pass to the sub-agent, `returns` describes what flows back; distinct from `CALL` (shared context, explicit routine) in both scope and return semantics
- `model` and `role` fields now explicitly listed on `DELEGATE` in spec
- Agent behavior section updated: `DELEGATE` documented as the explicit mechanism for multi-agent delegation

---

## [0.3.6] — 2026-05

### Changed
- `LIBRARY` renamed to `IMPORT` — clearer action semantics; `LIBRARY` implied definition, `IMPORT` expresses consumption

---

## [0.3.5] — 2026-05

### Added
- `HALT` instruction — immediately stops the process with an optional message; distinct from `ONERROR` (controlled termination, not a failure)
- `WAITUSERINPUT` instruction — pauses execution, prompts the user for input, and continues with the response available as context; halts with the prompt text in non-interactive contexts

---

## [0.3.4] — 2026-05

### Added
- `role` field on root and `SUB` — natural language persona the agent adopts for that scope
- Same scoping rules as `model`: inner overrides outer
- `role` is a hint, not an imperative; the agent may fulfill it inline or via sub-agent spawning
- Multi-agent section updated: distinct `role` values are now an explicit trigger hint alongside `model`

---

## [0.3.3] — 2026-05

### Changed
- `WHEN`: spec now documents behavior honestly — predictable only with mutually exclusive conditions; overlapping conditions produce non-deterministic results depending on the agent
- `WHEN`: clarified primary use case (shared `else` with mutually exclusive conditions)
- `WHEN`: added recommendation to use sequential `IF` blocks when conditions may overlap
- DESIGN: rewrote `WHEN` rationale section — authoring vs executing distinction, honest scope of the format

---

## [0.3.2] — 2026-05

### Changed
- `RUN`: placeholders changed from `<...>` to `{{...}}` — unambiguous template syntax
- `RUN` description clarified: verbatim execution, `{{}}` as explicit escape hatch for dynamic parts
- DESIGN: added `TODO vs RUN` rationale section

---

## [0.3.1] — 2026-05

### Changed
- `REPEAT`: removed parallelization prescription — execution strategy belongs to the execution context, not the process definition

---

## [0.3.0] — 2026-05

### Changed
- `CASE` renamed to `WHEN` — same multi-match semantics, clearer keyword with no SQL/switch baggage

---

## [0.2.0] — 2026-05

### Added
- `LIBRARY` instruction for importing subroutines from external files
- `model` field with semantic tiers (`fast` / `balanced` / `smart`) and exact model ID support
- `CASE` instruction with multi-match semantics
- Parallelization behavior documented for `REPEAT foreach/for`
- `ref` field at root for linking to published spec

### Changed
- `ONERROR` now supports both instruction-level and root-level scope

---

## [0.1.0] — 2026-04

Initial internal spec. Core instructions: `TODO`, `IF`, `REPEAT`, `RUN`, `ONERROR`, `SUB`, `CALL`.
