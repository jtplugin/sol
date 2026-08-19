# Agent Runtime: SOL — A New Frontier in AI Orchestration

AI agent orchestration is undergoing a fundamental transition: from using isolated models to creating complex ecosystems where multiple specialised entities collaborate to solve sophisticated tasks. Below is an overview of the leading orchestration approaches currently shaping the landscape, and the distinctive role of **SOL** (*Simple Orchestration Language*) within it.

## Current Approaches to Orchestration

Today, the market and research ecosystem offer three main categories of solutions.

### Open-Source Code-First Frameworks (LangGraph, CrewAI, AutoGen)

These tools model agent interactions directly through code.

- **LangGraph** uses finite-state graphs and checkpointing to provide persistence and granular execution control.
- **CrewAI** focuses on role-based delegation (backstories, goals, responsibilities), offering a lower learning curve.
- **AutoGen** (now AG2) emphasises inter-agent conversation as a peer-to-peer coordination mechanism.

These frameworks provide maximum flexibility, but they also require significant DevOps infrastructure and advanced AI engineering expertise.

### Vertically Integrated Data Platforms (Snowflake, Databricks)

In this model, orchestration happens where the data already resides.

The approach prioritises unified governance and security, allowing agents to query governed datasets without large-scale data movement. The main limitation is the risk of vendor lock-in and the difficulty of orchestrating workflows across distributed multi-cloud environments.

### Hybrid Enterprise Architectures (The "Trident" Pattern)

Many enterprises adopt hybrid approaches that combine a deterministic backbone (rule engines, workflow systems) with bounded agentic nodes.

This ensures that critical steps remain auditable and repeatable, while AI is only introduced where interpretative or adaptive reasoning is required.

## SOL: The Agent as the Runtime

SOL (*Simple Orchestration Language*) enters this landscape with a different paradigm: **the agent itself becomes the runtime**.

Where other approaches require dedicated interpreters, SDKs, or orchestration engines to execute workflows, SOL is a minimal JSON format that the agent can directly read, understand, and execute autonomously.

## What Makes SOL Different

### No Dependencies

SOL does not require SDKs or complex execution environments.

Any sufficiently capable LLM can interpret the specification and execute it, effectively removing the gap between "describing what to do" (natural language) and "programming how to do it" (Python or workflow code).

### TODO and RUN: an inversion of control

Unlike traditional workflow systems, SOL distinguishes between:

- **TODO** instructions, expressed in natural language, where the agent decides which steps and tools to use
- **RUN** commands, executed literally to preserve strict control over critical operations

The deeper shift is not the natural-language/verbatim split but the *direction* of control. In classical automation a deterministic engine drives the flow and calls an AI step where judgment is needed; intelligence is a plugin inside a mechanical pipeline. SOL reverses this: the agent orchestrates, and RUN is the deterministic operation it reaches for when exactness matters. Determinism is no longer the engine that calls the AI — it is what the AI calls.

### Semantic Model Tiers

Instead of binding workflows to specific model IDs (e.g. gpt-4o), SOL uses semantic execution tiers such as:

- fast
- balanced
- smart

The executing agent decides which underlying model best fits the task complexity at runtime.

### Modular and Multi-Agent by Design

Another defining characteristic of SOL is its openness to modular composition and explicit multi-agent behaviour design.

SOL workflows can be structured as reusable building blocks, enabling orchestration patterns to evolve incrementally instead of being tightly coupled to a single monolithic execution graph.

This modularity makes it possible to:

- compose reusable agent skills
- delegate responsibilities across specialised agents
- define hierarchical or collaborative execution patterns
- separate planning, execution, validation, and review phases across different agent roles

Rather than treating multi-agent behaviour as an implementation detail hidden inside framework code, SOL allows these interaction patterns to become part of the orchestration specification itself.

This makes workflows more portable, inspectable, and adaptable across different runtimes and agent ecosystems.

### Natural Language Compilation into SOL

To reduce the barrier to adoption, SOL also supports a translation layer that converts natural language, YAML, or XML descriptions into executable SOL specifications.

A dedicated skill can transform human-readable workflow descriptions into structured SOL documents, allowing users to define orchestrations without manually editing JSON.

This approach provides several advantages:

- non-technical users can describe workflows conversationally
- existing YAML or XML process definitions can be adapted with minimal friction
- orchestration logic remains inspectable and structured after conversion
- teams can progressively refine workflows from informal descriptions into deterministic execution patterns

In practice, this means SOL can function both as:

- a low-level orchestration format
- and as a compilation target for higher-level human-oriented descriptions

This further reinforces SOL's philosophy that the agent should interpret and execute intent directly, rather than forcing developers to fully encode orchestration logic in traditional programming abstractions.

## Strategic Positioning

Compared to complex orchestration frameworks such as LangGraph, SOL positions itself as an intermediate automation layer.

It is particularly well suited for describing reusable agent *skills* in environments such as Claude Code or Cursor, where purely prose-based instructions become ambiguous once loops (REPEAT) or complex conditional branches (IF, WHEN) are introduced.

Where classical orchestration focuses on building deterministic AI-driven machines, SOL instead leverages the agent's reasoning capabilities to transform a structured document into coherent action.

The result is reduced development complexity while preserving as much flow control as possible.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi — [Published on LinkedIn](https://www.linkedin.com/pulse/agent-runtime-sol-new-frontier-ai-orchestration-gianni-tommasi-zut6f)*
