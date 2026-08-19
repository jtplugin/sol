# Closing the series: SOL is open source, and here's exactly what that means

Six articles in, the picture is complete: a problem (an intermediate layer of automation without a standard), a format (JSON, the agent as the runtime), a vocabulary (`TODO`/`RUN`, control flow, delegation), and a file shape (JSON inside Markdown). What's left to say isn't about the language — it's about the project around it.

SOL is open source, MIT licensed, hosted at [github.com/jtplugin/sol](https://github.com/jtplugin/sol). Saying that and stopping there would be the easy, slightly hollow way to close a series. Here's the honest version instead: what's actually in the repository, what's deliberately unfinished, and what a contribution looks like.

---

## What's there today

- **The spec itself** — currently line `0.6`, the single source of truth. Everything else in the repo derives from it, not the other way around.
- **Design rationale** — `DESIGN.md` and `why-sol-works.md` justify every choice, including the ones that look like omissions (no variables, no execution strategy, no determinism guarantees). If you're wondering "why not X", there's a good chance it's answered there already.
- **A comparison map** — against LangGraph, CrewAI, AutoGen, and others, positioning SOL as the intermediate layer rather than a competitor to full orchestration frameworks.
- **Authoring tooling** — a Claude Code skill (`sol-translate`) that turns prose, pseudocode, YAML, or XML into valid SOL, and tooling that goes the other way: `sol2mermaid.py` and `sol2drawio.py` project a SOL process onto a diagram a non-JSON reader can follow.
- **Worked examples** — real SOL processes in `examples/`, not just spec snippets.

---

## What's deliberately not finished

This part matters more than the list above. A project that claims to be done is usually overselling itself.

**Testing is a method, not yet a suite.** `doc/testing-sol.md` lays out *how* to evaluate SOL faithfully — separating execution fidelity from outcome quality, across a language × harness × model matrix — but the runners and the results pipeline are still being built out. Concrete use in Claude Code is, by all accounts so far, more than satisfying; that's a different claim from "rigorously measured everywhere."

**Predictability strategies are scoped, not written.** The previous article in this series ended on an open thread: SOL can pressure context isolation from inside the language, but nothing forces a model choice without an external layer. The trade-offs of each layer — prompt directive, harness feature, small deterministic runtime, foreign orchestrator — are mapped but not yet the subject of the dedicated article they deserve.

**The issue tracker is short, on purpose.** At the time of writing there's exactly one open enhancement request, asking for tooling to convert between SOL and draw.io diagrams in both directions. A short tracker isn't a sign of a finished project — it's a sign of a young one where most of the surface hasn't been stress-tested by outside use yet. That's an invitation, not a flaw to hide.

---

## What a contribution actually looks like

`CONTRIBUTING.md` is short for a reason — the project would rather you read it than skim past it. The shape of it:

- **The spec is the source of truth.** If a change isn't in the spec, it isn't SOL. Schema, README, examples — they all derive from it, never the other way around.
- **Open an issue before a spec-changing PR.** Proposals for new instructions need motivation, an example, and an edge-case analysis — the same bar this series tried to hold itself to.
- **Articles need no issue at all.** The `articles/` folder takes PRs directly: new pieces, translations, case studies. This very series lives under that rule.
- **Versioning is semantic and explicit** — patch for clarifications, minor for backwards-compatible additions, major for breaking changes to existing semantics.

---

## Why end here

A spec that fits in one document, a runtime that's just "the agent," and a project that says plainly where it stops being finished — that combination is the actual pitch, more than any single feature covered in the last six articles. If an intermediate layer of automation is missing a standard, the way to find out whether SOL fills that gap isn't to take this series' word for it. It's to write one process, hand it to an agent, and see what happens.

Repository: https://github.com/jtplugin/sol — issues and PRs welcome.

---
*Author: Gianni Tommasi*
