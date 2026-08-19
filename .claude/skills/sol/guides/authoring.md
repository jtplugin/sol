# Authoring Guide — From a rough description to well-structured SOL

This guide is the prescriptive core of the skill. It defines **how a process must be
described in SOL** and **how to refine a rough first draft into a final, well-structured
script**. It is not optional reading: when this skill generates SOL, it follows this
discipline to the letter. A SOL script that buries control flow in prose is a failed
generation, no matter how readable the prose is.

---

## The one rule everything else serves

> **Control flow lives in constructs, never in prose.**

Every decision, every branch, every iteration, every error path, every wait — each is a
*structural fact* of the process. SOL has a construct for each one. If that fact is
expressed as English (or Italian) sentences inside a `TODO`, the process is not encoded —
it is merely described, and the agent is left to re-derive the structure at runtime, every
time, possibly differently. That defeats the entire point of SOL.

A `TODO` describes **one unit of work that requires judgment, assuming the branch and the
iteration that lead to it have already been selected by the surrounding constructs.** It is
a *leaf*, not a flowchart.

### The companion rule — data lives in data, never in the control structure

> **A family of cases that differ only by their values is a collection to iterate over, never
> N duplicated branches, SUBs, or setup steps.**

Control flow in constructs is only half the discipline. The other half is its mirror: when
three near-identical units differ only by the values they carry (env, script name,
parameters), the *shape* is one thing and the *values* are data. Copying the shape three
times — three SUBs, three `WHEN` branches, three `TODO: "set x=…"` blocks — bakes the data
*into the control structure*, the same defeat as burying control flow in prose. The agent
re-derives the shared shape every time and the data is scattered across the script.

The fix is to **separate the data from the control**: declare the values as an explicit,
named collection and walk it with a single `REPEAT foreach` whose body is the shape, written
once. The loop item *is* the parameterization, visible and fresh on each iteration — no
hidden contract, no residual state carried between calls.

**Where the collection lives.** A SOL script is a *document* — typically a JSON fence inside
a markdown file — and the agent reads the whole document before executing. So a collection of
**static, authoring-time** values (configuration known when you write the script) may live in
the document around the script: a JSON fence, a markdown table, a CSV block. Two conditions
make the reference unambiguous:

1. **It must be labelled.** Give the data a name the construct can cite —
   `foreach: "each revision in the ElencoRevisioni table"`. A reference resolves only if the
   thing referenced has a name. Unnamed data + `{{the list}}` brings the ambiguity back.
2. **It must be static / authoring-time.** Config that exists when you write the document
   belongs in the document. A value *produced at runtime by another context* (a `SPAWN`
   result, an `accepts` input) is a **contract**, not document data — never park it in the
   markdown. (See `contracts.md`.)

**Optionally precede the loop with a reading step.** A `TODO: "Read the ElencoRevisioni table"`
before the `foreach` is *redundant on the execution plane* — the `foreach` already names the
data and the runtime already has the document in context. It is **not** a dead step to strip
in Pass 7; it is deliberate signalling. Keep it as a matter of style, and reach for it
especially **when the document holds more than one table or block**: there an explicit "read
*this* one" removes any doubt about which dataset the loop walks, for the human reading and
for the agent binding `{{item.field}}`. With a single obvious dataset it is optional; with
several it earns its place as disambiguation. Never make it mandatory — a "Read X" before
every reference would be noise.

### The companion rule, extended — criteria live in criteria too

The data rule has a sibling that is easy to miss, because it *looks* like the antipattern it
is not. A leaf `TODO` may legitimately cite an external prose section — and that is correct —
when what it cites is **reference knowledge: a criterion, a policy, a spec, a style guide**.
There are three different things that can sit behind a pointer to an external section, and
only one of them is a smell:

| What's behind the pointer | Its nature | The citing `TODO` is… |
|---|---|---|
| **Values** (table, list, fence) | data to walk | data → collection + `foreach` (the rule above) ✅ |
| **Rules / criteria** (what "valid" means) | declarative knowledge | the *input to a judgment leaf* → legitimate reference ✅ |
| **Flow** (steps, decisions, order) | the program | buried control flow → must be lifted into constructs ❌ |

The decisive distinction is **declarative vs procedural**:

- *Declarative* — "a document is conformant if it has a title, ISO dates, no empty section."
  It describes a **state to recognize**; the agent applies judgment. Pointing a `TODO` at it
  is right, and forcing such prose into SOL constructs would *betray* it — rules written in
  ordinary, non-procedural prose are already in their correct form.
- *Procedural* — "first open X, then if Y is missing do Z, repeat for each attachment." It
  describes a **sequence to execute**. That is the program; it belongs in constructs, not in a
  referenced section.

This is legitimate — the control flow is already fully in SOL (the `foreach` iterates, the
`TODO` is a genuine judgment leaf); the rules are the *standard against which* the agent
judges, its cognitive input, exactly like a spec handed to a worker:

```json
{
  "REPEAT": {
    "foreach": "documento nella cartella",
    "ROUTINE": [
      { "TODO": "Verifica se il documento è conforme alle regole descritte in ## Regole di conformità" }
    ]
  }
}
```

**Placement follows the same logic as data.** When the declarative artifact is more than a
sentence — a fill-in template, a long checklist, a multi-section spec — keep it *out* of the
leaf and host it as a **labelled section in the document**, then let the `TODO` cite it by
name: `TODO: "Write 00_spec.md following the ## Spec template"`. This is the criteria-side
mirror of the data rule: a long template inlined in a `TODO` bloats the leaf and buries a
reusable artifact inside one step, exactly as a values table inlined in a branch buries data.
A one-line criterion can stay inline; a substantial template/spec/checklist earns its own
named section and a one-line reference. Either way the `TODO` stays a lean judgment leaf.

**The trap:** the two disguise themselves. "Rules" can smuggle a process ("check A; *only
if* A passes, check B; *for each* attachment verify C") — and then, under the label
"criteria," you have carried the flow out of SOL again. The one test that settles all three
cases:

> *If I delete the cited section, have I lost values, a judgment criterion, or steps?*
> values → collection · criterion → legitimate reference · steps → lift into constructs

### The smell test

Re-read every `TODO` you write. If its text contains any of the following, it is wrong and
must be lifted into a construct:

| Phrase in the prose | What it really is | Construct |
|---|---|---|
| "if…", "se…", "when…", "in case…", "should X be…" | a decision | `IF` / `WHEN` |
| "depending on X", "a seconda di", "based on the kind/type/mode" | a case analysis | `WHEN` |
| "for each", "per ogni", "for every item in" | an iteration | `REPEAT foreach` |
| "while…", "until…", "keep …ing until", "repeat N times" | a loop | `REPEAT while/until/for` |
| "if it fails", "on error", "se va in errore", "otherwise log…" | an error path | `ONERROR` |
| "wait for approval", "ask the user", "once they confirm" | a human gate | `WAITUSERINPUT` (or process split) |
| a bulleted list of cases (`- kind==A: …` / `- kind==B: …`) | a `WHEN` written as a list | `WHEN` |
| "then…, then…, finally…" (several actions) | a sequence | several sibling instructions |
| near-identical units differing only by values (`rev_a`/`rev_b`/`rev_c`, one per env) | data baked into the control structure | a named collection + `REPEAT foreach` |
| the **same sub-tree of constructs** repeated across two branches/SUBs (identical tail, not just values) | a shared routine copied by hand | extract one `SUB` + `CALL` |
| "ask / tell / call <other agent or skill> and get back …" | a context boundary written as prose | `AGENT` + `SPAWN` (`IMPORT` if cross-file) |

A leaf `TODO` should read as a single imperative: *"Write the test script that exercises
{{entry.description}}."* — not *"If the file is missing, create a script that, depending on
the kind, does one of four things, reading env vars first."*

---

## The refinement passes

A process is authored in ordered passes. Do not try to write final SOL in one shot from a
rough description — go through the passes. Each pass has a single concern.

### Pass 0 — Narrative

Capture the process as plain prose, in execution order. Do not think about constructs yet.
The goal is only to have the whole story written down: what happens, in what order, with
what decisions and loops mentioned in natural language. This is the "rough description" the
user typically gives you, or that you reconstruct from the conversation.

### Pass 1 — Segment into atomic steps

Cut the narrative at every verb that introduces a distinct unit of work. Each fragment
becomes a *candidate instruction*. A fragment that still contains the word "and" joining two
actions, or a "then", is not atomic — cut again. After this pass you have a flat,
ordered list of one-action fragments. Some fragments are still control words ("if…",
"for each…") — that is expected; the next pass handles them.

### Pass 2 — Lift the control flow (the important one)

Walk the list. Every fragment that is a control word becomes a **construct that wraps** the
fragments under its scope:

- "if / unless / when (binary)"  → `IF` with `then` / optional `else`
- "depending on X" / a list of mutually-exclusive cases → `WHEN`
- "for each item in C" → `REPEAT { foreach }` wrapping the per-item steps
- "while C" / "until C" / "N times" → `REPEAT { while | until | for }`
- "on failure, do…" → `ONERROR` attached to the instruction that can fail
- "ask the human / wait for approval" → `WAITUSERINPUT`, or split the process (see below)
- "this process is done / nothing to do, return to caller" → `RETURN`
- "stop everything, abort the whole run" → `HALT`

The fragments that were the *body* of each control word move **inside** the construct's
`then` / `else` / `ROUTINE`. After this pass, no `TODO` text should contain any word from
the smell-test table. If one still does, you have not finished lifting.

**Nesting is normal and correct.** A binary decision whose `then` contains a case analysis
becomes an `IF` whose `then` holds a `WHEN`. Do not flatten a real nesting back into prose
to "keep it short" — depth in the structure is depth that was always in the process.

### Pass 3 — Classify each leaf: TODO vs RUN

For each leaf instruction:

- It is a **verbatim command** (a known CLI/shell/script invocation) → `RUN`, with
  `{{placeholder}}` only for the parts resolved from context. Everything outside `{{…}}` is
  passed exactly as written.
- It requires the agent to **decide, read, reason, or produce** something → `TODO`.
- If you would have to *describe how to assemble* the command rather than write it → it is a
  `TODO`, not a `RUN`.

### Pass 4 — Find the boundaries (SUB / AGENT / DELEGATE) and the collections

First, **factor out the data.** Before deciding boundaries, scan for families of
near-identical units that differ only by their values (the companion rule above). Replace each
family with one named collection + a single `REPEAT foreach`. Do this *before* the boundary
decision: it often dissolves an apparent need for three duplicated SUBs into one loop body,
and it keeps you from contracting a boundary that was really just iteration. A manually
chained sequence (`rev_a` sets `next=rev_b`, `rev_b` sets `next=rev_c`, …) is the same smell —
it is a `foreach` over a list of descriptors with the chaining made implicit by the loop.

Then find the boundaries. **Apply the context test to *every* call to another unit — and
especially to every call that crosses a file or skill.** Do not default a cross-file call to a
`TODO` because it is "elsewhere": a call into a bounded context that exchanges a defined
input/output *is* an `AGENT`+`SPAWN` (with `IMPORT` to bring the definition in), exactly as an
in-file one would be. Modelling such a call as `TODO "call the other skill"` is the
cross-boundary twin of burying an `IF` in prose.

- A sequence that appears **more than once** and needs the caller's full context → `SUB` +
  `CALL`.
- A unit that needs an **isolated context** (must not see the whole workflow state), exchanges
  a clear in/out contract, and is **reused** → `AGENT` + `SPAWN`. This holds whether the agent
  is defined in the same file or another one — cross-file just adds `IMPORT`.
- A **one-off** isolated unit not worth naming → `DELEGATE`.
- Shared or cross-file definitions → `IMPORT`.

The deciding question is always *context*: does this work need to see what the caller sees
(`SUB`), or should it start clean and exchange only a contract (`AGENT` / `DELEGATE`)? The
file the callee happens to live in never changes that answer — it only decides whether you
need an `IMPORT`. If the legitimate architectural choice is to keep all cross-unit
orchestration at one level and leave the called units as contract-less shells, that is
allowed — but it must be a stated, deliberate decision, not a boundary left as prose by
default.

### Pass 5 — Draw the contracts

At every context boundary you just created — the root process and every `AGENT` — decide
whether a contract is needed, and if so draw it. Contracts are **not** mandatory in general —
a boundary that carries no information needs none. But there is one case where they **are**
mandatory: *if an `AGENT` operates on a specific input and must return predictable
information, the contract MUST be present.* Specific input ⇒ declare `accepts`; predictable
output a later step relies on ⇒ declare `returns`. The only agent that may omit a contract is
the pure side-effecting worker (no specific input, no consumed output). The rule overall: *if
it serves, it must be there and done well; if it does not, leave it out* — never a half-drawn
contract added for decoration.

A contract also implies **handling its violation, on both sides of the boundary.** A declared
contract that is never checked is a false guarantee, so in the same pass add:

- **Callee side (runtime, emitted)** — every `AGENT`/root with an `accepts` begins its
  `ROUTINE` by validating the *incoming* input and defining what happens when it is invalid
  (`RETURN` naming the offending field, local `ONERROR`, or a stated default — never silent,
  never improvised, never `HALT`: a failed guard hands control back to the invoker, it does
  not abort the whole run).
- **Caller side, input (authoring-time, NOT emitted)** — when you write a `SPAWN`/`DELEGATE`,
  read the callee's `accepts` and write a `with` that genuinely satisfies it. This is your
  check, performed now by reading the contract — do **not** emit a runtime guard around the
  outgoing `with`, and do not hallucinate `with` if the callee's contract is not in context
  (fetch it first).
- **Caller side, response (runtime, emitted)** — attach an `ONERROR` for the case where the
  callee returns nothing, something malformed, or off-contract.

**`RETURN` and the `returns` contract.** A process normally finishes by reaching the end of its
`ROUTINE`; its declared output is produced *by other means* (a written file, a sent message), so
no explicit `RETURN` is needed at the natural end — adding one there is noise. Use `RETURN` for
an **early** exit, or when the output is a literal value the invoker must receive in hand. In
that case the rule is **echo the contract**: the `RETURN` value mirrors the *form* of `returns`
— a string contract → a string; a structured `returns: {a, b}` → an object `{a, b}` with the
same keys, filled (typically via `{{placeholder}}` pulling named values from scope). Do **not**
restate the contract's schema inside `RETURN`; the contract at the top stays the single source
of truth. A `RETURN` whose shape does *not* match the contract is, by construction, the
invoker's signal that something went off-contract — handle it on the caller side with `ONERROR`.

See `contracts.md`.

### Pass 6 — Assign `model` and `role`

- `fast` for mechanical/repetitive leaves; `smart` for synthesis, ambiguous judgment, code
  generation; `balanced` (the default) otherwise — omit it rather than writing `balanced`.
- `role` only where a specific persona measurably improves the output. It is inherited by
  nested scopes, so set it at the highest scope where it applies.

### Pass 7 — Lint

Re-read the whole script as if you were the runtime agent. Check, in order:

1. **No buried control flow, no buried data, no buried boundary.** Re-apply the smell test to
   every `TODO` and `RUN`. Zero hits — including the companion smells: a family of
   value-only variants that should be a named collection + `REPEAT foreach`; an **identical
   sub-tree of constructs** repeated across two branches or SUBs (the *same shape*, not just
   values — e.g. a `SPAWN` + `WHEN` dispatch tail copied verbatim into two SUBs) that should
   be extracted to one `SUB` + `CALL`; and a cross-unit or cross-file call written as prose
   that should be `AGENT`+`SPAWN` (`IMPORT`).
2. **IF vs WHEN.** `WHEN` only where branches are mutually exclusive (or co-activation is
   genuinely intended and the author accepts agent-dependence). Overlapping conditions that
   need predictable behavior → sequential `IF` blocks instead.
3. **Loop keys and their data.** `foreach` has a real collection; `while`/`until` have a real
   condition; `for` has a count. The body does one item / one iteration — it does not re-loop
   in prose. A `foreach` over static data names a **labelled** collection that resolves in
   scope (a document table/fence or a prior step). If the document holds more than one such
   dataset, a preceding `TODO: "Read the <name> table"` disambiguates which one — keep it.
4. **Leaves are atomic.** No `TODO` chains three actions with "then". Split them.
5. **Contracts** present wherever a boundary carries information (and absent where it does
   not), structured only where it earns its place, never half-drawn. And every contract is
   honored on both sides, at the right time: each `accepts` is validated at the top of its
   `ROUTINE` with a defined violation path (emitted); each `SPAWN`/`DELEGATE` `with` was
   written by reading the callee's `accepts` (authoring-time, no emitted guard, not guessed)
   and handles a bad/missing response via `ONERROR` (emitted).
6. **Placeholders.** Every `{{…}}` resolves from something in scope; no single-brace `{…}`.
7. **Dead branches removed.** A case that the surrounding guard makes impossible is a
   precondition, not a branch — state it in the parent `description`, do not encode it.

If any check fails, return to the pass that owns it. Generation is done only when Pass 7 is
clean.

---

## Worked example — turning the antipattern into SOL

This is the exact kind of input this skill must never reproduce, and the transformation it
must always perform.

### Before — everything crammed into one `TODO` (wrong)

```json
{
  "TODO": "If the file {entry.script_path} does not exist on disk:\n  Create the file with a working test script for mode.kind={entry.mode.kind}.\n  - kind == RUN: Python script that exercises the functionality in {entry.description}, exit 0 if OK\n  - kind == API: Python script that calls the endpoint and checks the response, exit 0 if 2xx\n  - kind == WEB: Playwright script that drives the described UI flow, exit 0 if OK\n  - kind == CHK: never created here (script_path is null for CHK)\n  Read env vars from {repo_root}/.envtest with the test's env prefix (e.g. CODING_ for env=coding).\n  Use load_envtest().\n\nIf the file already exists (rework):\n  Do not overwrite, unless a gap was flagged on that file in the previous cycle."
}
```

What is wrong:
- A **binary decision** (file exists / does not exist) written as prose → must be `IF`.
- A **four-way case analysis** on `mode.kind` written as a bulleted list → must be `WHEN`.
- **Several actions** (create file, read env, use helper) chained in one leaf → must be
  separate instructions.
- A **dead branch** (`kind == CHK` "never created here") encoded as a case → it is a
  precondition, not a branch.
- The whole thing is presumably **inside a per-item loop** that the prose hides.

### After — control flow in constructs (correct)

```json
{
  "REPEAT": {
    "foreach": "entry in the test plan whose mode.kind is RUN, API, or WEB",
    "ROUTINE": [
      {
        "IF": {
          "when": "no file exists at {{entry.script_path}}",
          "then": [
            {
              "WHEN": [
                {
                  "when": "entry.mode.kind == RUN",
                  "then": [{ "TODO": "Write a Python test script at {{entry.script_path}} that exercises the functionality described in {{entry.description}} and exits 0 on success", "model": "smart" }]
                },
                {
                  "when": "entry.mode.kind == API",
                  "then": [{ "TODO": "Write a Python script at {{entry.script_path}} that calls the endpoint and asserts a 2xx response, exiting 0 on success", "model": "smart" }]
                },
                {
                  "when": "entry.mode.kind == WEB",
                  "then": [{ "TODO": "Write a Playwright script at {{entry.script_path}} that drives the UI flow described in {{entry.description}} and exits 0 on success", "model": "smart" }]
                }
              ]
            },
            { "TODO": "In the script just written, load env vars from {{repo_root}}/.envtest using the test's env prefix (e.g. CODING_ for env=coding) via load_envtest()" }
          ],
          "else": [
            {
              "IF": {
                "when": "a gap was flagged on {{entry.script_path}} in the previous cycle",
                "then": [{ "TODO": "Rework the existing script at {{entry.script_path}} to close the flagged gap, preserving the parts that already pass", "model": "smart" }],
                "else": [{ "TODO": "Leave {{entry.script_path}} unchanged" }]
              }
            }
          ]
        }
      }
    ]
  }
}
```

Note how the `CHK` case disappeared: the `foreach` target excludes it (its `script_path` is
null), so it is a precondition stated in the loop target, not a branch. That is Pass 7,
check 7 in action.

The result is longer in lines but shorter in *ambiguity*: the agent no longer re-derives the
structure — it executes it. That is the trade SOL is built on.

---

## Worked example — value-only variants become data + one loop

The mirror antipattern: not control flow in prose, but **data baked into the control
structure**.

### Before — three near-identical SUBs, one per revision (wrong)

```json
[
  { "SUB": { "name": "rev_a", "ROUTINE": [
    { "RUN": "deploy.py --env coding --script rev_a.py" },
    { "CALL": "rev_b" }
  ]}},
  { "SUB": { "name": "rev_b", "ROUTINE": [
    { "RUN": "deploy.py --env staging --script rev_b.py" },
    { "CALL": "rev_c" }
  ]}},
  { "SUB": { "name": "rev_c", "ROUTINE": [
    { "TODO": "Final revision: no deploy, signal done" }
  ]}}
]
```

What is wrong: one shape copied three times, the values (`env`, `script`) cabled into each
copy, and the sequence chained by hand (`rev_a` → `rev_b` → `rev_c`). The differences are
*data*, not structure.

### After — a labelled collection in the document + one `foreach` (correct)

Declared in the markdown around the script — static, authoring-time, named:

````markdown
## ElencoRevisioni

```json
[
  { "id": "A", "env": "coding",     "script": "rev_a.py", "deploy": true },
  { "id": "B", "env": "staging",    "script": "rev_b.py", "deploy": true },
  { "id": "C", "env": "production", "script": "rev_c.py", "deploy": false }
]
```
````

And the loop, in the ROUTINE:

```json
[
  { "TODO": "Read the ElencoRevisioni table" },
  {
    "REPEAT": {
      "foreach": "each revision in the ElencoRevisioni table",
      "ROUTINE": [
        {
          "IF": {
            "when": "{{revision.deploy}} is true",
            "then": [{ "RUN": "deploy.py --env {{revision.env}} --script {{revision.script}}" }]
          }
        }
      ]
    }
  },
  { "TODO": "Signal that all revisions are done" }
]
```

The chaining disappears — the loop sequences the items. The `deploy: false` case is a field
tested by a small `IF` in the body, not a third copy of the shape. The leading
`TODO: "Read the ElencoRevisioni table"` is redundant for the runtime but kept here as
signalling, and it would be *worth keeping* if the document held several tables. There is no
hidden contract: the SUBs shared context implicitly through hand-set values; the `foreach`
binds each item openly and freshly.

---

## Quick reference — phrase → construct

| You wrote / heard | Use |
|---|---|
| "do X" needing judgment | `TODO` |
| exact command to run | `RUN` |
| "if A then B else C" | `IF` |
| "depending on the kind/type/state" (exclusive cases) | `WHEN` |
| "for each item" | `REPEAT { foreach }` |
| "while / until / N times" | `REPEAT { while | until | for }` |
| "on failure, …" | `ONERROR` |
| "ask / wait for the human" | `WAITUSERINPUT` or process split |
| "this process is done / return to caller" | `RETURN` |
| "stop everything / abort the whole run" | `HALT` |
| reused steps, shared context | `SUB` + `CALL` |
| isolated reusable unit with a contract (same file or another) | `AGENT` + `SPAWN` (+ `IMPORT` if cross-file) |
| one-off isolated unit | `DELEGATE` |
| load definitions from a file | `IMPORT` |
| N near-identical units differing only by values | named collection + `REPEAT foreach` |
| static config the script iterates over | a labelled table/fence in the document, cited by name |
