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

Compute the sales summary by following strictly the procedure described below.

## Notes content

```
{{notes}}
```

## The procedure

You are given a block of handwritten sales annotations, one annotation per line. Your job is to
work through those lines one at a time and end up with two numbers: how much the valid sales
come to, and how many valid sales there were.

Before you start reading the lines, set both of those numbers to zero.

### Working through the lines

Take the lines of the notes one at a time, in the order they appear, from the first to the
last. For each line, decide which of the three cases below it falls into, do what that case
says, and then move on to the next line. Only when you have dealt with the last line do you go
on to assemble the answer.

**A line that carries no sale.** This is a line that is blank, or a header or separator line
with no monetary amount on it. Leave both numbers exactly as they are — this line adds nothing
to the sum and nothing to the tally. Then write out this line exactly as it stands here:

[fixture-w2-sales-summary][main] BRANCH: branch-noise

**A line that has been struck out.** This is a line marked as cancelled, annulled, voided,
reversed, or storno — in any language, and whether the word is written out in full or
abbreviated. Again, leave both numbers exactly as they are. Then write out this line exactly as
it stands here:

[fixture-w2-sales-summary][main] BRANCH: branch-cancelled

Test the two cases in that order. If a line could be read as carrying no sale and also as
struck out, treat it as carrying no sale: the first case wins, and the line goes no further.

**Any other line.** This is a real sale, and you have three things to do with it.

First, find the monetary amount on the line. Amounts are written in whatever style the writer
felt like: they may appear as '89€', 'EUR 89', '89 euro', '(89)', 'tot 89', or as arithmetic
expressions like '35+38=73' or '2x45=90' — in those last cases the amount is the final computed
value.

Second, add that amount to the running sum.

Third, add one to the tally of sales.

Having done all three, write out this line exactly as it stands here:

[fixture-w2-sales-summary][main] BRANCH: branch-count

Whichever of the three cases a line fell into, once you have written its line out you are
finished with that line: go back and take the next one, and carry on until there are no lines
left.

### What to return

When every line has been dealt with, return a single JSON object built from the two numbers you
have accumulated. It has exactly two keys and no others, spelled and cased just like this:

- `total` — the sum of the valid sale amounts, as a JSON number. Not a string, and not
  formatted with a currency symbol.
- `count` — how many valid sales you tallied, as a JSON integer.

The lines you wrote out while working through the notes are not part of this object; they stand
on their own, and the object carries only the two keys named above.

The shape of the object, with placeholders where the two values go:

```json
{"total": <sum of the valid amounts>, "count": <number of valid sales>}
```
