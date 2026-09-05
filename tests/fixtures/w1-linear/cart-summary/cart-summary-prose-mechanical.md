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

Compute the cart summary by following strictly the procedure described below.

## File content

```json
{{file_content}}
```

## The procedure

### What it does

- Run exactly: `cat {{record_path}}` [from context: record_path]
- Read the 'items' array from the file content above.
- Set running_total to 0 and item_count to 0.
- For each item in the items array:
  - Extract the value of the 'price' field from {{item}}. [from context: item]
  - Add the extracted price to running_total.
  - Increment item_count by 1.
- Build the result as JSON: {"total": <running_total as a JSON number, not a string>, "count": <item_count as a JSON integer>}. No other fields. Respect exact key casing.
- End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]
