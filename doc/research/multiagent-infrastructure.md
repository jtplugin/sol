# Multi-Agent Infrastructure — How It Works in Practice

> Research notes. Sources: LangGraph, CrewAI, AG2, OpenAI Agents SDK, AWS Strands docs, arXiv. May 2026.

---

## The Fundamental Problem

LLM calls are transactional: you call, you get a response, and it ends there. In a multi-agent system something is needed to hold the thread between transactions — state, routing, context. Every framework solves this problem differently, with different trade-offs.

Token cost is not an implementation detail: it is an architectural constraint that changes upstream design decisions.

---

## Token Cost Management

Strategies in use, from simplest to most sophisticated:

### 1. History Windowing
Keep only the last N messages. Linear savings, zero quality impact in most cases.

- AG2: `MessageHistoryLimiter(max_messages=10)`
- LangGraph: custom state reducer that truncates `messages`
- Typical deployment: N=10–20

### 2. Structured Inter-Agent Output
Agent A returns a JSON schema'd object; agent B receives structured data instead of a prose paragraph. Eliminates the summarization "chatter".

- CrewAI: `output_json` and `output_pydantic` on tasks
- Advantage: reduces output tokens without loss of information

### 3. RAG on History (Semantic Memory)
The entire history is stored in a vector store; each call retrieves only semantically relevant chunks. Cost per call is fixed and does not grow with conversation length.

- CrewAI memory: ChromaDB for short-term, SQLite for long-term, ChromaDB RAG for entity memory
- Physical storage: `~/Library/Application Support/CrewAI/{project_name}/`
- Advantage: scalable; disadvantage: requires embedding infrastructure

### 4. Explicit Summarization Node
An inexpensive model (Haiku, GPT-4o-mini) summarizes older turns before the main model is called. 4–10x savings on long conversations.

- LangGraph: dedicated node in the graph, inserted conditionally when `len(messages) > threshold`

```python
def maybe_summarize(state):
    if len(state["messages"]) > 50:
        summary = llm.invoke(
            "Summarize this conversation: " + format(state["messages"][:-10])
        )
        return {"messages": [SystemMessage(summary)] + state["messages"][-10:]}
    return state
```

No framework provides automatic summarization — it must be wired explicitly.

### 5. LLMLingua Compression
A local BERT model drops low-information tokens before the LLM call. Documented 4x reduction, with ~3–5% quality degradation. Adds latency for the compression pass.

- AG2: `TextMessageCompressor` with `LLMLingua`

```python
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import (
    MessageHistoryLimiter, MessageTokenLimiter, TextMessageCompressor
)

context_handler = TransformMessages(transforms=[
    MessageHistoryLimiter(max_messages=10),
    MessageTokenLimiter(max_tokens=8000),
    TextMessageCompressor(
        text_compressor=LLMLingua(
            model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            use_llmlingua2=True
        ),
        min_tokens=1000
    )
])
context_handler.add_to_agent(agent)
```

### 6. KV Cache (Prompt Caching)
The static prefix of the prompt (system prompt, tool schemas, shared context) is structured so that it is identical and long enough to hit the provider-side cache. ~90% savings on cached tokens.

- Anthropic: requires prefix ≥1024 identical tokens
- Works with any framework via careful prompt templating

### 7. Tool Schema Deduplication
In multi-agent systems where each agent receives the full tool list, moving shared tools into a single manifest avoids resending 2K–5K token schemas per agent per call.

### 8. Compaction API (New, 2026)
Anthropic Compaction API (beta, February 2026): automatic mid-conversation context summarization by Opus 4.6. Transparent to application code, but provider-locked.

OpenAI Responses API: maintains history server-side, avoiding resending already-seen tokens.

---

**In practice**: most teams use strategies 1–4 together. Strategies 5–8 are advanced optimizations applied after windowing and RAG are already in place.

---

## State Persistence Between Calls

### LangGraph — the Most Mature

`Checkpointer` abstraction: serializes graph state after each node. Available implementations:

| Backend | Use |
|---|---|
| `PostgresSaver` / `AsyncPostgresSaver` | Production |
| `SqliteSaver` | Local development |
| Redis | Worker coordination (not checkpoint) |

Postgres schema:

```
checkpoints       — JSONB: {v, ts, id, channel_values, channel_versions, versions_seen}
checkpoint_blobs  — BYTEA: large state values (message lists, etc.)
checkpoint_migrations — schema versioning
```

Key: `(thread_id, checkpoint_ns, checkpoint_id)`.

Resuming an interrupted thread:

```python
config = {"configurable": {"thread_id": "abc123"}}
result = graph.invoke(None, config)  # None = resume from checkpoint
```

### CrewAI

Three memory tiers with separate storage:

| Tier | Storage | Scope |
|---|---|---|
| Short-term | ChromaDB (embeddings) | Current session |
| Long-term | SQLite (`long_term_memory_storage.db`) | Cross-session |
| Entity | ChromaDB RAG | Persistent facts about specific entities |

For distributed deployment, teams integrate Mem0 (third-party service). No native distributed backend.

### AG2 / AutoGen

Minimal native persistence. Conversation history lives in Python objects during the run. Cross-session requires external tooling. `UpdateSystemMessage` allows injecting state into the prompt, but is not a storage layer.

### OpenAI Agents SDK

The `Session` abstraction (Responses API) manages in-process continuity: `session.run()` automatically tracks history. Cross-session: serialize `RunResult.to_input_list()` and restore manually. No bundled database integration.

### AWS Strands

`S3SessionManager`: serializes complete history and agent state to S3, keyed by `session_id`. Lifecycle: restore on init → add message → sync state → write. DynamoDB supported for session indexing. No built-in compression: if context fills up, management is the operator's responsibility.

---

## Conversation Resume

| Framework | Mechanism | Automatic? |
|---|---|---|
| LangGraph | Checkpoint + `invoke(None, config)` | Yes (infra), no (summarization) |
| AG2 | `summarize_conversation_method` at end of run | End of run only |
| OpenAI Agents SDK | `nest_handoff_history`: previous transcript collapsed into `<CONVERSATION HISTORY>` | At handoff time |
| CrewAI | RAG retrieval on relevant chunks | Automatic but partial |
| AWS Strands | None | No |

---

## What Passes Between Agents

This is the point where frameworks diverge most significantly.

### LangGraph
Agents are graph nodes. The "passing" is the state object flowing through edges. The developer controls exactly which channels propagate — full history, filtered messages, or a structured summary.

```
Agent A node → [state: {messages: [...], analysis: {...}}] → Agent B node
```

### CrewAI
Two mechanisms:
1. `context=` on the task: the textual output of task A is injected verbatim into the prompt of task B
2. Shared memory: both agents read/write the same ChromaDB and query for relevance

The `context` mechanism passes the raw output string, not a structured object.

### AG2 GroupChat
All agents in the group see the full accumulated `chat_history` by default. `TransformMessages` is the way to limit this:

4 agents × 5 rounds = 20 LLM calls, each with the full history without limitations.

### OpenAI Agents SDK
Handoff passes the full history. `input_filter` on `Handoff` allows rewriting `HandoffInputData`:

```python
def filter_to_summary(data: HandoffInputData) -> HandoffInputData:
    return HandoffInputData(
        input_history=data.input_history[-5:],  # last 5 turns
        pre_handoff_items=data.pre_handoff_items,
        new_items=data.new_items
    )

handoff = Handoff(agent=specialist, input_filter=filter_to_summary)
```

With `nest_handoff_history=True`, the previous transcript is wrapped in a `<CONVERSATION HISTORY>` block at each subsequent handoff.

### AWS Strands
For multi-agent patterns (Swarms, Graphs, Agents-as-Tools), the shared `S3SessionManager` gives all agents access to the same serialized session. The result of a sub-agent invoked as a tool is returned as a tool response and appended to the calling agent's history — no filtering mechanism.

---

## Production Infrastructure

Typical architecture for a serious deployment:

```
                 ┌───────────────────────────────┐
                 │      Load Balancer / API GW    │
                 └───────────────┬───────────────┘
                                 │
                 ┌───────────────▼───────────────┐
                 │        Agent API Server        │
                 │   (FastAPI / LangGraph Server) │
                 └──┬──────────┬──────────┬──────┘
                    │          │          │
          ┌─────────▼──┐  ┌────▼───┐  ┌──▼──────────┐
          │  Postgres   │  │ Redis  │  │ Worker Pool  │
          │ (state /    │  │(queue/ │  │(bg runs,    │
          │ checkpoint) │  │ cache) │  │ async tasks) │
          └─────────────┘  └────────┘  └─────────────┘
                    │
          ┌─────────▼──────────┐
          │    Vector Store     │
          │ (Chroma/Pinecone/   │
          │  Weaviate — RAG)    │
          └────────────────────┘
                    │
          ┌─────────▼──────────┐
          │   Observability     │
          │ LangSmith/Langfuse/ │
          │ OpenTelemetry       │
          └────────────────────┘
```

**LangGraph Server** explicitly requires: Postgres (checkpoint + run metadata), Redis (worker-server communication, run cancellation), LangSmith (tracing). Self-hosted LangSmith is itself a 5-service Docker stack.

**AWS Strands + Bedrock AgentCore**: S3 (session state), DynamoDB (optional session index), CloudWatch (metrics/logs), X-Ray (distributed tracing).

**AG2 / OpenAI SDK**: no infrastructure prescribed by the framework. Teams typically add: task queue (Celery + Redis or SQS), relational DB for run history, Langfuse or Phoenix for tracing, Prometheus + Grafana for token cost dashboards.

---

## The "Who Speaks Next" Problem

No framework has an economical answer to non-prescriptive routing:

| Approach | Framework | Cost per turn |
|---|---|---|
| Explicit graph — routing in code | LangGraph | Minimal (no LLM call for routing) |
| Explicit handoff — each agent decides | OpenAI Agents SDK | Included in the turn |
| LLM manager — a model chooses who speaks | CrewAI hierarchical, AG2 GroupChat | +1 LLM call per turn |
| Lightweight router — classifies the last message | AWS Multi-Agent Orchestrator | +1 cheap call per turn |

Whoever is truly non-prescriptive (AG2 GroupChat) is expensive. Whoever is economical (LangGraph) is prescriptive. There is no elegant approach that is simultaneously economical and non-prescriptive.

---

## Implications for SOL

**Token cost is infrastructural, not a spec concern.** SOL does not need to solve token cost, but must be designed in a way that doesn't make it worse. Structured inter-agent outputs — which SOL already favors with file artifacts — is the cleanest strategy and requires no spec changes.

**Persistence is the missing brick.** Every serious framework has a checkpointer. A SOL process already has `name` and `version` — they are the natural key for an external checkpoint. But this is a deployment concern, not a spec concern.

**Defining competency boundaries well in the SETTING is worth more than any generic orchestrator.** If roles are truly distinct and their domains don't overlap, routing becomes trivial — every message has an obvious recipient. Routing ambiguity is almost always a symptom of poorly defined or overlapping roles.

---

## References

- [LangGraph Checkpointing Internals](https://blog.lordpatil.com/posts/langgraph-postgres-checkpointer/)
- [LangGraph Data Plane — Infrastructure Requirements](https://langchain-ai.github.io/langgraph/concepts/langgraph_data_plane/)
- [CrewAI Memory Documentation](https://docs.crewai.com/en/concepts/memory)
- [AG2 TransformMessages / Context Compression](https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_transform_messages/)
- [AG2 LLMLingua Text Compression](https://microsoft.github.io/autogen/0.2/docs/topics/handling_long_contexts/compressing_text_w_llmligua/)
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [OpenAI Agents SDK — Session Memory Cookbook](https://cookbook.openai.com/examples/agents_sdk/session_memory)
- [AWS Strands 1.0 — Session Management](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/)
- [Stop Wasting Your Tokens: Efficient Multi-Agent Systems](https://arxiv.org/html/2510.26585v2)
- [Acon: Adaptive Context Compression for LLM Agents](https://arxiv.org/html/2510.00615v1)
- [AI Agent Memory: LangGraph vs CrewAI vs AutoGen](https://dev.to/foxgem/ai-agent-memory-a-comparative-analysis-of-langgraph-crewai-and-autogen-31dp)
