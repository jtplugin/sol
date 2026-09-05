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

Compute the total price by following strictly the procedure described in this document.

## The procedure

You are given the contents of a JSON record file. That content is a JSON object with a field
named `items`, whose value is an array of objects. Each of those objects carries exactly one
price value, held in a field named `price`.

Start by taking the `items` array from that content, and keep a running total, which begins
at 0.

Now work through the array one item at a time, in the order the items appear in it. For the
item you are on, take the value of its `price` field and add that value to the running total.
That done, the item is finished: go back to the array, take the next item that has not yet
been handled, and do the same again. Carry on this way until you have handled every item in
the array. The running total then holds the sum of all the price values.

When there are no items left to handle, build the result: a JSON object whose single key is
`verdict`, and whose value is the running total written as a JSON number, not as a string.
That object carries the key `verdict` and no other keys, and the key is written with exactly
that casing. Return that object.

The shape of what you return, with a placeholder standing where the value goes:

```json
{"verdict": TOTAL}
```

## File content

```json
{{file_content}}
```
