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

Route the task request by executing the SOL script below strictly.

## File content

```json
{{file_content}}
```

## SOL script

```json
{
  "ROUTINE": [
    {"RUN": "cat {{file content}}"},
    {
      "IF": {
        "when": "file content was not provided, the file could not be read, or effort_days or deadline_days is missing or not a positive integer",
        "then": [
          {"TODO": "Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-guard"},
          {"RETURN": {"verdict": "INVALID_INPUT"}}
        ]
      }
    },
    {
      "SUB": {
        "name": "assess-capacity",
        "ROUTINE": [
          {
            "IF": {
              "when": "effort_days is greater than 5",
              "then": [
                {"TODO": "Emit verbatim: [fixture-w3-task-router][assess-capacity] BRANCH: capacity-heavy"},
                {"TODO": "Set capacity_class to HEAVY"}
              ],
              "else": [
                {"TODO": "Emit verbatim: [fixture-w3-task-router][assess-capacity] BRANCH: capacity-light"},
                {"TODO": "Set capacity_class to LIGHT"}
              ]
            }
          }
        ]
      }
    },
    {
      "SUB": {
        "name": "assess-urgency",
        "ROUTINE": [
          {
            "WHEN": [
              {
                "when": "deadline_days is less than or equal to 3",
                "then": [
                  {"TODO": "Emit verbatim: [fixture-w3-task-router][assess-urgency] BRANCH: urgency-urgent"},
                  {"TODO": "Set urgency_class to URGENT"}
                ]
              },
              {
                "else": [
                  {"TODO": "Emit verbatim: [fixture-w3-task-router][assess-urgency] BRANCH: urgency-normal"},
                  {"TODO": "Set urgency_class to NORMAL"}
                ]
              }
            ]
          }
        ]
      }
    },
    {"CALL": "assess-capacity"},
    {"CALL": "assess-urgency"},
    {
      "WHEN": [
        {
          "when": "capacity_class is HEAVY and urgency_class is URGENT",
          "then": [
            {"TODO": "Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-split"},
            {"TODO": "set verdict to SPLIT"}
          ]
        },
        {
          "when": "capacity_class is HEAVY and urgency_class is NORMAL",
          "then": [
            {"TODO": "Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-schedule"},
            {"TODO": "set verdict to SCHEDULE"}
          ]
        },
        {
          "when": "capacity_class is LIGHT and urgency_class is URGENT",
          "then": [
            {"TODO": "Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-expedite"},
            {"TODO": "set verdict to EXPEDITE"}
          ]
        },
        {
          "else": [
            {"TODO": "Emit verbatim: [fixture-w3-task-router][main] BRANCH: branch-queue"},
            {"TODO": "set verdict to QUEUE"}
          ]
        }
      ]
    }
	{"TODO":  "Build the result as JSON: {\"verdict\": "{{verdict}}"}. MANDATORY: No other output, **JSON ONLY**, No other fields. Respect exact key casing."},
	{"RETURN": "{{result}}"}
  ]
}
```
