---
name: fixture-w1-cart-summary
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a precise data processor specializing in extracting and aggregating numeric values from structured records."
description: "W1 linear fixture. Extracts price values from an items array and returns both their numeric sum and the item count. No branching: the model applies a single extraction and aggregation pass producing two output fields."
accepts:
  record_path:
    required: true
    desc: "path to a JSON file with field 'items': array of objects each containing exactly one price value"
returns:
  total:
    number: true
    required: true
    desc: "sum of all price values in the items array, as a JSON number"
  count:
    number: true
    required: true
    desc: "number of items in the items array, as a JSON integer"
---

# Aggregation task

Compute the cart summary by executing strictly the SOL script below.

## File content

```json
{{file_content}}
```

## SOL script

```json
{
  "ROUTINE": [
    {"RUN": "cat {{record_path}}"},
    {"TODO": "Read the 'items' array from the file content above."},
    {"TODO": "Set running_total to 0 and item_count to 0."},
    {
      "REPEAT": {
        "foreach": "item in the items array",
        "ROUTINE": [
          {"TODO": "Extract the value of the 'price' field from {{item}}."},
          {"TODO": "Add the extracted price to running_total."},
          {"TODO": "Increment item_count by 1."}
        ]
      }
    },
    {"TODO": "Build the result as JSON: {\"total\": <running_total as a JSON number, not a string>, \"count\": <item_count as a JSON integer>}. No other fields. Respect exact key casing."},
    {"RETURN": "{{result}}"}
  ]
}
```
