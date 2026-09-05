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

Compute the cart summary by executing strictly the procedure below.

## File content

```json
{{file_content}}
```

## The procedure

You are working from the contents of the record file at the path you have been given. That
file is JSON, and it has a field called `items` holding an array of objects. Each of those
objects carries a price value in a field called `price`. Read the `items` array out of that
file; it is the only part of the file the work concerns.

Before you start on the items, fix two figures at zero: a running total of the prices, and a
count of the items seen. Both begin at zero and both grow as you go.

Now work through the items array one entry at a time, taking the entries in the order the
array gives them. For each entry, take the value of its `price` field, add that value to your
running total, and add one to your count. Then move on to the next entry and do the same
three things again, and keep going until you have handled every entry in the array. Only when
the array is exhausted do you go on to the rest of this procedure.

When every item has been handled, build the result as a JSON object with exactly two keys,
spelled and cased as written here. The key `total` holds your running total, written as a JSON
number and not as a string in quotes. The key `count` holds your count of items, written as a
JSON integer. The object carries these two keys and no others.

Return that object.

For shape only, the object you return looks like this, with the two placeholders standing
where the values go:

```json
{"total": TOTAL, "count": COUNT}
```
