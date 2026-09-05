---
name: fixture-w2-support-routing-notrace
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a senior support triage lead who classifies an incoming issue against a fixed product catalog and routes it to the team that owns that product, within a finite hour budget."
description: "W2 branching fixture in per-item delivery. One support request per invocation, together with the world state it must be decided against -- the hours left in the budget and the current state of three teams. Routing is set membership, not arithmetic: each team accepts a fixed set of products and stands as backup on another, one product is accepted by nobody (UNASSIGNED), and a team's load is a state (OPEN / LIMITED / CLOSED, where LIMITED takes BUG only) rather than a counter. The decision therefore cannot be reached from the request alone."
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

## The procedure

You are deciding one support request. Everything the decision depends on arrives in a JSON
file staged at the path you were given as request_path: an item object holding the request
itself (its id, its title, and its body), a remaining_hours number giving the hours left in
the budget, and a teams object giving the state currently in force for each of the teams T1,
T2, and T3.

### Check the input first

Read that file before doing anything else. If the path was not provided, the file cannot be
read, its content has no item object, the item is missing id, title, or body, remaining_hours
is missing or is not a number, or teams lacks a state for T1, T2, or T3, then the run ends
here: return the object {"status": "INVALID_INPUT", "item": null, "remaining_hours": null}
and do nothing further.

If the input is sound, work from what the file gave you: the request, the hours left in the
budget, and the team states. The states in the file are the ones in force for this request —
do not assume a team's state from anywhere else.

### Classify the request

Decide two things from the request's title and body.

First, which product the request concerns. Judge this using only the persona descriptions in
the product catalog, and choose the single best-matching product id: P1, P2, P3, P4, or P5.
If no product plausibly matches, the product is UNKNOWN.

Second, what the issue is asking for: exactly one of BUG, FEATURE, or QUESTION, judged
independently of which product it is.

### Decide the outcome

Whatever happens next, the decision you record is an object with exactly six keys — id,
product, intent, hours, team, action — where id is always the request's id and intent is
always the intent you classified. The cases below differ in what fills the other four keys
and in whether the budget changes. Go through them in the order given and act on the first
one that applies.

If the product is UNKNOWN: the decision has product "UNKNOWN", hours null, team null, and
action "NEEDS_INFO". The hours left in the budget do not change. Skip ahead to returning the
result.

If the product is known but no team's accepts list in the team assignment table contains it:
the decision has that product, hours null, team null, and action "UNASSIGNED". The hours left
do not change. Skip ahead to returning the result.

Otherwise some team accepts the product, and the work continues. Look up the cost first: in
the hours_table of the product catalog, take the number filed under the product and, within
it, under the intent. The request's hours are that number exactly — this is a fixed lookup,
not an estimate of your own. The request fits the budget when its hours are less than or
equal to the hours left; otherwise it does not fit.

If the request does not fit and the intent is BUG: the decision has the product, the intent,
the looked-up hours, team null, and action "ESCALATE". The hours left do not change. A bug
that does not fit is always escalated — this case takes precedence over the deferral in the
next one.

If the request does not fit and the intent is anything else: the decision is the same except
that the action is "DEFER". The hours left do not change.

If the request fits, find the team that takes it. The owning team is the one team whose
accepts list in the team assignment table contains the product. The owner takes the request
when its state is OPEN, and also when its state is LIMITED and the intent is BUG. In every
other case the owner does not take it, and you turn to the backup: the team whose backs_up
list contains the product, if there is one. The backup takes the request only when such a
team exists and its state is OPEN. Otherwise no team takes the request.

When no team takes it: the decision has the product, the intent, the looked-up hours, team
null, and action "DEFER". The hours left do not change.

When a team takes it: first subtract the request's hours from the hours left in the budget,
then record the decision — the product, the intent, the looked-up hours, the taking team's id
as team, and action "ASSIGN".

### Return the result

Build one JSON object with three keys: status, whose value is "OK"; item, whose value is the
decision object you recorded; and remaining_hours, whose value is the hours now left in the
budget — reduced by the request's hours if it was assigned, unchanged otherwise. The object
carries exactly those keys, with exactly that casing, and no others. Return it as JSON.

The shape of the returned object, with placeholders where the values go:

{"status": "OK", "item": {"id": "the request's id", "product": "a product id", "intent": "the intent", "hours": 0, "team": "a team id", "action": "the action"}, "remaining_hours": 0}
