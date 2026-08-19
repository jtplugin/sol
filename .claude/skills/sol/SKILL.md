---
name: sol
description: >
  Generate valid SOL 0.6 JSON scripts for any process, workflow, or multi-agent
  orchestration. Invoke proactively when the user describes a multi-step process,
  wants to automate or formalize a workflow, needs to orchestrate AI agents, or
  explicitly asks to write a SOL script. Also handles translation of existing
  documents (natural language, pseudocode, YAML, XML) into SOL.
---

# SOL Script Generator (SOL 0.6)

Design and generate SOL 0.6 JSON scripts — the canonical format for AI agent process
orchestration. This skill covers both generating SOL from scratch and translating existing
documents into SOL.

**Invoke:** `/sol [optional: file path or pasted content]`

**Proactive triggers:**
- User describes a multi-step process with sequencing, branching, loops, or error handling
- User wants to orchestrate multiple AI agents or delegate subtasks
- User asks to design, automate, formalize, or document a non-trivial workflow
- User says "create a SOL script", "write a SOL process", "make this a SOL workflow"

> **A note on this file's format.** This skill is written in prose, not as a SOL script,
> on purpose: it is a *methodology about writing SOL*, and that content reads as buried
> control flow when forced into SOL `TODO`s. The rationale and the general rule are in
> `guides/sol-vs-prose.md`. This is specific to meta/methodology processes — it is not a
> retreat from SOL, which remains the target for everything this skill produces.

---

## Operating stance

**Adopt the role of a SOL architect:** produce the leanest, clearest SOL representation that
preserves intent without over-engineering, and that exploits SOL's constructs to the letter
rather than describing structure in prose. Use a strong model for the judgment-heavy passes
below (segmentation, lifting control flow, contracts, emission, lint).

**Honor the request; advise, do not gatekeep.** When the user asks for SOL, produce SOL. If
SOL looks like a poor fit for what they described — a pure judgment checklist, a near-linear
methodology with no real branching — say so in one line and offer prose as an alternative,
then do what they decide. Never refuse to generate SOL because prose *might* fit better.
(See `guides/sol-vs-prose.md` for when each format wins.)

---

## Before you start — read the binding guides

Read the full SOL 0.6 specification in `spec/reference.md`, then `guides/authoring.md` (the
prescriptive refinement discipline) and `guides/contracts.md` (when and how to draw
`accepts`/`returns`). **These are binding:** the script you produce must obey them, not merely
resemble them. When a unit is hard to classify — a `TODO` that points at an external section,
a family of similar steps, a cross-file call — consult `guides/borderline-cases.md`, which
works these recurring ambiguities through the data/criteria/flow test.

Then determine the input source: (a) a file path the user passed, (b) text pasted inline, or
(c) a process described conversationally in the session. If the input is a document to
translate, also read `guides/translation.md`. If no input is clear, ask the user to describe
the process they want to formalize.

---

## The refinement method

Do not write final SOL in one shot. Refine a rough description through ordered passes; each
pass has a single concern. The full discipline (smell test, worked examples, the
data/criteria/flow rule) lives in `guides/authoring.md` — the summary here is the
orchestration, not a substitute for the guide.

- **Pass 0 — Narrative.** Restate the process as plain prose in execution order: what happens,
  in what sequence, with which decisions, loops, error paths, and human gates. Do not think
  about constructs yet. This is the rough draft the passes transform.

- **Pass 1 — Segment.** Cut the narrative into atomic, one-action fragments. A fragment still
  joining two actions ("and", "then") is not atomic — cut again. Control words ("if…", "for
  each…") stay as fragments for the next pass.

- **Pass 2 — Lift the control flow (the decisive pass).** Convert every control-word fragment
  into the construct that wraps its body: binary decision → `IF`; mutually-exclusive cases or
  a bulleted case list → `WHEN`; "for each" → `REPEAT foreach`; "while/until/N times" →
  `REPEAT while|until|for`; "on failure" → `ONERROR`; "ask/wait for the human" →
  `WAITUSERINPUT` or a process split; "this process is done, hand back up" → `RETURN`; "stop
  everything" → `HALT`. Move the body fragments
  *inside* the construct. After this pass, no `TODO` text may contain any phrase from the
  smell-test table in `authoring.md`. Nesting (an `IF` whose `then` holds a `WHEN`) is correct
  — do not flatten real structure back into prose.

- **Pass 3 — Classify leaves.** Each remaining leaf is a `RUN` (a verbatim command, with
  `{{placeholder}}` only for context-resolved parts) or a `TODO` (work needing judgment). If
  you would have to *describe how to assemble* the command rather than write it, it is a
  `TODO`.

- **Pass 4 — Collections, then boundaries.** *First* factor out the data: any family of
  near-identical units differing only by values (e.g. `rev_a`/`rev_b`/`rev_c`, one per env, or
  a manually chained next-step sequence) is a collection to iterate — **not** N duplicated
  SUBs/branches/setup steps. Replace it with one labelled collection + a single
  `REPEAT foreach` whose body is the shape written once; the loop item is the
  parameterization. Static, authoring-time config may live as a named JSON fence or table in
  the host document, cited by the `foreach` (optionally preceded by a "Read the `<name>`
  table" `TODO`, worth keeping when several tables exist). *Then* find boundaries: steps
  repeated in shared context → `SUB`+`CALL`; an isolated, reusable unit exchanging a contract
  → `AGENT`+`SPAWN` (+ `IMPORT` if defined elsewhere); a one-off isolated unit → `DELEGATE`.
  The deciding question is always *context*: does the work need the caller's context (`SUB`)
  or a clean one (`AGENT`/`DELEGATE`)? Apply this to **every** cross-unit call, including
  cross-file ones — a call into a bounded context that exchanges a defined in/out is
  `AGENT`+`SPAWN`, never a `TODO` "call the other skill"; the file the callee lives in only
  decides whether you need `IMPORT`. Keeping orchestration at one level with contract-less
  shells is allowed only as a stated, deliberate choice.

- **Pass 5 — Contracts.** At the root and every `AGENT`, decide whether a boundary carries
  information. **Mandatory case:** if an `AGENT` operates on a specific input and must return
  predictable information, the contract MUST be present (`accepts` for input, `returns` for
  the predictable output). Only a pure side-effecting worker may omit it. If it serves, draw
  it well; if not, leave it out — never decoration, never a needed one left implicit. Choose
  string (open) vs structured per `contracts.md`: structured only where getting a field wrong
  would break the machine, not the conversation. `SUB`s never get a contract. Honor every
  contract on both sides, at the right time: each `accepts` is validated at the top of its
  `ROUTINE` with a defined violation path (`RETURN` with the offending field, `ONERROR`, or a
  stated default — never silent, never `HALT`: a guard hands control back up, it does not kill
  the whole run), and this guard *is emitted*; for each `SPAWN`/`DELEGATE`, satisfy the callee's
  `accepts` at **authoring time** by reading its contract and writing a correct `with` (no
  emitted guard around your own `with`, never guessed — fetch the contract if you lack it),
  and emit only an `ONERROR` for a missing/malformed/off-contract response.

- **Pass 6 — `model` and `role`.** Assign `fast` to mechanical/repetitive leaves, `smart` to
  synthesis/ambiguous judgment/code generation, and omit `model` (balanced) elsewhere. Set
  `role` only where a persona measurably helps, at the highest scope where it applies (it is
  inherited).

Then **decide file structure and root form** using the reference's split heuristics: single
file for clean flows < 15 steps; split to `agents/<name>.json` when ≥ 2 named `AGENT`s; split
to `shared/<name>.json` when `SUB`s are reused. Use the **agent root form** (root = a single
`AGENT` key, name declared once inside) when the file's whole purpose is one reusable agent to
be imported and `SPAWN`ed; use the **process form** for a top-to-bottom script or any file
defining several agents or an agent plus an orchestrating routine. A file whose only purpose
is to export reusable `SUB`s/`AGENT`s for `IMPORT` uses the **library variant** of the process
form: its `ROUTINE` holds only definitions, no top-level executable steps, and it declares no
root `accepts`. Record the structural decision with a brief justification.

**Clarify before emitting.** If after the passes anything is genuinely ambiguous — sequential
vs parallelizable steps, `SUB` vs `AGENT` vs `DELEGATE`, `IF` vs `WHEN`, error-path behavior,
or whether the context is interactive enough for `WAITUSERINPUT` — ask the user, listing each
ambiguity as a numbered question with a recommended default, before generating output.

---

## Compliance check (wannabe-SOL) — trova problemi, non riscrivere

When the user asks you to **verify a candidate / wannabe SOL script** against the SOL 0.6
rules and the authoring discipline, run a compliance pass and output **only an issue list in
prose**. Do **not** emit a “better” script, do **not** propose a rewritten JSON, and do not
turn the findings into SOL — the deliverable is a report.

### Inputs and stance

- **Input**: a file path, pasted JSON, or a `.md` containing SOL JSON fences (same inputs the
  linter supports).
- **Goal**: enumerate defects and smells the script exhibits *as-is*, from “hard invalid” to
  “likely wrong / misleading”.
- **Non-goal**: producing the corrected script (even if the fix is obvious).

### How to reuse (not duplicate) the existing rules

- **Mechanical / deterministic checks** must follow `scripts/sol-lint.py` and the spec in
  `spec/reference.md`. If you can run the linter, do it; if you cannot, simulate its checks
  faithfully and call out uncertainty.
- **Judgment / authoring-discipline checks** must be grounded in the tests and smell tables in
  `guides/authoring.md` and the worked decisions in `guides/borderline-cases.md` and
  `guides/contracts.md`. Do not restate those guides; cite them as the basis of each finding.

### Output format (prose report)

Produce a compact list of findings. Each item should include:

- **Severity**: `ERROR` (invalid / will not run / violates binding rule), `WARN` (high-risk
  smell), `NOTE` (acceptable but worth review).
- **Location**: as specific as possible (construct name + a JSONPath-ish pointer, or the
  nearest enclosing `ROUTINE`/`AGENT`/`SUB` name).
- **Problem**: what is wrong *in the current script*.
- **Why it matters**: consequence at runtime or in maintainability.
- **Rule anchor**: a short reference like “spec/reference.md: <concept>”, “authoring.md: smell
  test”, “contracts.md: mandatory accepts/returns case”, or “sol-lint.py: <rule>”.
- **Minimal next action**: describe *what to change*, without writing the new JSON.

### What to check (two-layer audit)

#### Layer A — Mechanical correctness (deterministic)

Look for formal defects that a deterministic checker should catch (and, when possible, defer
to `scripts/sol-lint.py` output):

- **JSON / schema validity**: malformed JSON, unknown construct keys, missing required fields
  (e.g. missing `ROUTINE` where required), wrong root form.
- **Resolution**: unresolved `CALL`/`SPAWN`, missing/incorrect `IMPORT`, references to undefined
  `SUB`/`AGENT`.
- **Placeholders**: any single-brace `{x}` instead of `{{x}}`; placeholders that cannot resolve
  in scope; placeholders embedded in non-string positions when not allowed.
- **Control-flow integrity**: dead branches, unreachable steps, invalid `WHEN` shapes, invalid
  loop keys / missing collections for `REPEAT foreach`.
- **Contract surface**: `accepts`/`returns` fields malformed; guards missing where the script
  claims an `accepts` (if the guide marks it binding for that boundary).
- **RETURN vs structured `returns`**: under a structured `returns` contract (process root or
  `AGENT`), `RETURN` must echo the same top-level keys as an object; a string `RETURN` is a
  WARN (often intentional off-contract); a mismatched object is an ERROR. Open (string) `returns`
  imposes no shape check (`sol-lint.py`: `return-shape-mismatch`, `return-malformed`).

#### Layer B — Subtle compliance (AI judgment)

Look for defects that are “valid JSON” but non-compliant with the authoring discipline:

- **Buried control flow**: control words living inside `TODO` text instead of becoming `IF` /
  `WHEN` / `REPEAT` / `ONERROR` / `RETURN` / `HALT` / `WAITUSERINPUT` (use `guides/authoring.md` smell
  test).
- **Duplication vs iteration**: value-only duplication that should have been a labelled
  collection + `REPEAT foreach`.
- **Boundary mistakes**: `SUB` used where a clean-context `AGENT`+`SPAWN` is warranted (or
  vice-versa), or cross-file “calls” left as prose `TODO` instead of a real boundary plus
  `IMPORT`.
- **Contract misuse**: missing contracts where information crosses boundaries (mandatory case),
  contracts added as decoration, overly-structured contracts where open strings are safer, or
  caller not satisfying callee `accepts` (off-contract `with`).
- **Over/under-atomic steps**: leaves that combine multiple actions (“and/then”) or steps split
  so finely that they cannot be executed meaningfully.
- **Error handling intent mismatch**: missing/incorrect `ONERROR` around steps that obviously
  fail and need defined behavior; “happy path only” where the narrative implies otherwise.
- **Model/role misuse**: `model: smart` sprinkled on mechanical steps, or `fast` on synthesis;
  persona assigned too low/high scope.

---

## Emit, lint, write

1. **Emit** the SOL file(s) from the refined structure. The structure is already decided by
   the passes — this step only serializes it into valid SOL JSON. Do not reintroduce prose
   control flow here.

2. **Pass 7 — Self-lint before writing.** Re-read the script as the runtime agent and verify,
   in order, the full checklist in `authoring.md` → *Pass 7 — Lint*: no buried control flow /
   data / boundary (re-apply the smell test, including value-only duplication, identical
   duplicated sub-trees, and cross-file calls left as prose); `WHEN` only where branches are
   mutually exclusive; real loop keys with resolvable labelled collections; atomic leaves;
   contracts present where a boundary carries information and honored on both sides; every
   `{{…}}` resolving in scope with **double** braces in every field (no single-brace `{…}`); no
   dead branches; correct root form; every `CALL`/`SPAWN` resolving locally or via this file's
   own `IMPORT`. Fix any failure before writing.

3. **Write** the linted file(s) to disk. Base filename = the process name (e.g.
   `process-name.json`). Multi-file layout: main → `process-name.json`, agents →
   `agents/<name>.json`, shared routines → `shared/<name>.json`. If the user gave an output
   path, use it as the root.

4. **Pass 8 — Mechanical lint (deterministic gate).** Run the linter on every file written:

   ```bash
   python3 scripts/sol-lint.py <file.json>
   ```

   It exits non-zero when it finds **ERROR**-level defects — single-brace placeholders,
   unresolved `CALL`/`SPAWN`, malformed or unknown constructs, missing `ROUTINE`. These are not
   judgment calls: fix each at its structural root cause (do not patch the JSON to silence the
   check) and re-run until it exits clean. Then review the **WARN** findings: each is a prompt
   to re-read, not a verdict — apply the data/criteria/flow test. A `buried-flow` warning on
   real program steps, a `duplicate-subs` warning on value-only variants, a vague placeholder,
   a contracted `SPAWN` with no `ONERROR`, or an `AGENT.accepts` with no guard must be fixed; a
   warning on a legitimate declarative reference or a stated deliberate choice is acknowledged
   and left. Re-run the linter after any fix.

5. **Summarize:** files generated, which constructs were used and why, contracts drawn (and
   where deliberately omitted), the linter's final state (errors cleared, warnings resolved or
   consciously kept), assumptions made, and anything the user should review.

---

## Offer a diagram

After the files are generated, offer the user a diagram:

- **Mermaid** flowchart (`.mmd`, renderable at [mermaid.live](https://mermaid.live)):

  ```bash
  python3 scripts/sol2mermaid.py <file.json> [output.mmd]
  ```

- **draw.io** XML (`.drawio`, open in [app.diagrams.net](https://app.diagrams.net), then
  `Ctrl+Shift+H` for automatic vertical tree layout):

  ```bash
  python3 scripts/sol2drawio.py <file.json> [output.drawio]
  ```

For multi-file output, default to the main entry point unless the user names a file. If a
script is missing or Python is unavailable, generate the diagram manually from the SOL JSON.

---

## Supporting files

| File | Purpose |
|---|---|
| `spec/reference.md` | Full SOL 0.6 spec: all constructs, fields, selection rules, examples |
| `guides/authoring.md` | Prescriptive refinement discipline: the passes, the smell test, data/criteria/flow rules |
| `guides/contracts.md` | When and how to draw accepts/returns at context boundaries |
| `guides/borderline-cases.md` | Recurring ambiguities (reference vs buried flow, duplication vs iteration, cross-file calls) worked through the unifying test |
| `guides/translation.md` | Translation-specific guidance: input format mapping, extraction checklist, common patterns |
| `guides/sol-vs-prose.md` | When a process belongs in SOL vs prose; why this skill is prose; why json-in-md is a good pattern |
| `scripts/sol-lint.py` | Deterministic linter: the mechanical half of Pass 7/8. ERRORs = formal defects (single-brace placeholders, unresolved CALL/SPAWN, RETURN keys vs structured `returns`, malformed constructs); WARNs = heuristic smells (buried flow, value-only duplicated SUBs, missing ONERROR, string RETURN under structured `returns`). Lints a `.json` file or the `json` fences inside a `.md` |
| `scripts/sol2mermaid.py` | Converts a SOL JSON file to a Mermaid flowchart |
| `scripts/sol2drawio.py` | Converts a SOL JSON file to a draw.io XML diagram |

---

## Installation

```bash
# Personal install (available in all projects)
cp -r . ~/.claude/skills/sol-translate/

# Project install (this project only)
cp -r . .claude/skills/sol-translate/
```

Invoke with `/sol` in Claude Code.

---

## License

MIT License — see [LICENSE](./LICENSE)
