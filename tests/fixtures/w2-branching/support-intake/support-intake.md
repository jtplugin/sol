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

## SOL script

```json
{
  "ROUTINE": [
    {"RUN": "cat {{queue_path}}"},
    {
      "IF": {
        "when": "queue_path was not provided, the file could not be read, the content has no 'queue' array, or any queue item is missing 'id', 'title', or 'body'",
        "then": [
          {"TODO": "Emit verbatim: [fixture-w2-support-intake][main] BRANCH: guard status=INVALID_INPUT"},
          {"RETURN": {"status": "INVALID_INPUT", "items": [], "remaining_hours": null, "halted_at": null}}
        ]
      }
    },
    {"TODO": "Set remaining_hours to 20 (the budget_hours value from the product catalog above). Set halted_at to null. Set items to an empty list."},
    {
      "SUB": {
        "name": "classify-request",
        "ROUTINE": [
          {"TODO": "Using ONLY the product catalog persona descriptions above, read the current item's title and body. Set product to the single best-matching product id (P1, P2, P3, P4, or P5). If no product plausibly matches, set product to UNKNOWN."},
          {"TODO": "Read the current item's title and body. Set intent to exactly one of BUG, FEATURE, QUESTION -- what the issue is asking for, independent of which product it is."},
          {"TODO": "Emit verbatim, filling the placeholders with the values just set: [fixture-w2-support-intake][main] EVAL: item={{item.id}} product={{product}} intent={{intent}}"}
        ]
      }
    },
    {
      "SUB": {
        "name": "estimate-effort",
        "ROUTINE": [
          {"TODO": "Look up hours_table[product][intent] in the product catalog above. Set hours to that number exactly -- this is a fixed lookup, not an estimate you make yourself."}
        ]
      }
    },
    {
      "SUB": {
        "name": "check-budget",
        "ROUTINE": [
          {
            "IF": {
              "when": "hours is less than or equal to remaining_hours",
              "then": [{"TODO": "Set budget_state to FITS."}],
              "else": [{"TODO": "Set budget_state to NOFIT."}]
            }
          }
        ]
      }
    },
    {
      "REPEAT": {
        "foreach": "item in the queue array, in the given order",
        "ROUTINE": [
          {"CALL": "classify-request"},
          {
            "IF": {
              "when": "product is UNKNOWN",
              "then": [
                {"TODO": "Append {\"id\": item.id, \"product\": \"UNKNOWN\", \"intent\": intent, \"hours\": null, \"action\": \"NEEDS_INFO\"} to items. Do not change remaining_hours."},
                {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=NEEDS_INFO remaining={{remaining_hours}}"}
              ],
              "else": [
                {"CALL": "estimate-effort"},
                {"CALL": "check-budget"},
                {
                  "WHEN": [
                    {
                      "when": "intent is BUG and budget_state is NOFIT",
                      "then": [
                        {"TODO": "Set halted_at to item.id."},
                        {"TODO": "Append {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"action\": \"ESCALATE\"} to items. Do not change remaining_hours."},
                        {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ESCALATE remaining={{remaining_hours}}"},
                        {"TODO": "Build the result as JSON: {\"status\": \"OK\", \"items\": {{items}}, \"remaining_hours\": {{remaining_hours}}, \"halted_at\": {{halted_at}}}. JSON ONLY, no other fields, exact key casing. The EVAL and BRANCH lines are not part of it."},
                        {"RETURN": "{{result}}"}
                      ]
                    },
                    {
                      "when": "budget_state is FITS",
                      "then": [
                        {"TODO": "Subtract hours from remaining_hours."},
                        {"TODO": "Append {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"action\": \"ASSIGN\"} to items."},
                        {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=ASSIGN remaining={{remaining_hours}}"}
                      ]
                    },
                    {
                      "else": [
                        {"TODO": "Append {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"action\": \"DEFER\"} to items. Do not change remaining_hours."},
                        {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-intake][main] BRANCH: item={{item.id}} action=DEFER remaining={{remaining_hours}}"}
                      ]
                    }
                  ]
                }
              ]
            }
          }
        ]
      }
    },
    {"TODO": "Build the result as JSON: {\"status\": \"OK\", \"items\": {{items}}, \"remaining_hours\": {{remaining_hours}}, \"halted_at\": {{halted_at}}}. JSON ONLY, no other fields, exact key casing. The EVAL and BRANCH lines are not part of it."},
    {"RETURN": "{{result}}"}
  ]
}
```
