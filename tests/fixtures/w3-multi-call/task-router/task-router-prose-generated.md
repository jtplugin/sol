---
name: fixture-w3-task-router
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are an expert project manager specialising in task scheduling and resource allocation. You respect the mandatory instruction and do not send any output other than what is strictly required."
description: "W3 multi-call fixture. Reads a task request (effort_days, deadline_days) and routes it to the appropriate scheduling action. Two SUBs — assess-capacity and assess-urgency — each produce an intermediate classification; the main WHEN composes them into a final routing verdict. Quality oracle: returned verdict matches expected routing action. Fidelity oracle: last BRANCH trace line from the main WHEN."
accepts:
  record_path:
    required: true
    desc: "path to a JSON file with fields: effort_days (positive integer), deadline_days (positive integer)"
returns:
  verdict:
    anyof: ["SPLIT", "SCHEDULE", "EXPEDITE", "QUEUE", "INVALID_INPUT"]
    required: true
    desc: "routing action: SPLIT (heavy+urgent), SCHEDULE (heavy+normal), EXPEDITE (light+urgent), QUEUE (light+normal), INVALID_INPUT (bad record)"
---

# Routing task

Route the task request by following the procedure below strictly.

## File content

```json
{{file_content}}
```

## The procedure

Your job is to decide which scheduling action a single task request deserves, and to hand back
that decision. Along the way you will write out a few marker lines; each one is quoted here
exactly as it must appear, and you copy it character for character — the same brackets, the
same spacing, the same capitalisation — on a line by itself, with nothing added before or
after it.

### Reading the request

The request is a JSON record held in a file whose location is given to you as record_path. Two
fields in it matter: effort_days, how many days of work the task is estimated to take, and
deadline_days, how many days remain before it is due.

### Checking that the request can be used

Before deciding anything, satisfy yourself that you actually have a usable request. It is not
usable if no location was given for the record, if the file could not be read, or if either
effort_days or deadline_days is absent or is anything other than a positive whole number.

If any one of those is true, write out this line:

[fixture-w3-task-router][main] BRANCH: branch-guard

and then stop working through the request. The routing action is INVALID_INPUT. Make none of
the judgements described below; go straight to the result, which at that point consists of that
action and nothing else. The only line you will have written is the one just above.

### Judging the size of the task

If the request is usable, judge it in two independent ways. Take its size first.

A task of more than 5 effort_days is heavy. When it is, write out this line:

[fixture-w3-task-router][assess-capacity] BRANCH: capacity-heavy

A task of 5 effort_days or fewer is light. When it is, write out this line instead:

[fixture-w3-task-router][assess-capacity] BRANCH: capacity-light

### Judging the urgency of the task

Now take its urgency, on the same footing as the size — a task can be heavy or light quite
independently of how soon it is due.

A task with 3 deadline_days or fewer is urgent. When it is, write out this line:

[fixture-w3-task-router][assess-urgency] BRANCH: urgency-urgent

A task with more than 3 deadline_days is normal. When it is, write out this line instead:

[fixture-w3-task-router][assess-urgency] BRANCH: urgency-normal

### Combining the two judgements

You now hold one verdict on size and one on urgency. Together they settle the routing action;
exactly one of the four cases below fits.

Heavy and urgent. Write out this line:

[fixture-w3-task-router][main] BRANCH: branch-split

and the routing action is SPLIT.

Heavy and normal. Write out this line:

[fixture-w3-task-router][main] BRANCH: branch-schedule

and the routing action is SCHEDULE.

Light and urgent. Write out this line:

[fixture-w3-task-router][main] BRANCH: branch-expedite

and the routing action is EXPEDITE.

Anything else — that is, light and normal. Write out this line:

[fixture-w3-task-router][main] BRANCH: branch-queue

and the routing action is QUEUE.

### What you hand back

Build the result as a JSON object carrying a single key, verdict, spelled in lower case exactly
as written here. Its value is the routing action you arrived at, as a string: one of SPLIT,
SCHEDULE, EXPEDITE, QUEUE or INVALID_INPUT. That object must be JSON only, and it must carry
that key and no other fields. The marker lines you wrote as you worked are not part of the
returned object.

The shape of the object, with a placeholder where the routing action goes:

```json
{"verdict": "ROUTING_ACTION"}
```
