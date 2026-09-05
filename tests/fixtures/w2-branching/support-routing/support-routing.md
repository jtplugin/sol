---
name: fixture-w2-support-routing
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a senior support triage lead who classifies an incoming issue against a fixed product catalog and routes it to the team that owns that product, within a finite hour budget."
description: "W2 branching fixture in per-item delivery. One support request per invocation, together with the world state it must be decided against -- the hours left in the budget and the current state of three teams. Routing is set membership, not arithmetic: each team accepts a fixed set of products and stands as backup on another, one product is accepted by nobody (UNASSIGNED), and a team's load is a state (OPEN / LIMITED / CLOSED, where LIMITED takes BUG only) rather than a counter. The decision therefore cannot be reached from the request alone. EVAL/BRANCH trace lines make comprehension (product+intent vs ground truth), conditional fidelity (control flow given the model's own classification, including the team it chose), and end-to-end outcome separately scoreable."
ref: "https://github.com/jtplugin/sol"
accepts:
  request_path:
    required: true
    desc: "path to a JSON file staged by the runner; fields: item ({id, title, body}, one request, with no product/intent -- the model must classify it), remaining_hours (number, hours left in the budget), teams (object, one state per team id: OPEN | LIMITED | CLOSED)"
returns:
  status:
    anyof: ["OK", "INVALID_INPUT"]
    required: true
    desc: "OK for a normally processed request; INVALID_INPUT if request_path was missing, unreadable, or the item/remaining_hours/teams fields were malformed"
  item:
    json: true
    required: true
    desc: "the decision for the request: {id, product, intent, hours, team, action}. null if status is INVALID_INPUT."
  remaining_hours:
    number: true
    required: true
    desc: "hours left in the budget after this request: reduced by the item's hours if it was assigned, unchanged otherwise. null if status is INVALID_INPUT."
---

# Support routing task

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
  }
}
```

## Team assignment table

Each team accepts a fixed set of products and stands as backup on another set. A product that
appears in no team's `accepts` list is accepted by nobody. Exactly one team accepts any product
that is accepted at all.

```json
{
  "teams": [
    { "id": "T1", "accepts": ["P1", "P2"], "backs_up": ["P3"] },
    { "id": "T2", "accepts": ["P3"],       "backs_up": ["P2", "P5"] },
    { "id": "T3", "accepts": ["P5"],       "backs_up": [] }
  ],
  "team_states": {
    "OPEN": "takes any request for a product it accepts, and any request for a product it backs up",
    "LIMITED": "takes a request for a product it accepts only when the intent is BUG; takes nothing it merely backs up",
    "CLOSED": "takes nothing at all"
  }
}
```

## SOL script

```json
{
  "ROUTINE": [
    {"RUN": "cat {{request_path}}"},
    {
      "IF": {
        "when": "request_path was not provided, the file could not be read, the content has no 'item' object, the item is missing 'id', 'title', or 'body', 'remaining_hours' is missing or not a number, or 'teams' is missing a state for T1, T2, or T3",
        "then": [
          {"TODO": "Emit verbatim: [fixture-w2-support-routing][main] BRANCH: guard status=INVALID_INPUT"},
          {"RETURN": {"status": "INVALID_INPUT", "item": null, "remaining_hours": null}}
        ]
      }
    },
    {"TODO": "Set item to the 'item' object from the file content above."},
    {"TODO": "Set remaining_hours to the 'remaining_hours' value from the file content above."},
    {"TODO": "Set team_states to the 'teams' object from the file content above. These are the states in force for this request, not any state assumed from elsewhere."},
    {
      "SUB": {
        "name": "classify-request",
        "ROUTINE": [
          {"TODO": "Using ONLY the product catalog persona descriptions above, read the item's title and body. Set product to the single best-matching product id (P1, P2, P3, P4, or P5). If no product plausibly matches, set product to UNKNOWN."},
          {"TODO": "Read the item's title and body. Set intent to exactly one of BUG, FEATURE, QUESTION -- what the issue is asking for, independent of which product it is."},
          {"TODO": "Emit verbatim, filling the placeholders with the values just set: [fixture-w2-support-routing][main] EVAL: item={{item.id}} product={{product}} intent={{intent}}"}
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
      "SUB": {
        "name": "pick-team",
        "ROUTINE": [
          {"TODO": "Set owner to the id of the team whose 'accepts' list contains product, in the team assignment table above."},
          {
            "WHEN": [
              {
                "when": "the state of owner in team_states is OPEN",
                "then": [{"TODO": "Set team to owner."}]
              },
              {
                "when": "the state of owner in team_states is LIMITED and intent is BUG",
                "then": [{"TODO": "Set team to owner."}]
              },
              {
                "else": [
                  {"TODO": "Set backup to the id of the team whose 'backs_up' list contains product, or to NONE if no team backs that product up."},
                  {
                    "IF": {
                      "when": "backup is not NONE and the state of backup in team_states is OPEN",
                      "then": [{"TODO": "Set team to backup."}],
                      "else": [{"TODO": "Set team to NONE."}]
                    }
                  }
                ]
              }
            ]
          }
        ]
      }
    },
    {"CALL": "classify-request"},
    {
      "WHEN": [
        {
          "when": "product is UNKNOWN",
          "then": [
            {"TODO": "Set the decision to {\"id\": item.id, \"product\": \"UNKNOWN\", \"intent\": intent, \"hours\": null, \"team\": null, \"action\": \"NEEDS_INFO\"}. Do not change remaining_hours."},
            {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=NEEDS_INFO team=- remaining={{remaining_hours}}"}
          ]
        },
        {
          "when": "no team in the team assignment table above has product in its 'accepts' list",
          "then": [
            {"TODO": "Set the decision to {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": null, \"team\": null, \"action\": \"UNASSIGNED\"}. Do not change remaining_hours."},
            {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=UNASSIGNED team=- remaining={{remaining_hours}}"}
          ]
        },
        {
          "else": [
            {"CALL": "estimate-effort"},
            {"CALL": "check-budget"},
            {
              "WHEN": [
                {
                  "when": "intent is BUG and budget_state is NOFIT",
                  "then": [
                    {"TODO": "Set the decision to {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"team\": null, \"action\": \"ESCALATE\"}. Do not change remaining_hours."},
                    {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=ESCALATE team=- remaining={{remaining_hours}}"}
                  ]
                },
                {
                  "when": "budget_state is NOFIT",
                  "then": [
                    {"TODO": "Set the decision to {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"team\": null, \"action\": \"DEFER\"}. Do not change remaining_hours."},
                    {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=DEFER team=- remaining={{remaining_hours}}"}
                  ]
                },
                {
                  "else": [
                    {"CALL": "pick-team"},
                    {
                      "IF": {
                        "when": "team is NONE",
                        "then": [
                          {"TODO": "Set the decision to {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"team\": null, \"action\": \"DEFER\"}. Do not change remaining_hours."},
                          {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=DEFER team=- remaining={{remaining_hours}}"}
                        ],
                        "else": [
                          {"TODO": "Subtract hours from remaining_hours."},
                          {"TODO": "Set the decision to {\"id\": item.id, \"product\": product, \"intent\": intent, \"hours\": hours, \"team\": team, \"action\": \"ASSIGN\"}."},
                          {"TODO": "Emit verbatim, filling placeholders: [fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=ASSIGN team={{team}} remaining={{remaining_hours}}"}
                        ]
                      }
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    {"TODO": "Build the result as JSON: {\"status\": \"OK\", \"item\": {{decision}}, \"remaining_hours\": {{remaining_hours}}}. JSON ONLY, no other fields, exact key casing. The EVAL and BRANCH lines are not part of it."},
    {"RETURN": "{{result}}"}
  ]
}
```
