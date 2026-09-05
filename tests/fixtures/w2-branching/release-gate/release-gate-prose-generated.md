---
name: fixture-w2-release-gate
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a senior software release manager who evaluates release readiness criteria and makes go/no-go decisions."
description: "W2 branching-fidelity fixture. Reads a release record from a fixed file and classifies it into exactly one gate verdict. Each staged input is built so that exactly one branch is correct, so the returned verdict reveals which branch executed — that is the quality oracle. The per-branch trace TODOs emit a machine-readable BRANCH line so the checker can also verify fidelity."
ref: "https://github.com/jtplugin/sol"
accepts:
  record_path:
    required: true
    desc: "path to a JSON release record staged by the runner; fields: coverage (number 0-100), blocking_bugs (integer >= 0), security_review (one of passed|pending|failed)"
returns:
  verdict:
    anyof: ["BLOCKED", "INSUFFICIENT_COVERAGE", "SECURITY_HOLD", "READY", "INVALID_INPUT"]
    required: true
    desc: "the single gate verdict; identifies the branch taken"
---

# Gate evaluation task

Evaluate the release record by following strictly the procedure set out below.

## File content

```json
{{file_content}}
```

## The procedure

You are judging a single release record and giving it exactly one verdict. The record is a JSON
document held in a file; its location is the record path you were given.

### Read the record

Start by obtaining the contents of that file and reading the record it holds. A well-formed
record carries three pieces of information:

- **coverage** — a number between 0 and 100.
- **blocking_bugs** — a whole number, zero or greater.
- **security_review** — one of the three words `passed`, `pending` or `failed`.

### Check that you can work with it

Before judging anything, satisfy yourself that all of the following hold: you were actually
given a path to a record; the file at that path could be read; the record contains all three of
coverage, blocking_bugs and security_review; and each of those three is of the kind of value
described above rather than some other kind.

If any one of those fails — no path, an unreadable file, a missing field, or a field whose value
is of the wrong kind — then the record cannot be judged. Write out the following line exactly as
it appears here, on a line of its own:

[fixture-w2-release-gate][main] BRANCH: branch-guard

Then give the verdict `INVALID_INPUT` and stop. Nothing further in this procedure applies, and
nothing else about the record needs to be examined.

### Judge the record

If the record passed that check, work through the four cases below **in the order they are
given** and act on the **first** one that fits. The order matters: more than one of them can be
true of the same record, and the earlier one always wins. As soon as one fits, do what it says
and stop — do not go on to consider the ones after it.

**First case — there are blocking bugs.** If blocking_bugs is greater than 0, write out this
line exactly, on a line of its own:

[fixture-w2-release-gate][main] BRANCH: branch-0

Then give the verdict `BLOCKED` and stop.

**Second case — coverage is too low.** If coverage is below 80, write out this line exactly, on
a line of its own:

[fixture-w2-release-gate][main] BRANCH: branch-1

Then give the verdict `INSUFFICIENT_COVERAGE` and stop.

**Third case — security review has not passed.** If security_review is anything other than
`passed`, write out this line exactly, on a line of its own:

[fixture-w2-release-gate][main] BRANCH: branch-2

Then give the verdict `SECURITY_HOLD` and stop.

**Fourth case — none of the above.** If none of the three cases above fits the record, write out
this line exactly, on a line of its own:

[fixture-w2-release-gate][main] BRANCH: branch-else

Then give the verdict `READY`.

In every case, write the line first and give the verdict afterwards.

### What you return

The object you return carries a single key, `verdict`, spelled in lower case, and no other keys
alongside it. Its value is a string, and it is one of exactly these five: `BLOCKED`,
`INSUFFICIENT_COVERAGE`, `SECURITY_HOLD`, `READY`, `INVALID_INPUT` — written in capitals as they
appear here. It is never empty and never absent.

The branch line you wrote out is not part of that object; it stands on its own, outside what is
returned.

The object has this shape:

```json
{
  "verdict": "THE_VERDICT"
}
```
