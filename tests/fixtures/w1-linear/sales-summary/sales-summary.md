---
name: fixture-w1-sales-summary
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a precise data extractor specializing in reading free-form handwritten sales annotations and computing numeric totals."
description: "W1 linear fixture. Parses free-form handwritten sales notes (plain text) and returns the total amount of valid sales and the count of valid entries. Lines explicitly marked as cancelled, reversed, or voided must be excluded. No branching: single extraction and aggregation pass."
accepts:
  notes:
    required: true
    desc: "plain-text block containing one sales annotation per line; format varies (dates, names, item descriptions, amounts in various styles)"
returns:
  total:
    type: number
    required: true
    desc: "sum of all valid sale amounts (numeric, not a string); cancelled/voided/reversed entries excluded"
  count:
    type: integer
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
    {"TODO": "Read the sales annotations from the notes block above."},
    {"TODO": "Set running_total to 0 and sale_count to 0."},
    {
      "REPEAT": {
        "foreach": "line in the notes block",
        "ROUTINE": [
          {"TODO": "Skip blank lines and header/separator lines with no monetary amount."},
          {"TODO": "If the line is marked as cancelled, annulled, voided, reversed, or storno (in any language or abbreviation), skip it — do not add its amount."},
          {"TODO": "Extract the monetary amount from the line. Amounts may appear as: '89€', 'EUR 89', '89 euro', '(89)', 'tot 89', or as arithmetic expressions like '35+38=73' or '2x45=90' — in the latter cases use the final computed value."},
          {"TODO": "Add the extracted amount to running_total."},
          {"TODO": "Increment sale_count by 1."}
        ]
      }
    },
    {"TODO": "Build the result as JSON: {\"total\": <running_total as a JSON number>, \"count\": <sale_count as a JSON integer>}. No other fields. Exact key casing."},
    {"RETURN": "{{result}}"}
  ]
}
```
