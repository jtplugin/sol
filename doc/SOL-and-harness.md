# SOL and the Agentic Harness

> Where SOL fits in the ecosystem of AI coding engines — and what it brings to each.

---

## What every AI coding engine is actually doing

Behind the different UIs and brand names, every current AI coding engine — Claude Code, Cursor, Windsurf, GitHub Copilot — is solving the same structural problem: how do you turn a stateless language model into something that can carry out a multi-step task on a real codebase?

The answer, in every case, is some form of **agentic harness**: an execution layer that provides tools (file read/write, shell, search), manages context, enforces permissions, and runs the model in a loop until the task is done.

Anthropic uses the term officially. The others don't, but the architecture is the same.

SOL is not a harness. SOL is a format for defining what a harness executes. The distinction matters: SOL doesn't manage tools, context windows, or permissions — it describes a process that an agent running inside a harness can read and carry out.

---

## The gap SOL fills

Every harness needs to answer: *what should the agent do?*

Today, the answer is almost always prose — a Markdown file, a block of text in a Rules file, a system-prompt addition. This works for linear, simple tasks. It breaks down when the task has:

- conditional branches ("if the tests fail, do X; otherwise Y")
- iteration ("for each changed file, check Z")
- reusable sub-steps invoked from multiple points
- phases with different cognitive demands (fast scan vs. deep analysis)

In these cases, prose is ambiguous. Different runs interpret the same instructions differently. The harness has no way to know whether the agent followed the intended control flow or improvised.

SOL's primitives — `IF`, `WHEN`, `REPEAT`, `SUB`, `CALL`, `ONERROR` — express this structure without adding a runtime dependency. The agent still interprets and executes; SOL just makes the intent unambiguous.

---

## Claude Code: the natural home

Claude Code exposes the harness as a **programmable surface**: lifecycle hooks (`SessionStart`, `PreToolCall`, `Stop`), fine-grained permissions per tool and pattern, a skill system with structured Markdown files, versioned configuration in `settings.json`. This is intentional design — Claude Code is built for developers who want control over what the agent does and when.

SOL slots into this model at the skill layer. A Claude Code skill today is a Markdown file that Claude reads and follows. When the skill has real control flow, that Markdown becomes ambiguous. SOL provides the structured core:

```markdown
# skill: sync-dependencies

**Trigger:** user asks to update or audit project dependencies.
**Prerequisites:** `package.json` present, clean working tree.

## Process

```json
{
  "name": "sync-dependencies",
  "ROUTINE": [
    { "TODO": "Read package.json and note current versions" },
    { "RUN": "npm outdated --json" },
    {
      "IF": {
        "when": "any package has a major version update available",
        "then": [
          { "TODO": "List breaking changes from changelogs" },
          { "TODO": "Ask the user before updating those packages" }
        ],
        "else": [
          { "RUN": "npm update" }
        ]
      }
    },
    { "RUN": "npm run test" },
    {
      "IF": {
        "when": "tests fail",
        "then": [{ "TODO": "Revert the update, report which package caused the failure" }]
      }
    }
  ]
}
```

## Notes

- Don't update devDependencies unless the user asks explicitly.
```

The Markdown wrapper carries human context; the SOL block carries the executable logic. Together they serve both audiences: a developer reading the skill file, and Claude executing it.

Beyond skills, SOL maps cleanly onto the hook lifecycle. A `SessionStart` hook today is typically a shell script that runs setup commands. A complex setup sequence — conditional on branch, environment, or project type — could be described in SOL and passed to an agent invoked by the hook, rather than encoded as imperative shell with embedded heuristics.

The alignment is not accidental: Claude Code's premise (the agent is the runtime) and SOL's premise (the agent is the runtime) are the same.

Where this alignment leaves a gap — making a `SPAWN` reliably isolated or a `model` tier
reliably honored — Claude Code's surface (native sub-agents with a `model:` frontmatter, hooks)
is also where you close it. The layered options are catalogued in
[predictability-strategies.md](predictability-strategies.md).

---

## Cursor: good fit, lower surface area

Cursor's equivalent of skills is the `.cursor/rules/*.mdc` system: Markdown files with YAML frontmatter that control when a rule is injected into context. The `agent_requested` trigger makes rules invocable on demand, similar to Claude Code slash commands.

The gap: `.mdc` files are prose only. There is no control flow, no loops, no sub-routines. A rule that says "when reviewing a PR, check X then Y then Z, but if the branch is main, also check W" is expressed as a paragraph, and the agent may or may not follow the intended sequence.

SOL could be embedded in `.mdc` files the same way it embeds in Claude Code skills — a JSON block inside a Markdown wrapper. The `agent_requested` trigger would invoke it; the agent (Cursor's underlying model) would interpret the SOL process. No Cursor-specific changes needed.

What SOL adds to Cursor rules:

| Without SOL | With SOL |
|---|---|
| "Check A, then B, then if C do D" in prose | `IF`/`WHEN` blocks with explicit branches |
| Repeated logic copied across rules | `SUB` + `CALL` for shared sub-steps |
| No way to hint at reasoning depth | `model: "smart"` on reasoning-heavy phases |
| Non-deterministic ordering | Named `SUB`s give explicit sequencing |

The harness (Cursor's execution loop) doesn't change. The process definition becomes less ambiguous.

---

## Windsurf: same story, different name

Windsurf's Rules system (`.windsurfrules`, workspace rules, global rules) is architecturally similar to Cursor's. Cascade, the underlying agentic engine, executes rules as plain text instructions.

The same pattern applies: SOL embedded as a JSON block inside a Windsurf rules file gives Cascade a structured process to follow rather than prose to interpret. The benefit is identical — explicit branching, loops, reuse, model tier hints.

One practical consideration: Windsurf's rules cascade from global to workspace to project, with lower levels able to override higher. An SOL block in a workspace rule is still plain text to Windsurf's loader — it doesn't need special handling. Cascade receives the full rule text including the JSON, parses it, and executes it. The embedding is transparent to the harness.

---

## GitHub Copilot: limited applicability today

Copilot's instruction system (`GITHUB_INSTRUCTIONS`, `.github/copilot-instructions.md`) is prose-only and not invocable as discrete skills. The execution model is primarily reactive — inline completions and chat responses — rather than an agentic loop that could follow a multi-step process.

Copilot Workspace (the agentic mode) is more promising but the instruction surface is not yet open enough to embed a structured process. SOL's fit here is minimal in current form; it may become relevant as Copilot's agentic capabilities mature and expose a configurable skill or instruction layer.

---

## What SOL does not replace

It's worth being explicit about what SOL is not.

**SOL is not a hook.** Hooks are automation at the harness boundary — they run before/after tool calls, enforce policies, trigger on session events. SOL is the content of what an agent executes, not the trigger mechanism.

**SOL is not a permissions system.** Which tools the agent can use, which files it can read, which shell commands it can run — all of this is governed by the harness configuration (`settings.json`, `.windsurfrules` restrictions, etc.). SOL assumes the agent has the access it needs; it doesn't grant or restrict it.

**SOL is not a runtime.** There is no SOL interpreter, no SOL executor. The agent is the executor. SOL is the format that structures what the agent executes.

---

## The common premise

Every AI coding engine in active development today is converging on the same architectural insight: **the agent is the runtime**. The harness provides the environment; the agent provides the judgment. Configuration files (settings, rules, skills) tell the agent what to do; the agent decides how.

SOL makes the "what to do" part precise. It is not tied to any single harness — it requires only an agent capable of reading a JSON document and following control flow. Any engine that has reached the "agent as runtime" stage can interpret SOL processes.

The differentiator today is surface area: Claude Code exposes enough of the harness to make SOL genuinely powerful (structured skills, hooks, permissions). Cursor and Windsurf have the right execution model but less configurability. Others are further behind.

As the field matures and harness surfaces become more open, a common process definition language becomes more valuable. SOL is a candidate for that role — not because it is ambitious, but because it is minimal. It adds structure without adding a runtime, and structure is what prose-based instruction systems most lack.

---

## See also

- [predictability-strategies.md](predictability-strategies.md) — how to make a `SPAWN` or a `model` tier reliably realized, layer by layer.
- [SOL-and-models.md](SOL-and-models.md) — which SOL workloads run with confidence on which model + environment, from a bare API call to a full harness.
- [testing-sol.md](testing-sol.md) — a method for measuring execution fidelity across language/harness/model configurations.
