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

Route the task request by following the procedure described below strictly.

## File content

```json
{{file_content}}
```

## The procedure

### What it does

- Run exactly: `cat {{record_path}}` [from context: record_path]
- If record_path was not provided, the file could not be read, or effort_days or deadline_days is missing or not a positive integer, then:
  - Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-guard
  - End this process and hand control back to whoever invoked it, yielding: {"verdict": "INVALID_INPUT"}
- Define the subroutine «assess-capacity» — see *Subroutines* below.
- Define the subroutine «assess-urgency» — see *Subroutines* below.
- Call the subroutine «assess-capacity», which sees everything this process sees.
- Call the subroutine «assess-urgency», which sees everything this process sees.
- Depending on the case:
  - When capacity_class is HEAVY and urgency_class is URGENT:
    - Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-split
    - set verdict to SPLIT
  - When capacity_class is HEAVY and urgency_class is NORMAL:
    - Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-schedule
    - set verdict to SCHEDULE
  - When capacity_class is LIGHT and urgency_class is URGENT:
    - Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-expedite
    - set verdict to EXPEDITE
  - Otherwise:
    - Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-queue
    - set verdict to QUEUE
- Build the result as JSON: {"verdict": "{{verdict}}"}. MANDATORY: **JSON ONLY**, no other fields, exact key casing. The BRANCH lines are not part of it. [from context: verdict]
- End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]

### Subroutines

#### The subroutine «assess-capacity»

**What it does:**

- If effort_days is greater than 5, then:
  - Emit verbatim: [fixture-w3-task-router][assess-capacity] BRANCH: capacity-heavy
  - Set capacity_class to HEAVY
- Otherwise:
  - Emit verbatim: [fixture-w3-task-router][assess-capacity] BRANCH: capacity-light
  - Set capacity_class to LIGHT

#### The subroutine «assess-urgency»

**What it does:**

- Depending on the case:
  - When deadline_days is less than or equal to 3:
    - Emit verbatim: [fixture-w3-task-router][assess-urgency] BRANCH: urgency-urgent
    - Set urgency_class to URGENT
  - Otherwise:
    - Emit verbatim: [fixture-w3-task-router][assess-urgency] BRANCH: urgency-normal
    - Set urgency_class to NORMAL
