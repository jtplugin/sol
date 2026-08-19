# From Thought to Process: The Skill That Writes SOL for You

In the landscape of AI agent orchestration, the **SOL (Simple Orchestration Language)** format stands out for its philosophy: the agent is the runtime. Although SOL uses a minimal JSON format to ensure the absence of the ambiguities typical of formats like YAML, this does not mean users must necessarily write code.

While it is possible to edit JSON by hand or with VS Code or other tools to make life easier among square brackets and curly braces, we would like to simplify life for humans after having simplified it for agents...

A **specific skill** is currently under development, designed to bridge the gap between human intent and the — admittedly simple — formal structure. This skill allows one to describe a process in **natural language**, or to import existing definitions in **XML or YAML**, automatically converting them into a valid, execution-ready SOL file.

## Precision and Error Reduction

Unlike traditional formats designed for deterministic machines, SOL delegates the interpretation of the more flexible steps (the `TODO` instructions) to the agent's judgment. This approach, combined with the stability of JSON as a base format, drastically reduces the possibility of errors in workflow generation. The skill does not need to "invent" complex logic, but simply maps the user's intent onto SOL's control primitives (such as `IF`, `WHEN`, or `REPEAT`).

## Handling Ambiguity: The Dialogue with the User

One of the key strengths of this skill must be its ability not to proceed "blind" in the presence of **contradictions or ambiguities** in the input text. Being based on an intelligent agent, the skill can be instructed to:

- Identify incomplete or conflicting logical steps.
- Engage directly with the user to ask for clarifications.
- Use the native `WAITUSERINPUT` instruction to insert checkpoints into the final process where human intervention is structurally expected.

This transforms the creation of an automation from a solitary programming activity into a **guided conversation**, where the final result is a self-explanatory document that the agent can execute with full autonomy and judgment.
