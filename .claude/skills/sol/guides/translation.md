# Translation Guide — Converting Existing Formats to SOL

This guide applies when the input is an existing document (natural language description, pseudocode, YAML, XML) that must be converted into a SOL 0.6 script. For generating SOL from scratch based on a conversational description, the main process in SKILL.md applies directly.

---

## Input format identification

| Input | Treatment |
|---|---|
| Natural language prose | Extract semantic structure; identify phases, conditions, loops, agents |
| Pseudocode | Map control flow constructs directly to SOL equivalents |
| YAML workflow (e.g. GitHub Actions, Airflow DAGs) | Map jobs/tasks → steps, triggers → entry points, needs → sequencing |
| XML (e.g. BPMN, Ant, Maven) | Map tasks/activities → TODO or RUN, gateways → IF/WHEN, subprocesses → SUB or AGENT |
| Mixed / ambiguous | Treat as natural language |

---

## Semantic extraction checklist

Before writing any SOL, extract:

- [ ] Main phases and their natural order
- [ ] Steps that must be sequential vs. those that could be parallel
- [ ] All conditions — what triggers each branch?
- [ ] All loops — what iterates, what's the termination condition?
- [ ] Error paths — what happens when something fails?
- [ ] Human gates — where does a human need to review or approve?
- [ ] Agent roles — which steps require different cognitive modes?
- [ ] Reuse — are any sub-steps called more than once?

---

## Common translation patterns

### "For each X, do Y" → REPEAT foreach

```json
{
  "REPEAT": {
    "foreach": "item in the list",
    "ROUTINE": [
      { "TODO": "Process item" }
    ]
  }
}
```

### "If A then B, otherwise C" → IF

```json
{
  "IF": {
    "when": "A is true",
    "then": [{ "TODO": "B" }],
    "else": [{ "TODO": "C" }]
  }
}
```

### "Depending on type, do X / Y / Z" → WHEN

```json
{
  "WHEN": [
    { "when": "type is X", "then": [{ "TODO": "Handle X" }] },
    { "when": "type is Y", "then": [{ "TODO": "Handle Y" }] },
    { "else": [{ "TODO": "Handle default" }] }
  ]
}
```

### Shell command / CLI call → RUN

```json
{ "RUN": "git push origin {{branch-name}}" }
```

### Reusable helper → SUB + CALL

If a sequence of steps appears more than once, extract it as a SUB and replace each occurrence with CALL.

### "Delegate to specialized component" → AGENT + SPAWN or DELEGATE

When a step requires a distinct cognitive mode or a bounded context (the agent should not see the full workflow state), use AGENT+SPAWN (if reusable) or DELEGATE (if one-off). This holds even when the component is defined in another file: add an IMPORT and SPAWN it — do not downgrade a cross-file bounded call to a prose TODO just because the definition lives elsewhere.

### "Check X against the rules described in …" → judgment TODO citing a reference

When a step applies *declarative* criteria — rules, a policy, a spec, a style guide written in ordinary non-procedural prose — leave it as a TODO that cites that section by name. The criteria are the agent's cognitive input, not the program; forcing them into constructs would betray prose that is already in its correct form. The control flow (the iteration, the decision to accept/reject) stays in SOL; the rules stay in prose. Only when the cited "rules" are actually *procedural* (steps, ordering, nested conditions) must you lift them into constructs.

### Near-identical variants differing only by values → collection + REPEAT foreach

When the source spells out several blocks that share one shape and differ only by their values (three deploy steps, one per environment; a list of items each handled the same way), do not translate them into N duplicated SUBs/branches. Extract the values into a labelled collection — a JSON fence or table in the document hosting the script, citable by name — and walk it with one REPEAT foreach whose body is the shared shape. The loop item is the parameterization; residual per-item differences become a small IF inside the body or a field on the item. Static config like this belongs in the document (the agent reads it before executing); only values produced at runtime by another context are contracts rather than document data.

---

## Ambiguity resolution

When translating, surface these ambiguities before generating output:

1. **Sequential vs. parallel** — the source says "do A and B"; can they run at the same time?
2. **SUB vs. AGENT** — is the reusable step contextually dependent (SUB) or self-contained (AGENT)? And is a "cross-file call" a bounded contract (AGENT+SPAWN+IMPORT) or genuinely just shared-context steps?
2b. **Duplication vs. iteration** — are the repeated blocks one shape over different values (collection + REPEAT foreach) or genuinely distinct logic?
2c. **Reference vs. buried flow** — when a step points to an external prose section, is that section declarative (values or judgment criteria the agent applies — a legitimate reference, leave it as a TODO that cites it) or procedural (steps/decisions/order — buried control flow that must be lifted into constructs)? Test: deleting the section loses values, a criterion, or steps; only the last is a smell.
3. **IF vs. WHEN** — are the conditions mutually exclusive?
4. **Error handling** — what should happen on failure? Log and continue? Halt? Notify?
5. **WAITUSERINPUT suitability** — is the execution context guaranteed interactive?

Present ambiguities as numbered questions with recommended defaults before generating any SOL.
