# SOL Borderline Cases — When the Rules Meet Reality

The authoring discipline states two cardinal rules:

1. **Control flow lives in constructs, never in prose.**
2. **Data lives in data, never in the control structure** (and its sibling: *criteria live in criteria*).

Stated baldly, they sound absolute: never point a `TODO` at an external section, never write prose where a construct fits. But real scripts are full of cases that *look* like violations and are not — and cases that *look* clean and hide a violation. These borderline cases are not exceptions to the rules; they are where the rules earn their precision. Each one below sharpened the rule rather than weakening it.

This document collects them so the distinctions survive contact with real documents.

---

## The unifying test

Every borderline case in this document reduces to one question about a pointer or a piece of prose:

> **If I delete this, what have I lost — values, a judgment criterion, or steps?**
>
> - **values** → it is data → a labelled collection the `foreach` walks
> - **criterion** → it is declarative knowledge → a legitimate reference cited by a judgment `TODO`
> - **steps** → it is the program → buried control flow → lift it into constructs

The whole skill turns on telling these three apart. The mistake is treating any reference to an external section as a smell. The correct stance is to classify *what sits behind the pointer*.

---

## Case 1 — Value-only variants that look like distinct subroutines

**Looks like:** several SUBs/branches, one per environment or revision, each genuinely "its own thing."

**Actually is:** one shape over a table of values.

```text
deploy rev_a to dev
deploy rev_b to staging
deploy rev_c to prod (disabled for now)
```

The tell: you can describe two of them as *"the same thing but with X different."* X is the data; the thing is the loop body. Three SUBs become one labelled collection in the host document plus a single `REPEAT foreach`; the residual difference (prod disabled) becomes a field on the item, handled by an `IF` in the body. Adding `rev_d` is then a table row, not new control flow.

**Why it reinforces the thesis:** duplicated structure is data that put on a costume. Collapsing it to a loop is the data rule doing exactly its job — pulling values out of the control skeleton.

> Full worked example in `authoring.md` → *value-only variants become data + one loop*.

---

## Case 2 — A `TODO` that cites an external prose section of *rules*

**Looks like:** buried control flow — "the real logic lives outside the JSON."

**Actually is:** a judgment leaf citing declarative knowledge.

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

Here the control flow is *already fully in SOL*: the `foreach` iterates, the `TODO` is a genuine unit of judgment. The cited section — "a document is conformant if it has a title, ISO dates, no empty section" — is **declarative**: it describes a *state to recognize*, not a *sequence to execute*. It is the agent's cognitive input, exactly like a spec handed to a worker. Forcing such prose into constructs would betray it; rules written in ordinary non-procedural prose are already in their correct form.

**Long artifacts go in a labelled section, not inside the leaf.** A one-line criterion can sit inline in the `TODO`. But when the declarative knowledge is bulky — a fill-in template, a long checklist, a multi-section spec — host it as a *named section in the document* and have the `TODO` cite it by name (`"…following the ## Spec template"`), exactly as the data rule hosts a values table. Inlining a whole template in a `TODO` keeps the reference legitimate but bloats the leaf and hides a reusable artifact inside one step. Same membrane as data: substance in a named section, a lean pointer in the leaf.

**Why it reinforces the thesis:** the rule was never "prose is forbidden." It was "the *program* must not hide in prose." A judgment criterion is not the program. This case forced the binary (data vs flow) to become a ternary (values vs criteria vs flow).

---

## Case 3 — A `TODO` that cites an external section that *is actually a process*

**Looks like:** clean SOL — the JSON is short, every branch is a tidy `TODO`.

**Actually is:** the hybrid antipattern. The flow has been *moved out* of the JSON, not removed.

```json
{
  "WHEN": [
    { "when": "tipo è story",      "then": [{ "TODO": "Segui le istruzioni in ## Orchestrazione story" }] },
    { "when": "tipo è functional", "then": [{ "TODO": "Segui le istruzioni in ## Orchestrazione functional" }] }
  ]
}
```

The cited sections are not values and not criteria — they are *steps, decisions, ordering*: a program. The short JSON is deceptive; deleting the section loses the program. This is "control flow lives in constructs, never in prose," merely disguised as a bibliographic reference instead of inline prose.

**The fix is chosen by the context test, not by reflex.** Lifting the flow into SOL is mandatory; the construct is not always a SUB:

- flow that lives in the dispatcher's context, reused → **SUB + CALL**
- isolated unit exchanging a contract → **AGENT + SPAWN** (+ `IMPORT` if defined in another file)
- one-off, isolated → **DELEGATE**

**Why it reinforces the thesis:** it shows that "short and clean-looking" is not the metric. The metric is whether the *program* is inspectable in constructs. A pointer to a procedure is still buried control flow.

---

## Cases 2 vs 3 side by side — the declarative/procedural line

| | Case 2 — reference (ok) | Case 3 — buried flow (smell) |
|---|---|---|
| Cited section describes | a **state to recognize** | a **sequence to execute** |
| Grammar | declarative ("X is valid if…") | procedural ("first…, then…, for each…") |
| The agent | applies judgment | follows steps |
| In SOL terms | a leaf `TODO` + its criterion | a missing SUB/AGENT/DELEGATE |
| Delete the section, you lose | a criterion | the program |

**The trap:** the two disguise themselves as each other. "Rules" can smuggle a procedure: *"check A; only if A passes, check B; for each attachment verify C."* The moment a criterion section contains ordering and nested conditions, it has become flow under a declarative label — and Case 2 has turned into Case 3. Read what is actually behind the pointer; do not trust the heading.

---

## Case 4 — A cross-file call written as a prose `TODO`

**Looks like:** a reasonable instruction — "call the other skill to do Y."

**Actually is:** an unmarked boundary. A call into a bounded context that exchanges a defined input/output is `AGENT + SPAWN`, never a prose `TODO`. The file the callee lives in only decides whether you also need `IMPORT` — it never downgrades the call to prose.

**Why it reinforces the thesis:** these are agents in dialogue with a contract. The boundary, the input, and the predictable output are exactly the things SOL exists to make inspectable. A prose `TODO` erases all three.

---

## Case 5 — The redundant-but-clarifying read step

**Looks like:** dead weight — `{ "TODO": "Read the ElencoRevisioni table" }` before a `foreach` that already cites it. The agent reads the whole document first, so on the execution plane it is redundant.

**Actually is:** legitimate signalling, and it becomes *important* when the host document holds more than one table — it tells the runtime which collection the `foreach` binds to, removing ambiguity for both the human reader and the agent.

**Why it reinforces the thesis:** the rules optimize for an agent that *acts on what it reads*. Redundancy that removes ambiguity serves that agent. Keep it when several datasets coexist; drop it when there is only one.

---

## Case 6 — A `TODO` that classifies *and then acts on the class*

**Looks like:** a single judgment leaf — "classify the test case as A, B, or C."

**Actually is:** a judgment leaf *plus* buried branches. The classification itself is genuine judgment and belongs in a `TODO`. But the moment the same prose continues *"…if B, verify the contract is stable, and if so flag it; if C, record the failing test's path,"* the per-class consequences are control flow wearing the costume of "notes on the classification."

```text
Classify the case: A (missing test) | B (test exists but inadequate) | C (regression).
If B: check that fixing the test won't touch a stable contract; if so, flag it.
If C: note the path of the failing test, then pass the array on.
```

The fix splits the leaf from the branching: a `TODO` that *only* classifies and records the class, followed by a `WHEN` on the class whose branches carry the per-class actions. The "if B…", "if C…" are not annotations — they are the smell-test's `se…` → `WHEN`, and the trailing "then pass the array on" is a separate sibling step.

**Why it reinforces the thesis:** "judgment" is not a license to bury the consequences of that judgment. The criterion (what makes a case A/B/C) is declarative and may be referenced; the *reaction* to each class is flow and must be lifted into constructs.

---

## Case 7 — A `WHEN` on a `SPAWN` result used as the error handler

**Looks like:** the failure case is covered — the `WHEN` after the `SPAWN` has an `else`, so "everything else" is handled.

**Actually is:** two different membranes collapsed into one. The `WHEN` dispatches on the *values the agent returned* (`ok` / `ambiguous` / `ko`); its `else` catches an *unexpected value*. None of that fires when the `SPAWN` itself **fails, returns nothing, or returns off-contract** — that is the `ONERROR`'s job, and it is missing.

```json
{ "SPAWN": "censor", "with": "…" },
{ "WHEN": [
  { "when": "censor_result.result == 'ok'", "then": [ /* … */ ] },
  { "else": [ { "CALL": "spec_blocked" } ] }
]}
```

The `else → spec_blocked` reads like a catch-all, but it presumes `censor_result` exists and merely carries an unexpected value. Add an `ONERROR` to the `SPAWN` for the dead-call case; keep the `WHEN`/`else` for the live-but-unexpected value. See `contracts.md` → *A `WHEN`/`IF` on the result is not the `ONERROR`*.

**Why it reinforces the thesis:** SOL distinguishes "the boundary produced a wrong answer" from "the boundary produced no answer." Conflating them hides a real failure mode behind a data branch.

---

## How to use this document

When a script feels borderline, do not ask "does this break a rule?" — ask the unifying test. Locate the case above that matches the shape in front of you, confirm the classification with the test, and apply the indicated move. If none matches cleanly, you are probably looking at a *mix* (a criterion section that has grown a procedure, a collection that has grown distinct per-item logic) — split it along the test's three axes until each piece is unambiguously values, criteria, or flow.
