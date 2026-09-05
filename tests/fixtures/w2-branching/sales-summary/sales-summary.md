---
name: fixture-w2-sales-summary
version: "1.1"
schema: "../../../../sol-schema.json"
system_prompt: "You are a precise data extractor specializing in reading free-form handwritten sales annotations and computing numeric totals."
description: "W2 branching fixture. Parses free-form handwritten sales notes (plain text) and returns the total amount of valid sales and the count of valid entries. Two guards inside the per-line loop: non-data lines and lines marked as cancelled, reversed or voided are skipped. Both are explicit IF constructs -- they used to be prose inside TODO steps, where a flowchart built from the script could not show them (2026-08-20)."
accepts:
  notes:
    required: true
    desc: "plain-text block containing one sales annotation per line; format varies (dates, names, item descriptions, amounts in various styles)"
returns:
  total:
    number: true
    required: true
    desc: "sum of all valid sale amounts (numeric, not a string); cancelled/voided/reversed entries excluded"
  count:
    number: true
    required: true
    desc: "number of valid sales entries counted"
---

# Sales summary task

Compute the sales summary by executing strictly the SOL script below.

## Notes content

```
{{notes}}
```

## SOL script

```json
{
  "ROUTINE": [
    {
      "TODO": "Read the sales annotations from the notes block above."
    },
    {
      "TODO": "Set running_total to 0 and sale_count to 0."
    },
    {
      "REPEAT": {
        "foreach": "line in the notes block",
        "ROUTINE": [
          {
            "IF": {
              "when": "the line is blank, or a header or separator line with no monetary amount",
              "then": [
                {
                  "TODO": "Leave running_total and sale_count unchanged for this line."
                },
                {
                  "TODO": "Emit verbatim: [fixture-w2-sales-summary][main] BRANCH: branch-noise"
                }
              ],
              "else": [
                {
                  "IF": {
                    "when": "the line is marked as cancelled, annulled, voided, reversed, or storno (in any language or abbreviation)",
                    "then": [
                      {
                        "TODO": "Leave running_total and sale_count unchanged for this line."
                      },
                      {
                        "TODO": "Emit verbatim: [fixture-w2-sales-summary][main] BRANCH: branch-cancelled"
                      }
                    ],
                    "else": [
                      {
                        "TODO": "Extract the monetary amount from the line. Amounts may appear as: '89€', 'EUR 89', '89 euro', '(89)', 'tot 89', or as arithmetic expressions like '35+38=73' or '2x45=90' — in the latter cases use the final computed value."
                      },
                      {
                        "TODO": "Add the extracted amount to running_total."
                      },
                      {
                        "TODO": "Increment sale_count by 1."
                      },
                      {
                        "TODO": "Emit verbatim: [fixture-w2-sales-summary][main] BRANCH: branch-count"
                      }
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    },
    {
      "TODO": "Build the result as JSON: {\"total\": <running_total as a JSON number>, \"count\": <sale_count as a JSON integer>}. No other fields. Exact key casing."
    },
    {
      "RETURN": "{{result}}"
    }
  ]
}
```
