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

You are triaging a queue of incoming support items against a fixed hour budget. The queue is a
JSON document, found at the path given as `queue_path`, holding a `queue` array whose entries
each have an `id`, a `title` and a `body`. The product catalog gives you five products with a
short persona for each, a table of how many hours a piece of work costs for a given product and
intent, and the size of the budget you are spending.

### First, check that you can work at all

If no `queue_path` was given to you, or the file at it cannot be read, or what it contains has
no `queue` array, or any item in that array is missing its `id`, its `title` or its `body`, then
the run is over before it starts. Emit this line:

[fixture-w2-support-intake][main] BRANCH: guard status=INVALID_INPUT

and return this object, with exactly these four keys and no others:

{"status": "INVALID_INPUT", "items": [], "remaining_hours": null, "halted_at": null}

Nothing further is done in that case. Everything below assumes the queue is sound.

### Set yourself up

You have twenty hours to spend — the budget from the product catalog. As you go you build a
record of the items you have handled, one entry per item, in the order you handled them; it
starts out empty. Nothing has stopped the queue, and unless something does, nothing will.

### Work through the queue, one item at a time

Take the items in the order the array gives them. What follows is the work for a single item.
When you have finished one item, unless that item stopped the queue, go back to the start of
this section and take the next one, carrying forward the hours you have left and the record you
have built so far. Both change as you go, which means the same item can be handled differently
depending on where in the queue it sits.

**Classify it.** Using only the persona descriptions in the product catalog, read the item's
title and body and pick the single best-matching product id: P1, P2, P3, P4 or P5. If none of
them plausibly matches, the product is UNKNOWN. Then, from the same title and body, decide what
the item is asking for — exactly one of BUG, FEATURE or QUESTION — judged on its own, whichever
product it turned out to concern.

Emit this line, putting the item's id, the product id you settled on and the intent you settled
on in place of the three placeholders:

[fixture-w2-support-intake][main] EVAL: item={{item.id}} product={{product}} intent={{intent}}

**If the product came out UNKNOWN**, there is nothing to cost and nothing to spend. Add an entry
to the record carrying the item's id, the product "UNKNOWN", the intent you decided on, hours of
null, and the action "NEEDS_INFO". The hours you have left do not change. Emit this line, with
the item's id and the hours you have left in place of the placeholders:

[fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=NEEDS_INFO remaining={{remaining_hours}}

That is all for this item.

**If the product is one of the five**, find what it costs: look in the hours table under that
product and that intent, and take the number you find there exactly as it stands. It is a
lookup, not an estimate of your own. Then one of the following three applies to the item.

*A bug that no longer fits.* The intent is BUG and the cost is greater than the hours you have
left. This item stops the queue. First note that it is the item that stopped it. Then add an
entry to the record carrying the item's id, its product, its intent, the cost in hours, and the
action "ESCALATE"; the hours you have left do not change. Emit this line, with the item's id and
the hours you have left in place of the placeholders:

[fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ESCALATE remaining={{remaining_hours}}

Then the run ends here. Return an object with `status` set to "OK", `items` set to the record
exactly as it now stands, `remaining_hours` set to the hours you have left, and `halted_at` set
to this item's id. It carries those four keys and no others, with exactly that casing. The
lines you have been emitting are not part of it; they stand on their own. No later item in the
queue is looked at, classified or recorded.

*It fits.* The cost is less than or equal to the hours you have left. Take the work on:
subtract the cost from the hours you have left, then add an entry to the record carrying the
item's id, its product, its intent, the cost in hours, and the action "ASSIGN". Emit this line,
with the item's id and the hours you have left after the subtraction in place of the
placeholders:

[fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ASSIGN remaining={{remaining_hours}}

*It does not fit, and it is not a bug.* The cost is greater than the hours you have left and
the intent is FEATURE or QUESTION. Put the work off. Add an entry to the record carrying the
item's id, its product, its intent, the cost in hours, and the action "DEFER"; the hours you
have left do not change. Emit this line, with the item's id and the hours you have left in place
of the placeholders:

[fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=DEFER remaining={{remaining_hours}}

### When the queue runs out

If you reach the end of the queue without any item having stopped it, return an object with
`status` set to "OK", `items` set to the record you have built, `remaining_hours` set to the
hours you have left after the last item, and `halted_at` set to null, since nothing stopped the
queue. It carries those four keys and no others, with exactly that casing. The lines you emitted
as you went are not part of it; they stand on their own.

This is the shape of the object, with placeholders where the values go:

```
{
  "status": "OK",
  "items": [
    {"id": "<item id>", "product": "<product id>", "intent": "<intent>", "hours": <cost in hours>, "action": "<action>"}
  ],
  "remaining_hours": <hours left>,
  "halted_at": null
}
```
