# Using SOL to Describe Claude Code Skills

> When and how to use SOL to define Claude Code skills instead of (or alongside) prose instructions.

## Background: what is a Claude Code skill

A Claude Code skill is a Markdown file that Claude reads when a user invokes a slash command
(e.g. `/review`, `/init`). It extends Claude's behavior for a specific task — no runtime, no
compilation. Claude reads the file and follows it.

This is exactly the execution model SOL was designed for: **the agent is the runtime**.

---

## Why SOL fits

Prose instructions work well for simple, linear skills. They break down when a skill has:

- Conditional branches ("if the branch is main, also check X")
- Loops ("for each changed file, do Y")
- Distinct phases with different cognitive demands
- Reusable sub-steps invoked from multiple points

In these cases, prose becomes ambiguous. SOL's control flow primitives — `IF`, `WHEN`,
`REPEAT`, `SUB`, `CALL` — express intent more precisely without adding runtime dependencies.

---

## When to use SOL in a skill

Use SOL (or a hybrid) when:

| Situation | Benefit |
|---|---|
| Multiple conditional branches | `IF` / `WHEN` replaces ambiguous "if … then …" prose |
| Iteration over a collection | `REPEAT foreach` is unambiguous |
| Reusable sub-steps | `SUB` + `CALL` avoids repetition |
| Different cognitive load per phase | `model` tier (`fast` / `smart`) hints at required reasoning depth |
| The skill is long enough to have internal structure | Sections become named `SUB`s, easier to reference |

Skip SOL when:

- The skill is a short, linear sequence (3–5 steps, no branches) — prose is more readable
- The skill is primarily a system-prompt extension with heuristics rather than a process
- The author can't test the skill enough to validate that Claude's interpretation is stable

---

## The hybrid pattern

The most practical approach is **not** to replace the skill file with pure SOL, but to keep a
Markdown wrapper and embed an SOL block for the executable logic:

```markdown
# skill: project-scan

**Trigger:** user asks to scan repositories or sync the vault.
**Prerequisites:** `GH_TOKEN` env var with `repo` read scope.

## Process

​```json
{
  "name": "project-scan",
  "description": "Scan configured GitHub repositories and update the ingest queue.",
  "ROUTINE": [
    { "TODO": "Read project-sources.md and collect active sources" },
    {
      "REPEAT": {
        "foreach": "active source",
        "ROUTINE": [
          { "RUN": "main.py vault-scan {{source-id}}" },
          { "TODO": "Update SHA manifest for processed files" },
          {
            "IF": {
              "when": "RUN produced errors",
              "then": [{ "TODO": "Log error in log.md, continue to next source" }]
            }
          }
        ]
      }
    },
    { "TODO": "Report: scanned N, new M, updated K, errors E" }
  ]
}
​```

## Notes

- Sources marked `disabled` in project-sources.md are skipped without logging.
- SHA manifest is updated only after a file is fully ingested, not on scan.
```

The Markdown wrapper carries human-readable context (trigger, prerequisites, notes). The SOL
block carries the executable logic. Together they serve both audiences: a human reading the
skill file and Claude executing it.

---

## Using `model` tiers in skills

Some skills have phases with very different cognitive demands. The `model` field lets you
declare this explicitly without committing to a specific model ID:

```json
{
  "name": "code-review",
  "model": "balanced",
  "ROUTINE": [
    {
      "SUB": {
        "name": "collect-diff",
        "model": "fast",
        "ROUTINE": [
          { "TODO": "Run git diff against base branch" },
          { "TODO": "List changed files by type" }
        ]
      }
    },
    {
      "SUB": {
        "name": "analyze",
        "model": "smart",
        "ROUTINE": [
          { "TODO": "Identify logic errors, security issues, missing edge cases" },
          { "TODO": "Check consistency with the rest of the codebase" }
        ]
      }
    },
    { "CALL": "collect-diff" },
    { "CALL": "analyze" },
    { "TODO": "Write a structured review: summary, issues by severity, suggestions" }
  ]
}
```

`fast` for mechanical data collection, `smart` for reasoning-heavy analysis. Claude decides
whether to handle each phase inline or spawn a sub-agent — the skill author doesn't need to
care about the mechanics.

---

## Caveats

**Interpretation is not deterministic.** Claude reads SOL as text, it does not execute a
formal specification. Two runs of the same skill may interpret an ambiguous `IF` condition
differently. This is inherent to any agent-native format — SOL reduces ambiguity compared to
prose, it does not eliminate it.

**Consequence:** test complex skills before relying on them. If a branch is always taken (or
never), rewrite the condition as plain prose in a `TODO`.

**`RUN` still goes through Claude.** A `RUN` instruction in a skill causes Claude to call its
Bash tool (or equivalent). This means it is subject to the user's permission settings — it
won't silently bypass sandboxing.

**Keep SOL blocks self-contained.** A skill file may be loaded without surrounding
conversation context. Don't reference variables or state that exist only in conversation
history — make the SOL block readable cold.

---

## Summary

SOL adds value to a Claude Code skill when the skill has real control flow. Use it as the
executable core of a Markdown wrapper: the Markdown carries context and notes, the SOL block
