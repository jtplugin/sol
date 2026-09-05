---
name: fixture-w2-support-intake
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a senior support triage lead who classifies incoming issues against a fixed product catalog and assigns them within a finite hour budget."
description: "W2 branching fixture with state accumulation across iterations. Triages a queue of ~15 support items against a finite hour budget in a single invocation. The same item, in a different position in the queue, takes a different branch, because the hour accumulator has changed -- the model must actually execute the process, not classify items independently. Per-item EVAL/BRANCH trace lines make comprehension (product+intent vs ground truth), conditional fidelity (control-flow given the model's own classifications), and end-to-end outcome (everything vs ground truth) separately scoreable."
ref: "https://github.com/jtplugin/sol"
accepts:
  queue_path:
    required: true
    desc: "path to a JSON file staged by the runner; fields: queue (array of {id, title, body}, ~15 items, no product/intent -- the model must classify them)"
returns:
  status:
    anyof: ["OK", "INVALID_INPUT"]
    required: true
    desc: "OK for a normally processed queue; INVALID_INPUT if queue_path was missing, unreadable, or the queue array/items were malformed"
  items:
    json: true
    required: true
    desc: "one entry per queue item actually processed, in order: {id, product, intent, hours, action}. Empty array if status is INVALID_INPUT."
  remaining_hours:
    number: true
    required: true
    desc: "hours left in the 20-hour budget after the last processed item. null if status is INVALID_INPUT."
  halted_at:
    required: true
    desc: "id of the item whose ESCALATE condition stopped the queue early, or null if the queue was fully processed (or if status is INVALID_INPUT)"
---

# Support intake triage task

## File content

```json
{{file_content}}
```

## Product catalog

```json
{
  "products": [
    { "id": "P1", "name": "Solidus",  "persona": "a cryptocurrency full-node and wallet client: consensus rules, peer-to-peer networking, transaction relay, wallet key management." },
    { "id": "P2", "name": "Lucent",   "persona": "a JavaScript library for building user interfaces: component rendering, the virtual DOM, hooks, server-side rendering." },
    { "id": "P3", "name": "Meridian", "persona": "a cross-platform source code editor: the text-editing core, extensions/plugins, debugging integration, the integrated terminal." },
    { "id": "P4", "name": "Aperture", "persona": "a computer-vision and image-processing library: image I/O, filters and transforms, camera calibration, video analysis." },
    { "id": "P5", "name": "Tensora",  "persona": "a machine-learning framework: tensor operations, automatic differentiation, model training and serving, GPU/accelerator support." }
  ],
  "hours_table": {
    "P1": { "BUG": 3, "FEATURE": 5, "QUESTION": 1 },
    "P2": { "BUG": 2, "FEATURE": 4, "QUESTION": 1 },
    "P3": { "BUG": 2, "FEATURE": 4, "QUESTION": 1 },
    "P4": { "BUG": 3, "FEATURE": 5, "QUESTION": 1 },
    "P5": { "BUG": 3, "FEATURE": 5, "QUESTION": 1 }
  },
  "budget_hours": 20
}
```

## The procedure

### What it does

- Run exactly: `cat {{queue_path}}` [from context: queue_path]
- If queue_path was not provided, the file could not be read, the content has no 'queue' array, or any queue item is missing 'id', 'title', or 'body', then:
  - Emit verbatim: [fixture-w2-support-intake][main] BRANCH: guard status=INVALID_INPUT
  - End this process and hand control back to whoever invoked it, yielding: {"status": "INVALID_INPUT", "items": [], "remaining_hours": null, "halted_at": null}
- Set remaining_hours to 20 (the budget_hours value from the product catalog above). Set halted_at to null. Set items to an empty list.
- Define the subroutine «classify-request» — see *Subroutines* below.
- Define the subroutine «estimate-effort» — see *Subroutines* below.
- Define the subroutine «check-budget» — see *Subroutines* below.
- For each item in the queue array, in the given order:
  - Call the subroutine «classify-request», which sees everything this process sees.
  - If product is UNKNOWN, then:
    - Append {"id": item.id, "product": "UNKNOWN", "intent": intent, "hours": null, "action": "NEEDS_INFO"} to items. Do not change remaining_hours.
    - Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=NEEDS_INFO remaining={{remaining_hours}} [from context: item.id, remaining_hours]
  - Otherwise:
    - Call the subroutine «estimate-effort», which sees everything this process sees.
    - Call the subroutine «check-budget», which sees everything this process sees.
    - Depending on the case:
      - When intent is BUG and budget_state is NOFIT:
        - Set halted_at to item.id.
        - Append {"id": item.id, "product": product, "intent": intent, "hours": hours, "action": "ESCALATE"} to items. Do not change remaining_hours.
        - Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ESCALATE remaining={{remaining_hours}} [from context: item.id, remaining_hours]
        - Build the result as JSON: {"status": "OK", "items": {{items}}, "remaining_hours": {{remaining_hours}}, "halted_at": {{halted_at}}}. JSON ONLY, no other fields, exact key casing. The EVAL and BRANCH lines are not part of it. [from context: items, remaining_hours, halted_at]
        - End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]
      - When budget_state is FITS:
        - Subtract hours from remaining_hours.
        - Append {"id": item.id, "product": product, "intent": intent, "hours": hours, "action": "ASSIGN"} to items.
        - Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ASSIGN remaining={{remaining_hours}} [from context: item.id, remaining_hours]
      - Otherwise:
        - Append {"id": item.id, "product": product, "intent": intent, "hours": hours, "action": "DEFER"} to items. Do not change remaining_hours.
        - Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=DEFER remaining={{remaining_hours}} [from context: item.id, remaining_hours]
- Build the result as JSON: {"status": "OK", "items": {{items}}, "remaining_hours": {{remaining_hours}}, "halted_at": {{halted_at}}}. JSON ONLY, no other fields, exact key casing. The EVAL and BRANCH lines are not part of it. [from context: items, remaining_hours, halted_at]
- End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]

### Subroutines

#### The subroutine «classify-request»

**What it does:**

- Using ONLY the product catalog persona descriptions above, read the current item's title and body. Set product to the single best-matching product id (P1, P2, P3, P4, or P5). If no product plausibly matches, set product to UNKNOWN.
- Read the current item's title and body. Set intent to exactly one of BUG, FEATURE, QUESTION -- what the issue is asking for, independent of which product it is.
- Emit verbatim, filling the placeholders with the values just set: [fixture-w2-support-intake][main] EVAL: item={{item.id}} product={{product}} intent={{intent}} [from context: item.id, product, intent]

#### The subroutine «estimate-effort»

**What it does:**

- Look up hours_table[product][intent] in the product catalog above. Set hours to that number exactly -- this is a fixed lookup, not an estimate you make yourself.

#### The subroutine «check-budget»

**What it does:**

- If hours is less than or equal to remaining_hours, then:
  - Set budget_state to FITS.
- Otherwise:
  - Set budget_state to NOFIT.
