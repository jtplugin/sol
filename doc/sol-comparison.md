# The Agent Is the Runtime: SOL and the New Frontier of AI Orchestration

AI agent orchestration is undergoing a fundamental transition: from the use of isolated models to the creation of complex ecosystems in which multiple specialized entities collaborate to solve articulated tasks. Below is an analysis of the main current approaches and the distinctive role of SOL (Simple Orchestration Language) in this landscape.

## Current Approaches to Orchestration

Today, the market and research offer three main categories of solutions:

**Open-Source Code-First Frameworks (LangGraph, CrewAI, AutoGen)**: These tools model agent interaction through code.
- LangGraph uses finite-state graphs and checkpointing to ensure persistence and granular control
- CrewAI focuses on role-based delegation (backstory, objectives), offering a lower learning curve
- AutoGen (now AG2) centers on agent conversation as a peer-to-peer coordination mechanism
- These frameworks offer maximum flexibility but require significant DevOps infrastructure and AI engineering expertise

**Vertically Integrated Data Platforms (Snowflake, Databricks)**: In this model, orchestration happens where the data resides. The approach prioritizes uniform governance and security, allowing agents to query governed data without massive data movement. The main limitation is the risk of vendor lock-in and the difficulty of managing data distributed across different clouds.

**Hybrid Enterprise Architectures (the "Trident" Pattern)**: Many companies adopt an approach that combines a deterministic backbone (rules engine) with bounded agentic nodes. This ensures that critical steps are auditable and repeatable, while AI intervenes only where interpretive capacity is needed.

## SOL: The Agent as Runtime

SOL (*Simple Orchestration Language*) enters this scenario by proposing a paradigm shift: the agent is the runtime.

While other approaches require a specific interpreter or SDK to execute the flow, SOL is a minimal JSON format that the agent reads, understands, and executes autonomously.

Distinctive features of SOL compared to other approaches:
- **No Dependencies**: SOL does not require SDKs or complex execution environments. Any sufficiently capable LLM can interpret the spec and execute it, eliminating the gap between "saying what to do" (prose) and "programming how to do it" (Python)
- **TODO and RUN — the inversion of control**: The point is not "natural language vs verbatim command" but the *direction* of the call. In classical automation a deterministic orchestrator drives the flow and invokes AI only where judgment is needed: intelligence is a plugin inside a mechanical pipeline. SOL reverses the direction: the agent orchestrates and *descends* into deterministic operations when and where they are needed. TODO is where the agent exercises judgment; RUN is the verbatim, algorithmic operation the agent invokes. Determinism is no longer the engine that calls the AI — it is what the AI calls
- **Semantic Model Tiers**: Instead of binding the process to specific IDs (e.g. "gpt-4o"), SOL uses semantic levels (fast, balanced, smart). The executing agent decides which model to use for that specific task based on complexity
- **Human checkpoint as intent, not guarantee**: The `WAITUSERINPUT` instruction lets a process mark where a human decision belongs — but it is a context-dependent shortcut: it works only when execution is guaranteed interactive (the harness supports mid-process pausing), and otherwise degrades to a clean stop. For a human gate that holds in any context, the robust pattern is process decomposition: two SOL processes with the human decision between them

## Strategic Positioning

Compared to complex frameworks like LangGraph, SOL positions itself as an intermediate layer of automation.

It is ideal for describing the *skills* of agents to be used in environments like Claude Code or Cursor, where prose instructions become ambiguous when presenting loops (REPEAT) or complex conditional branches (IF, WHEN).

While classical orchestration focuses on building deterministic machines guided by AI, SOL exploits the agent's capacity for judgment to transform a structured document into a coherent action, reducing development complexity while maintaining as much control over the flow as possible.

[https://github.com/jtplugin/sol]
