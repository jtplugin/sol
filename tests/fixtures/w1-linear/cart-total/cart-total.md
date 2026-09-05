---
name: fixture-w1-cart-total
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a precise data processor specializing in extracting and aggregating numeric values from structured records."
description: "W1 linear fixture. Extracts price values from an items array and returns their numeric sum. Prices may appear as string values or as numeric keys. No branching: the model applies a single extraction and aggregation pass."
accepts:
  record_path:
    required: true
    desc: "path to a JSON file with field 'items': array of objects each containing exactly one price value"
returns:
  verdict:
    number: true
    required: true
    desc: "sum of all price values in the items array, as a JSON number"
---

# Aggregation task

Compute the total price by executing strictly the SOL script below.

## SOL script

```json
{
  "ROUTINE": [
    {"RUN": "cat {{record_path}}"},
    {"TODO": "Read the 'items' array from the file content below."},
    {"TODO": "Set a running total to 0."},
    {
      "REPEAT": {
        "foreach": "item in the items array",
        "ROUTINE": [
          {"TODO": "Extract the value of the 'price' field from {{item}}."},
          {"TODO": "Add the extracted price to the running total."}
        ]
      }
    },
    {"TODO": "Build the result as JSON: {\"verdict\": <running total as a JSON number, not a string>}. No other fields. Respect exact key casing."},
    {"RETURN": "{{result}}"}
  ]
}
```

## File content

```json
{{file_content}}
```