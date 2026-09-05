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

Evaluate the release record by following strictly the procedure described below.

## File content

```json
{{file_content}}
```

## The procedure

### What it does

- Run exactly: `cat {{record_path}}` [from context: record_path]
- If record_path was not provided, the file could not be read, or the record is missing any of coverage / blocking_bugs / security_review, or a field has the wrong type, then:
  - Emit verbatim: [fixture-w2-release-gate][main] BRANCH: branch-guard
  - End this process and hand control back to whoever invoked it, yielding: {"verdict": "INVALID_INPUT"}
- Depending on the case:
  - When blocking_bugs is greater than 0:
    - Emit verbatim: [fixture-w2-release-gate][main] BRANCH: branch-0
    - End this process and hand control back to whoever invoked it, yielding: {"verdict": "BLOCKED"}
  - When coverage is below 80:
    - Emit verbatim: [fixture-w2-release-gate][main] BRANCH: branch-1
    - End this process and hand control back to whoever invoked it, yielding: {"verdict": "INSUFFICIENT_COVERAGE"}
  - When security_review is not "passed":
    - Emit verbatim: [fixture-w2-release-gate][main] BRANCH: branch-2
    - End this process and hand control back to whoever invoked it, yielding: {"verdict": "SECURITY_HOLD"}
  - Otherwise:
    - Emit verbatim: [fixture-w2-release-gate][main] BRANCH: branch-else
    - End this process and hand control back to whoever invoked it, yielding: {"verdict": "READY"}
