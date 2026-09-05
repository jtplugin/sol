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

## The procedure

You handle one support request. Everything you need about it, and about the situation it has to
be decided in, comes from a single request file: the request itself, the hours left in the
budget, and the current state of each team.

### First, check that the material is usable

Read the request file. Then stop and check all of the following. The material is unusable if no
path to the file was given, or the file could not be read, or its content has no `item` object,
or that item is missing its `id`, its `title`, or its `body`, or `remaining_hours` is missing or
is not a number, or `teams` does not give a state for each of T1, T2 and T3.

If the material is unusable, write out this line exactly as it stands:

[fixture-w2-support-routing][main] BRANCH: guard status=INVALID_INPUT

and then return an object whose `status` is `"INVALID_INPUT"`, whose `item` is null and whose
`remaining_hours` is null. That ends the work: there is no decision to make and nothing to
report about the budget.

Otherwise carry on with three things taken from the file: the request, the hours left in the
budget, and the state of each team. The team states are the ones in force for this request —
never a state you assume from anywhere else.

### Classify the request

Decide which product the request concerns. Judge this from the persona descriptions in the
product catalog and from nothing else: read the request's title and body, and settle on the
single product whose persona best matches — one of P1, P2, P3, P4 or P5. If none of them
plausibly matches, the product is UNKNOWN.

Then decide, from the same title and body, what the request is asking for. It is exactly one of
BUG, FEATURE or QUESTION, and you judge it on its own, whatever product turned out to be
involved.

Now write out this line, putting in place of the three placeholders the request's id, the
product you settled on, and the intent you settled on:

[fixture-w2-support-routing][main] EVAL: item={{item.id}} product={{product}} intent={{intent}}

### Reach a decision

The decision you are building always carries the same six things: the request's id, the product,
the intent, an hours figure, a team, and an action. Work through the cases below in the order
they are given and follow the first one that fits.

**The product is UNKNOWN.** The decision records the request's id, `"UNKNOWN"` as the product,
the intent you settled on, null for hours, null for team, and `"NEEDS_INFO"` as the action. The
hours left in the budget do not change. Write out this line, putting in the request's id and the
hours left in the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=NEEDS_INFO team=- remaining={{remaining_hours}}

**No team accepts the product.** That is, the product you settled on appears in no team's
`accepts` list in the team assignment table. The decision records the request's id, the product,
the intent, null for hours, null for team, and `"UNASSIGNED"` as the action. The hours left in
the budget do not change. Write out this line, putting in the request's id and the hours left in
the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=UNASSIGNED team=- remaining={{remaining_hours}}

**Otherwise** — the product is one of the five and some team accepts it — work out the effort
first. Look the product up in `hours_table` in the product catalog, then look up the intent
under it. The number you find there is the hours figure, exactly as written; it is a lookup, not
an estimate of your own.

Compare that figure with the hours left in the budget. If it is greater than the hours left, the
request does not fit, and there are two ways that can go:

- **It does not fit and the intent is BUG.** The decision records the request's id, the product,
  the intent, the hours figure, null for team, and `"ESCALATE"` as the action. The hours left in
  the budget do not change. Write out this line, putting in the request's id and the hours left
  in the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=ESCALATE team=- remaining={{remaining_hours}}

- **It does not fit and the intent is anything else.** The decision records the request's id,
  the product, the intent, the hours figure, null for team, and `"DEFER"` as the action. The
  hours left in the budget do not change. Write out this line, putting in the request's id and
  the hours left in the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=DEFER team=- remaining={{remaining_hours}}

If instead the hours figure is less than or equal to the hours left in the budget, the request
fits, and you go looking for a team to take it.

### Finding a team

Start with the team that owns the product: the one whose `accepts` list contains it, in the team
assignment table. Whether it takes the request depends on the state that team is in for this
request.

If that team's state is OPEN, it takes the request. If its state is LIMITED and the intent is
BUG, it takes the request. In every other case it does not, and you look for a backup instead:
the team whose `backs_up` list contains the product. If there is such a team and its state is
OPEN, the backup takes the request. If no team backs that product up, or the backup's state is
anything other than OPEN, then nobody takes the request.

**Nobody takes the request.** The decision records the request's id, the product, the intent,
the hours figure, null for team, and `"DEFER"` as the action. The hours left in the budget do
not change. Write out this line, putting in the request's id and the hours left in the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=DEFER team=- remaining={{remaining_hours}}

**A team takes the request.** First spend the effort: subtract the hours figure from the hours
left in the budget, so that from here on the hours left are the reduced amount. Then the
decision records the request's id, the product, the intent, the hours figure, the team that took
it, and `"ASSIGN"` as the action. Write out this line, putting in the request's id, the id of
the team that took it, and the hours now left in the budget:

[fixture-w2-support-routing][main] BRANCH: item={{item.id}} action=ASSIGN team={{team}} remaining={{remaining_hours}}

### What you return

Return one JSON object carrying exactly three keys and no others, cased just like this:
`status`, `item`, `remaining_hours`. Its `status` is `"OK"`. Its `item` is the decision you
reached, with the six keys named above. Its `remaining_hours` is the hours left in the budget
now that this request has been dealt with — the reduced amount if the request was assigned, and
otherwise the same amount you started with. The EVAL and BRANCH lines you wrote out are not part
of that object.

The object has this shape, with each placeholder standing where its value goes:

```json
{
  "status": "OK",
  "item": {
    "id": "<request id>",
    "product": "<product>",
    "intent": "<intent>",
    "hours": <hours>,
    "team": "<team id>",
    "action": "<action>"
  },
  "remaining_hours": <hours left>
}
```
