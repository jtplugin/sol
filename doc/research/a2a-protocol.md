# A2A — Agent-to-Agent Protocol

> Research notes. Sources: Linux Foundation, a2a-protocol.org, GitHub a2aproject/A2A, arXiv, Palo Alto Unit 42, Spring AI, AWS docs. May 2026.

---

## Origin and Governance

A2A was announced by Google on **April 9, 2025**, with over 50 partner organizations at launch. On **June 23, 2025** Google donated the protocol to the **Linux Foundation**, where it became the "Agent2Agent Protocol Project". LF founding members: AWS, Cisco, Google, Microsoft, Salesforce, SAP, ServiceNow.

In **December 2025** the Linux Foundation launched the **Agentic AI Foundation (AAIF)**, a broader umbrella co-founded by OpenAI, Anthropic, Google, Microsoft, AWS and Block. AAIF hosts both A2A and MCP under the same governance, resolving what for several months appeared to be a clash between parallel standards.

A2A reached stable version **v1.0.0** on March 12, 2026. The GitHub repo (`github.com/a2aproject/A2A`) has over 23,900 stars, 560 commits, 233 open issues as of May 2026. Versions go through a public RFC process with Architecture Decision Records (ADRs) documented in `/adrs/`.

In **May 2026** the protocol surpassed 150 member organizations.

**Official spec**: https://a2a-protocol.org/latest/specification/
**GitHub**: https://github.com/a2aproject/A2A

---

## Positioning — A2A vs MCP

MCP (Anthropic, now also AAIF) and A2A are complementary, not competing. They operate at different levels of the same stack:

| | MCP | A2A |
|---|---|---|
| Connects | Agent ↔ Tool / Resource | Agent ↔ Agent |
| Capability contract | Typed schema (JSON Schema) | Natural language description |
| Agents are seen as | Invocable tools | Opaque black boxes |
| Call pattern | Structured tool call | Task conversation |
| Governance | AAIF (Linux Foundation) | AAIF (Linux Foundation) |

In practice: an agent uses MCP to connect to databases, APIs and local tools; it is reached via A2A by other agents that delegate work to it. The two protocols coexist in the same architecture.

---

## Transport and Format

**HTTP + JSON-RPC 2.0**. All client requests are HTTP POST with `Content-Type: application/json`. Responses are `JSONRPCResponse` objects. Nothing exotic — any HTTP client can speak A2A.

For streaming, **Server-Sent Events (SSE)** are used: the server responds with `Content-Type: text/event-stream` and each `data:` contains a `JSONRPCResponse` with partial updates.

---

## Core Primitives

### AgentCard

The discovery document. Served via HTTP GET at the conventional URL `/.well-known/agent-card.json`. There is no central registry — discovery is based on this path convention.

```json
{
  "name": "Weather Agent",
  "description": "Provides weather information for cities worldwide",
  "url": "http://localhost:8080/",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "capabilities": {
    "streaming": true
  },
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "skills": [
    {
      "id": "weather_search",
      "name": "Search weather",
      "description": "Get current temperature and conditions for any city",
      "tags": ["weather", "forecast"]
    }
  ],
  "securitySchemes": {
    "bearerAuth": { "type": "http", "scheme": "bearer" }
  }
}
```

**Critical note**: skills have a natural language `description` and `tags`, but **do not have a typed input/output schema**. Unlike MCP, the caller does not deterministically know what to send — it relies on the textual description. Agents are treated as black boxes by design.

---

### Task

The fundamental unit of work. Identified by a unique ID. Has a defined lifecycle:

```
submitted → working → completed  (terminal)
                    → canceled   (terminal)
                    → rejected   (terminal)
                    → failed     (terminal)
```

A task in a terminal state cannot be restarted. The client can query state with `tasks/get` or cancel with `tasks/cancel`.

---

### Message

A turn in the conversation between client and agent. Each message has a `role` (`user` or `agent`) and is composed of one or more **Parts**.

```json
{
  "messageId": "msg-abc123",
  "role": "user",
  "parts": [
    { "kind": "text", "text": "What is the weather in Berlin?" }
  ]
}
```

---

### Part

The atomic unit of content inside a Message or an Artifact. Three subtypes:

| Kind | Use |
|---|---|
| `text` | Plain text or markdown |
| `file` | File (inline base64 or external URL) |
| `data` | Arbitrary structured JSON |

---

### Artifact

An output produced by the agent: document, image, structured data. Composed of Parts. Attached to the Task, represents the completed deliverable. Can be streamed incrementally via SSE.

---

## JSON-RPC Methods

| Method | Description |
|---|---|
| `message/send` | Sends a message, receives synchronous response |
| `message/stream` | Sends a message, receives response in SSE streaming |
| `tasks/get` | Retrieves state and result of a task by ID |
| `tasks/cancel` | Cancels an in-progress task |
| `tasks/resubscribe` | Reconnects to an SSE stream after disconnection |
| `tasks/pushNotification/set` | Registers webhook for push notifications |
| `tasks/pushNotification/get` | Reads the active webhook configuration |

### Example — sending a message

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "id": 1,
  "params": {
    "message": {
      "messageId": "msg-123",
      "role": "user",
      "parts": [{ "kind": "text", "text": "What is the weather in Berlin?" }]
    }
  }
}
```

---

## Long-Running Tasks and Push Notifications

For tasks lasting minutes or hours, the client can register a webhook:

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/pushNotification/set",
  "id": 2,
  "params": {
    "taskId": "task-xyz",
    "pushNotificationConfig": {
      "url": "https://myclient.example.com/webhook",
      "authentication": { "schemes": ["bearer"] }
    }
  }
}
```

The server sends HTTP POST to that URL as the task progresses, without requiring a persistent SSE connection.

---

## Authentication

The AgentCard declares the supported schemes. The protocol supports OAuth 2.0 and API key as primary patterns. Enterprises typically use OAuth 2.0 bearer tokens. Verification is delegated to the implementation — the protocol does not prescribe the mechanism, only the declaration point (AgentCard `securitySchemes`).

---

## Official SDKs

| Language | Installation |
|---|---|
| Python | `pip install a2a-sdk` |
| JavaScript | `npm install @a2a-js/sdk` |
| Java | Maven (`a2a-sdk`) |
| Go | Go module |
| .NET | NuGet |

---

## Adoption in Frameworks

### Google ADK (Agent Development Kit)
Native A2A support from v1.0 (April 2025). Automatically generates AgentCard for ADK agents. The hierarchical ADK model (root → sub-agents) can delegate to external A2A agents cross-framework.

### LangGraph
Native A2A support. LangSmith Agent Server automatically exposes `POST /` (JSON-RPC endpoint) and `GET /.well-known/agent-card.json` for any deployed LangGraph graph.

### CrewAI
A2A task delegation added in 2026. Crews can be exposed as A2A servers and invoke external A2A agents as if they were crew members.

### Spring AI
Official integration: `DefaultAgentExecutor` bridges Spring AI's `ChatClient` and the A2A transport. Distributed via standard Maven.

### Semantic Kernel, LlamaIndex, AutoGen / AG2
Native A2A support announced with the Linux Foundation May 2026 milestone.

### OpenAI Agents SDK
**No native A2A support**. The SDK uses an internal "handoff" model — agents explicitly transfer control within the same deployment. Cross-vendor discovery via A2A is not a first-class feature. Integrating OpenAI Agents SDK into an A2A network requires custom adapters.

### AWS Bedrock AgentCore
Documented A2A protocol contract support. AWS is an LF founding member.

---

## Production Deployments (Real Cases)

- **Salesforce Agentforce**: each custom agent exposed as an A2A endpoint; partner agents invocable from Flow.
- **SAP Joule**: delegates subtasks (legal review, finance check) to A2A partner agents cross-system S/4HANA.
- **ServiceNow Now Assist**: A2A agents registered as skills; incident triage in fan-out to specialized agents.
- **AWS Bedrock AgentCore**: A2A support documented in the developer guide.

---

## Limitations and Critical Issues

### No Typed Contract for Skills
Skills in the AgentCard have a name, textual description and `tags`, but no JSON Schema for input/output. Unlike MCP, the caller cannot deterministically verify what to send. Automated orchestration must rely on natural language descriptions — suitable for LLM agents, fragile for deterministic systems.

### Weak Trust Model at the Boundary
The protocol delegates identity verification to OAuth 2.0 / API key, but does not define how an orchestrator validates that a remote AgentCard is authentic. A malicious agent can publish an AgentCard with false capabilities and intercept tasks.

### Agent Session Smuggling
Palo Alto Unit 42 documented a concrete attack class: payloads injected inside A2A messages can hijack task context across agent boundaries. A2A's message-passing model creates channels for cross-agent context corruption.

### Amplified Prompt Injection
In multi-agent chains, an injection in one agent's input propagates via A2A calls to downstream agents. The protocol has no message filtering or sanitization layer.

### Token Lifetime and Consent Gap
The arXiv:2505.12490 paper documents that A2A's OAuth integration does not enforce expiration durations for sensitive transactions. Leaked tokens can remain valid for hours/days. Consent flows required by financial regulations (PSD2, etc.) are also absent.

### No Standardized Semantics for Agent-Level Errors
JSON-RPC error codes cover transport errors. No vocabulary exists for agent-level failures (policy refusal, capability mismatch, rate limiting) — error handling is left to implementer convention.

### "Opaque by Design" — Feature and Bug
The protocol intentionally treats agents as black boxes. Practical for integration, but means no behavioral guarantees: you cannot verify what a remote agent will do before delegating a task to it.

### AAIF Governance Tension
A2A was donated to the LF in June 2025; AAIF was created six months later with OpenAI/Anthropic. The two governance frameworks were briefly parallel competing structures. Consolidation under AAIF is still being formalized as of mid-2026.

---

## Relationship with SOL

SOL and A2A operate at different levels and are **complementary**:

- SOL describes *what* a process does — its instructions, its logic, its context
- A2A describes *how an agent is reached* by other agents — its endpoint, its capabilities, its task lifecycle

A SOL process could be exposed as an A2A agent: the AgentCard would describe its capabilities in natural language (consistent with SOL's philosophy), its endpoint would receive tasks via `message/send`, and the process would be executed as always by the agent-runtime.

The fact that A2A uses natural language for skills — rather than typed schemas — is perfectly aligned with SOL's philosophy: describe the intent, the agent interprets.

---

## References

- Official spec: https://a2a-protocol.org/latest/specification/
- GitHub: https://github.com/a2aproject/A2A
- Samples: https://github.com/a2aproject/a2a-samples
- Linux Foundation launch: https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project
- LF 150 organizations milestone: https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations
- Spring AI A2A: https://spring.io/blog/2026/01/29/spring-ai-agentic-patterns-a2a-integration/
- AWS Bedrock AgentCore A2A: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html
- Palo Alto Unit 42 — Agent Session Smuggling: https://unit42.paloaltonetworks.com/agent-session-smuggling-in-agent2agent-systems/
- arXiv:2505.12490 — Improving A2A security: https://arxiv.org/abs/2505.12490
- Cloud Security Alliance — MAESTRO threat modeling: https://cloudsecurityalliance.org/blog/2025/04/30/threat-modeling-google-s-a2a-protocol-with-the-maestro-framework
