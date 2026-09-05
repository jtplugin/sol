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

Compute the total price by following strictly the procedure described below.

## The procedure

### What it does

- Run exactly: `cat {{record_path}}` [from context: record_path]
- Read the 'items' array from the file content below.
- Set a running total to 0.
- For each item in the items array:
  - Extract the value of the 'price' field from {{item}}. [from context: item]
  - Add the extracted price to the running total.
- Build the result as JSON: {"verdict": <running total as a JSON number, not a string>}. No other fields. Respect exact key casing.
- End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]

## File content

```json
{{file_content}}
```