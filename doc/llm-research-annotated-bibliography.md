# SOL and LLM Research: An Annotated Bibliography

*This document connects SOL's design choices to published research on large language models. Each entry explains what the paper demonstrates and which specific aspect of SOL it informs. Where the research does not fully cover a claim, we say so explicitly.*

*All links are to publicly accessible sources. Paper abstracts and findings described here are accurate as of the date of this writing (May 2026).*

---

## Introduction

SOL's design is grounded in a set of claims about how large language models work: what they do well, where they fail, and what kinds of formats are legible to them. Some of these claims are well-supported by published research. Others are supported by indirect evidence. And some remain, as far as we know, not yet formally studied — gaps that future research may fill.

This bibliography is organized thematically, by the principle it supports. It is not exhaustive — the LLM research literature is vast and grows weekly — but it covers the most directly relevant work we are aware of.

---

## Theme 1: LLMs as Reasoning and Acting Agents

The foundation of SOL's design is the claim that a capable LLM can be the runtime of a process, not merely a tool invoked within one. This is supported most directly by the ReAct paradigm.

---

### ReAct: Synergizing Reasoning and Acting in Language Models
**Yao et al. (Google Research / Princeton University), ICLR 2023**
**arxiv.org/abs/2210.03629** | **research.google/blog/react-synergizing-reasoning-and-acting-in-language-models**

**What the paper demonstrates:**
ReAct shows that LLMs can interleave verbal reasoning traces with concrete actions — not just produce outputs, but reason about what to do next, act, observe results, and adjust. The paper evaluates this on four benchmarks: multi-hop question answering (HotPotQA), fact verification (Fever), text-based navigation (ALFWorld), and web interaction (WebShop). ReAct outperforms both pure reasoning (chain-of-thought) and pure action (without reasoning traces) across all four.

The key finding: the separation between reasoning (internal traces) and acting (external interactions) is not just conceptually clean — it produces measurably better results. Agents that reason about what to do before doing it outperform agents that act directly from instructions.

**What this means for SOL:**
SOL's TODO/RUN distinction is a formalization of the ReAct insight. TODO delegates both reasoning and action to the agent — the agent reasons about how to fulfill the instruction, then acts. RUN suppresses the reasoning layer for the action component: the command is fixed, and the agent executes it verbatim. By making this distinction explicit in the process format, SOL lets process authors specify *which mode* is appropriate for each step.

More broadly, ReAct validates the premise that LLMs can serve as the runtime of a process, not merely as tools within one. If LLMs can reason-then-act across multiple steps of a complex task — maintaining internal state, adapting to observations, recovering from errors — then it is coherent to write processes designed for them to execute autonomously.

---

### From Static Templates to Dynamic Runtime Graphs: A Survey of Workflow Optimization for LLM Agents
**arxiv.org/html/2603.22386v1 (2026)**

**What the paper demonstrates:**
This survey documents the emerging paradigm of LLM-based systems as executable workflows — not static pipelines, but dynamic graphs that interleave LLM calls, tool use, memory updates, and verification. The paper frames LLM agent systems as "agentic computation graphs" and surveys methods for optimizing their structure.

**What this means for SOL:**
The survey confirms that the field is converging on the architecture SOL assumes: processes as structured sequences of LLM and tool invocations, with the LLM as the orchestrating intelligence rather than a passive component. SOL is positioned within this trend, providing a format that expresses these graphs as human-readable, agent-executable documents rather than Python code.

---

## Theme 2: Natural Language vs. Structured Formats for Tool Calling

One of SOL's most important claims is that natural language at the instruction level outperforms rigid structured vocabularies. This is directly supported by recent empirical work.

---

### Natural Language Tools: A Natural Language Approach to Tool Calling in Large Language Agents
**Johnson, Pain, and West, arxiv.org/abs/2510.14453 (October 2025)**

**What the paper demonstrates:**
This paper directly tests the hypothesis that natural language tool descriptions outperform JSON-schema-based tool definitions for LLM agents. Across 10 models and 6,400 trials in customer service and mental health domains, replacing programmatic JSON tool calling with natural language equivalents improves tool-calling accuracy by **18.4 percentage points** and reduces output variance by **70%**.

The mechanism identified: JSON tool definitions force the model to simultaneously handle task understanding, tool selection, and format compliance — a multi-objective problem that degrades performance on each objective. Natural language descriptions separate these concerns, letting the model focus on understanding and selection.

Notably, the gains are largest for open-weight models, which "surpass flagship closed-weight alternatives" when given natural language tool descriptions rather than JSON schemas.

**What this means for SOL:**
This paper is the most direct empirical support for SOL's TODO design. TODO instructions are natural language — the agent interprets them, selects appropriate tools, and executes without being constrained by a rigid format. The paper's findings suggest that this is not just a usability preference but a measurable performance advantage.

The paper also supports the TODO/RUN distinction from a different angle: RUN is the case where format compliance *is* the objective (execute exactly this command), and JSON-style rigidity is appropriate. TODO is the case where format compliance would interfere with the real objective (accomplish this task), and natural language is superior.

---

### StructuredRAG: JSON Response Formatting with Large Language Models
**arxiv.org/abs/2408.11061 (2024)**

**What the paper demonstrates:**
StructuredRAG benchmarks LLM performance on tasks requiring JSON-formatted output. The headline finding: requiring JSON output reduces response accuracy by **27.3 percentage points** on GSM8K compared to natural language output. Some models experience accuracy reductions exceeding 20% due to task interference — the cognitive load of maintaining format compliance degrades the quality of the actual task performance.

**What this means for SOL:**
This finding is relevant to a subtle but important aspect of SOL's design: the process definition is JSON (read by the agent) but the instructions within it are natural language (not generated by the agent under format constraints). SOL avoids the failure mode StructuredRAG documents. The agent does not generate JSON when executing a TODO — it reads JSON and responds in natural language or action. The JSON is the container, not the output format.

Process authors sometimes ask why SOL doesn't use JSON for instruction content — why not `{ "action": "read", "target": "projects/" }` instead of `{ "TODO": "Read all files in projects/" }`? StructuredRAG's findings provide one answer: forcing agents to produce (or interpret) highly structured vocabularies for their actions degrades their performance on the actual tasks. Natural language instructions keep the agent in its highest-competence domain.

---

### Decoupling Task-Solving and Output Formatting in LLM Generation
**arxiv.org/html/2510.03595v1 (2025)**

**What the paper demonstrates:**
This paper formalizes the task interference problem: when LLMs must simultaneously solve a task and format their output according to rigid constraints, both suffer. The paper proposes and evaluates methods for separating these concerns — solving the task first, then formatting the output as a separate step — and shows measurable improvements.

**What this means for SOL:**
SOL's architecture embodies this separation at the process level. The control flow structure (JSON) is separated from the task content (natural language TODO). The agent reads the structure, understands the flow, and then focuses entirely on task execution without format constraints on its intermediate reasoning. This is the decoupling the paper advocates, implemented at the process format level rather than the model inference level.

---

## Theme 3: Global Planning Before Execution

SOL is designed to be read globally before any instruction is executed. This allows the agent to plan, identify parallelizable steps, and resolve forward references. Several papers support the value of this approach.

---

### Plan-over-Graph: Towards Parallelable LLM Agent Schedule
**arxiv.org/abs/2502.14563 (2025)**

**What the paper demonstrates:**
This paper introduces a paradigm where the agent first decomposes a task into a graph of subtasks, then plans execution over that graph — identifying which subtasks are independent (parallelizable) and which have dependencies (must be sequenced). The paper shows that this global-planning-before-execution approach produces more efficient and correct task completion than greedy sequential execution.

The key insight: by understanding the task as a whole before beginning, the agent can make better decisions about ordering and parallelization than it could if it processed instructions one at a time.

**What this means for SOL:**
SOL does not prescribe parallelization — it trusts the agent to infer it from the global structure of the process. This is only possible if the agent reads the process globally before executing, which SOL is designed to support. The agent can look at a REPEAT foreach and determine whether the iterations are independent; it can look at a sequence of TODOs and determine which can run concurrently. Plan-over-Graph provides empirical support for this approach: global planning is not just theoretically cleaner, it produces better outcomes.

---

### Enhancing LLM-Based Agents via Global Planning and Hierarchical Execution (GoalAct)
**arxiv.org/abs/2504.16563 (2025)**

**What the paper demonstrates:**
GoalAct introduces a continuously-updated global planning mechanism combined with hierarchical execution. The agent maintains a high-level plan throughout execution, updating it as new information arrives. This allows the agent to keep long-term goals in view while executing specific steps, and to adjust the plan when unexpected situations arise.

The paper shows that agents with global planning outperform agents that execute greedily on multi-step tasks requiring adaptation.

**What this means for SOL:**
SOL's description field at the root level — required, not optional — is designed exactly for this. The description tells the agent not just the name of the process but *why it exists and when to run it*. This gives the agent a goal frame that persists throughout execution. Combined with the agent's global reading of the ROUTINE before executing, this enables the kind of goal-directed execution GoalAct describes.

The SUB/AGENT/DELEGATE hierarchy in SOL also reflects GoalAct's hierarchical execution model: the process defines high-level structure, and sub-agents handle execution of bounded subtasks within that structure.

---

## Theme 4: Separating Intelligence from Execution

A recurring theme in SOL's design is the separation between what a process defines (intent) and how the agent executes it (strategy). Recent work has begun to formalize this separation.

---

### Separating Intelligence from Execution: A Workflow Engine for the Model Context Protocol
**Parmar, arxiv.org/abs/2605.00827 (March 2026)**

**What the paper demonstrates:**
This paper addresses a specific inefficiency in LLM agent systems: the agent must re-reason about every tool invocation in every session, even for tasks it has solved before. The proposed solution is a workflow engine that decouples intelligence (deciding what to do, done once) from execution (carrying it out, done repeatedly). The agent produces a declarative workflow blueprint — a JSON document specifying a sequence of tool calls with parameterized templates, loops, and parallel branches — which subsequent executions follow without re-invoking the agent for reasoning.

**What this means for SOL:**
The paper describes, from a different angle, exactly the architecture SOL embodies. SOL processes are declarative workflow blueprints. The agent reads them, reasons about them, and executes them. The process definition captures the "decided what to do" stage; execution is the "carry it out" stage. SOL extends this insight to the process *format* level: not just what happens at runtime, but how processes are written and stored.

The paper's framing also validates SOL's JSON-based approach: the declarative blueprints it proposes are JSON documents, confirming that JSON is the right structural format for this kind of intelligence-execution separation.

---

## Theme 5: Instruction Understanding and Intent Reasoning

SOL's TODO instructions are natural language statements of intent. For this to work, the agent must be capable of understanding the intent behind the instruction, not just its literal content. This is an active area of research.

---

### A Survey of LLM Alignment: Instruction Understanding, Intention Reasoning, and Reliable Generation
**Chang et al., arxiv.org/abs/2502.09101 (February 2025, updated January 2026)**

**What the paper demonstrates:**
This comprehensive survey covers three challenges in LLM deployment: instruction understanding (interpreting what an instruction asks), intention reasoning (understanding what the user actually means, including implicit goals), and reliable generation (producing outputs that honor both). The survey identifies remaining weaknesses — difficulty with long-context instructions, inconsistent handling of ambiguous commands — and maps the directions research is taking to address them.

The survey frames the goal of alignment as closing the gap between what users write and what they mean — a continuous process, not a solved problem.

**What this means for SOL:**
The survey is important for two reasons. First, it confirms that instruction following in natural language is what LLM alignment research is fundamentally about — which validates SOL's choice to put natural language at the instruction level. The massive investment in alignment research is, in part, investment in making LLMs better at exactly the task SOL gives them.

Second, the survey is honest about current limitations. LLMs can still misinterpret ambiguous instructions. SOL's design acknowledges this: it recommends using precise, unambiguous language in TODO instructions, and notes that for tasks where exact reproducibility is required, RUN is more appropriate than TODO. The survey's limitations map directly to the cases where SOL recommends caution.

---

### Aligning Language Models to Explicitly Handle Ambiguity
**arxiv.org/html/2404.11972v1 (2024)**

**What the paper demonstrates:**
This paper studies how LLMs should handle ambiguous instructions — situations where the instruction can be interpreted multiple ways. It proposes training approaches that teach models to identify ambiguity, ask clarifying questions, and resolve uncertainty explicitly rather than silently choosing one interpretation.

**What this means for SOL:**
SOL's WAITUSERINPUT instruction is a structural mechanism for exactly this. When a process reaches a decision point that the process author cannot resolve at writing time — because it depends on context that will only be available at execution time — WAITUSERINPUT creates an explicit pause for human input. This is not a workaround for the agent's limitations; it is a recognition that some decisions legitimately belong to the human.

The paper also supports SOL's honest treatment of WHEN's limitations. When WHEN conditions are ambiguous (can overlap), SOL recommends using sequential IF instead — effectively recommending that process authors remove the ambiguity at the format level rather than leaving it to the agent to resolve.

---

## Theme 6: JSON in LLM Training Data

SOL's choice of JSON as the structural format rests partly on the claim that LLMs have seen enough JSON during training to work with it fluently, without special instruction. This claim is supported by indirect but substantial evidence.

---

### StarCoder2 and The Stack v2
**BigCode Project, arxiv.org/abs/2402.19173 (2024)**
**huggingface.co/datasets/bigcode/the-stack-v2**

**What the paper demonstrates:**
The Stack v2 is one of the largest publicly documented pretraining datasets for code-capable LLMs. It contains 3.28 billion unique files from 104.2 million GitHub repositories, covering 600+ programming languages and markup formats. JSON is explicitly included as one of the recognized formats.

While the paper does not report the exact proportion of JSON files (a common limitation of dataset papers — they describe composition at the language/category level, not the format level), the structural presence of JSON in the dataset is documented.

**What this means for SOL:**
The Stack v2 is used to train models like StarCoder2 and serves as a reference dataset for many other code-capable LLMs. Its inclusion of JSON files — package.json, tsconfig.json, schema files, API response fixtures, configuration files — means that any LLM trained on The Stack has extensive exposure to JSON as a format. This is the basis for the claim that LLMs work with JSON fluently, without needing JSON explained to them.

We should be precise about the strength of this evidence: it establishes that JSON is in LLM training data, not the exact quantity. The exact proportions of JSON vs. other formats in major LLMs' training corpora are not publicly reported by OpenAI, Anthropic, or Google. The Stack v2 is the most detailed public documentation of a major code dataset, and it confirms JSON's presence; the ubiquity of JSON on the web and in software repositories makes the inference robust even without exact percentages.

---

### GPT-4 Technical Report
**OpenAI, arxiv.org/abs/2303.08774 (2023)**
**cdn.openai.com/papers/gpt-4.pdf**

**What the paper demonstrates:**
The GPT-4 technical report confirms that the model is pretrained on "publicly available data" including code and web text. It does not detail the format-level composition of the training set, which is consistent with OpenAI's general policy of not disclosing training data specifics.

**What this means for SOL:**
The report's opacity on training data composition is itself informative: the single most important publicly available reference on a frontier LLM does not tell us the proportion of JSON in training data. This is an honest gap in the public record. What we can infer — from the model's demonstrated ability to read, generate, and reason about JSON without special instruction — is that the training exposure is substantial. But this inference, while strong, remains an inference.

---

## Theme 7: The AGENT/SPAWN Architecture and Agent-to-Agent Protocols

SOL v0.5 introduced first-class AGENT definitions with explicit context boundaries. This design connects to emerging standards for agent-to-agent communication.

---

### Agent-to-Agent Protocol (A2A)
**Linux Foundation Agentic AI Foundation, v1.0.0 (March 2026)**
*(Internal research document: `/home/user/sol/doc/research/a2a-protocol.md`)*

**What the protocol demonstrates:**
A2A is an emerging standard (backed by 150+ organizations) for communication between AI agents using HTTP + JSON-RPC 2.0. It operates at the agent-to-agent level — complementing MCP (which covers agent-to-tool communication). A2A defines how agents declare their capabilities, accept tasks, and return results across process boundaries.

**What this means for SOL:**
SOL's AGENT/SPAWN architecture mirrors the A2A pattern at the process-definition level. An AGENT definition declares `accepts` and `returns` — a natural-language capability contract — and SPAWN invokes it with a `with` clause and a `returns` expectation. This is the same pattern A2A formalizes at the protocol level: declare capabilities, invoke with context, receive results. SOL provides a format for expressing agent orchestration that is structurally compatible with how the agent ecosystem is evolving.

---

## Theme 8: Official Prompt Engineering Guidance from Anthropic, OpenAI, and Google

Beyond academic research, the three major AI providers have published official prompt engineering documentation that — often without referencing SOL or any comparable format — independently validates the same design choices. This convergence is significant: it means SOL's principles are not idiosyncratic design preferences but reflect what the builders of these models have learned from extensive empirical practice.

The sources below are official documentation pages and technical guides, not research papers. They describe recommended practice rather than controlled experiments. The strength of support is therefore practical rather than empirical.

---

### Task Decomposition: One Clear Objective per Step

**Anthropic — Prompt Chaining**
**docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-prompts**

> *"Each subtask should have a single, clear objective."*
> *"Simpler subtasks mean clearer instructions and outputs."*

The page describes multi-step pipeline patterns explicitly: Content creation (Research → Outline → Draft → Edit → Format), Data processing (Extract → Transform → Analyze → Visualize), Decision-making (Gather → List options → Analyze → Recommend). Prompt chaining is recommended specifically for tasks that "involve multiple transformations, citations, or instructions" because chaining "prevents Claude from dropping or mishandling steps."

**OpenAI — Prompt Engineering Guide**
**platform.openai.com/docs/guides/prompt-engineering**

Strategy 3 of six: *"Split complex tasks into simpler subtasks."*
> *"Complex tasks can often be re-defined as a workflow of simpler tasks in which the outputs of earlier tasks are used to construct the inputs to later tasks."*

**Google — Break Down Complex Tasks**
**docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/break-down-prompts**

> *"For complex tasks that require multiple instructions or steps, you can improve the model's responses by breaking your prompts into subtasks. Smaller prompts can help you improve controllability, debugging, and accuracy."*
> *"Instead of having many instructions in one prompt, create one prompt per instruction."*

**What this means for SOL:** All three providers independently arrived at the same principle that defines SOL's ROUTINE: a process is an ordered sequence of single-objective instructions, not a monolithic prompt. The language is nearly identical across providers.

---

### Explicit Instructions: Say Exactly What You Mean

**Anthropic — Prompt Engineering Overview**
**docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview**

> *"Claude responds well to clear, direct, and detailed instructions, and when instructions can be interpreted in different ways, you should explain to Claude what exactly you mean."*

**Anthropic — Building Effective Agents**
**anthropic.com/research/building-effective-agents**

> *"Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries."*
> *"Vague instructions like 'research the semiconductor shortage' led to subagents duplicating work or exploring tangential paths without effective division of labor."*

**OpenAI — GPT-4.1 Prompting Guide**
**cookbook.openai.com/examples/gpt4-1_prompting_guide**

> *"GPT-4.1 is trained to follow instructions more closely and more literally than its predecessors, which tended to more liberally infer intent from user and system prompts."*
> *"Since the model follows instructions more literally, developers may need to include explicit specification around what to do or not to do."*
> *"A single sentence firmly and unequivocally clarifying your desired behavior is almost always sufficient."*

**What this means for SOL:** SOL's TODO instructions are explicit statements of intent, not hints to be interpreted. The providers' guidance — and particularly the observation that newer models follow instructions *more literally* — reinforces the value of writing TODOs precisely. The more capable the model, the more exactly it executes what is written.

---

### Separating What from How: Goal, Procedure, and Output Format as Distinct Concerns

**OpenAI — GPT-4.1 Prompting Guide** (verbatim recommended structure)

> ```
> # Role and Objective
> # Instructions
> ## Sub-categories for more detailed instructions
> # Reasoning Steps
> # Output Format
> # Examples
> # Context
> ```

This structure explicitly separates the *goal* (Role and Objective), the *procedure* (Instructions / Reasoning Steps), and the *output specification* (Output Format). OpenAI reports this is the template their own teams use.

**Anthropic — Chain Prompts**

Recommends using XML tags to pass outputs between prompts: *"Use XML tags to pass outputs between prompts for clear handoffs."* Each step in a chain has its own goal, its own instructions, and produces a defined output that becomes input to the next step.

**Anthropic — Building Effective Agents**

Distinguishes between what the orchestrator is trying to achieve and the mechanics each subagent uses to achieve it — the orchestrator-workers model separates goal definition from execution.

**What this means for SOL:** SOL's architecture mirrors OpenAI's recommended structure precisely. The `description` field at the root level is the Objective. Each TODO is an Instruction. Model tiers map to implicit Reasoning Steps guidance. This is not coincidence — it reflects a convergence on what works.

---

### Structured Formats for Agent Instructions

**Anthropic — Use XML Tags**
**docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags**

> *"Claude was trained specifically to recognize XML tags as a prompt organizing mechanism."*
> *"Be consistent: use the same tag names throughout your prompts, and refer to those tag names when talking about the content."*
> *"Combine XML tags with other techniques like multishot prompting (`<examples>`) or chain of thought (`<thinking>`, `<answer>`). This creates super-structured, high-performance prompts."*

**OpenAI — GPT-4.1 Prompting Guide**

> *"XML is convenient to precisely wrap a section including start and end, add metadata to the tags for additional context, and enable nesting."*

A note on JSON: the GPT-4.1 guide reports that *"JSON performed particularly poorly"* in long-context document retrieval compared to XML. This deserves clarification in the context of SOL: the finding refers to using JSON to format *retrievable content chunks* in a long context (a RAG-style use case), not to using JSON as a *process definition format read by the agent*. SOL uses JSON as the structural container for the process — a document the agent reads in full before executing — not as an encoding for retrievable data fragments. The contexts are distinct.

**What this means for SOL:** The consistent recommendation for explicit structural formatting — XML tags in prompts, structured system prompts — validates SOL's use of JSON fields as named, semantically distinct containers for each aspect of a process (goal, instructions, model tier, role, error handling). The principle is the same: structured, named containers outperform unstructured prose for reliable agent behavior.

---

### Human-in-the-Loop: Checkpoints Before Irreversible Actions

**Anthropic — Building Effective Agents**
**anthropic.com/research/building-effective-agents**

> *"Build checkpoints where agents pause for human review, particularly important before they carry out irreversible actions, like approving financial transactions or deleting data."*
> *"Agents can pause for human feedback at checkpoints or when encountering blockers."*
> *"Err toward doing less and confirming when uncertain about scope."*

This is Anthropic's "minimal footprint" principle applied to agent design — the agent does less and confirms more when uncertainty is present.

**OpenAI — GPT-4.1 Prompting Guide**

On handling missing information: *"If you are not sure about file content or codebase structure pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer."* And: *"if they do not have enough information to call the tool, ask the user for the information you need."*

**What this means for SOL:** Anthropic's checkpoint guidance directly validates SOL's WAITUSERINPUT instruction — and more specifically its process decomposition alternative. Anthropic's description of "pausing before irreversible actions" maps exactly to the pattern: Process A produces output and halts; the human reviews before Process B executes the irreversible step. The checkpoint is the boundary between the two processes.

---

### Roles and Personas per Agent

**Anthropic — Role Prompting**
**docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview**

> *"Role prompting via a system message is one of the most effective ways to steer Claude's behavior, significantly boosting performance on domain-specific tasks."*

**OpenAI — GPT-4.1 Prompting Guide**

The recommended template opens with `# Role and Objective` as the mandatory first section of every system prompt.
> *"A well-structured developer message typically includes: Identity: Define the purpose, communication style, and high-level goals of the assistant."*

**Google — Gemini Prompting Strategies**
**ai.google.dev/gemini-api/docs/prompting-strategies**

> *"If you are going to ask the model to act in a specific role, make sure that role is defined in the system instructions."*

**What this means for SOL:** SOL's `role` field — available at root, SUB, AGENT, and DELEGATE scope — encodes exactly what all three providers recommend as a first-class field. The ability to specify different roles for different scopes (e.g., the orchestrator acts as a project manager while a sub-agent acts as a security engineer) reflects the orchestrator-workers pattern described in Anthropic's agent research.

---

### Model Capability Tiers per Task

**Anthropic — Multi-Agent Research System**
**anthropic.com/engineering/multi-agent-research-system**

> *"Many teams use Claude Sonnet or Opus as the orchestrator and route execution tasks to Haiku."*
> *"When given Claude Sonnet 4.5 subagents, Claude Opus 4.5 as orchestrator achieved 85.4%, suggesting subagent choice can materially affect end-to-end pipeline performance."*

Anthropic explicitly describes the orchestrator-uses-heavy-model / worker-uses-light-model pattern as standard production practice, with measured performance differences.

**OpenAI — Reasoning Best Practices**
**platform.openai.com/docs/guides/reasoning-best-practices**

OpenAI distinguishes reasoning models (o1, o3 — for complex multi-step deliberation) from standard models (GPT-4.1 — for instruction-following, structured outputs, agentic workflows). The GPT-4.1 guide states: *"GPT-4.1 is a great place to build agentic workflows."* Different model families are recommended for different task types.

**Google — Model Selection Documentation**
**ai.google.dev/gemini-api**

Google explicitly differentiates Gemini Pro (complex reasoning, multi-step tasks) from Gemini Flash (fast, high-throughput, sub-agent execution), with documentation describing when each is appropriate.

**What this means for SOL:** SOL's `fast`/`balanced`/`smart` tiers are the declarative encoding of exactly the routing practice all three providers describe. Anthropic's production pattern (heavy orchestrator, light workers) corresponds directly to SOL processes where the root or orchestrating AGENT uses `"model": "smart"` while worker SUBs or repeated tasks use `"model": "fast"`. The tiers abstract away the specific model IDs while preserving the intent.

---

### Parallelization of Independent Subtasks

**Anthropic — Building Effective Agents**

> *"Parallelization is useful when speed is critical, allowing independent subtasks to run at the same time."*
> *"Sectioning breaks a task into independent subtasks run in parallel."*
> *"The lead agent spins up 3–5 subagents in parallel rather than serially; the subagents use 3+ tools in parallel. These changes cut research time by up to 90% for complex queries."*

**OpenAI — GPT-4.1 Prompting Guide**

Acknowledges parallel tool calls as a first-class feature of the API, with guidance on when to enable or disable it based on task structure.

**Google — Vertex AI Break Down Complex Tasks**

> *"Aggregate responses: split a task into subtasks and run the subtasks in parallel."*
> *"In cases where you have complex tasks but you don't need to perform the tasks in a specific order, you can run parallel prompts and aggregate the model's responses."*

**What this means for SOL:** SOL deliberately does not prescribe parallelization at the process level — the agent infers it from the global structure of the process. This is the right design given how providers describe it: parallelization is an execution strategy, not a process definition concern. The agent, having read the full process, knows which steps are independent and can parallelize them. All three providers agree that this judgment belongs to the executing layer, not the specification layer.

---

## Gaps: What the Research Does Not Yet Cover

Intellectual honesty requires noting where SOL's design makes claims that are not yet fully supported by published research.

**Semantic model tiers.** SOL's `fast`/`balanced`/`smart` taxonomy is, as far as we know, not yet studied in the literature. There is research on model routing (selecting among available models based on task complexity), but no published work on declarative semantic tiers as a process format feature. SOL's approach here is pragmatic rather than research-backed: the tiers work in practice because they express intent that agents understand, but we do not have formal evidence of how consistently agents interpret them.

**JSON as container vs. JSON as output.** The StructuredRAG and NLT papers study the effect of requiring JSON *output* from LLMs. SOL uses JSON as the *input* format (the process definition). These are different tasks, and the performance implications may differ. We are not aware of research that specifically studies LLM performance when reading JSON-structured process definitions — a gap that empirical work on SOL itself could begin to fill.

**Global document reading as an execution model.** SOL assumes that agents read the entire document before executing. This is empirically true of current frontier models given appropriate prompting, but we are not aware of research that formally characterizes this property or measures how consistently it holds across model families and sizes.

**Non-determinism and its acceptable scope.** SOL acknowledges that natural language instructions introduce non-determinism. The practical question — how much non-determinism is acceptable for which classes of tasks — is not addressed by existing research in a way that directly informs process design. This remains a judgment call for process authors.

---

## Summary Table

| SOL Design Choice | Academic Research | Official Provider Docs | Overall Strength |
|---|---|---|---|
| Agent as runtime | ReAct (arxiv 2210.03629) | Anthropic BEA: orchestrator-workers pattern | Strong |
| Task decomposition (ROUTINE as steps) | — | Anthropic chain-prompts; OpenAI PE guide; Google Vertex AI | Strong — all three providers, near-identical language |
| Natural language at leaves (TODO) | NLT paper (arxiv 2510.14453) | Anthropic: "single clear objective per subtask" | Strong |
| Explicit instructions over inferred intent | Alignment survey (2502.09101) | OpenAI GPT-4.1: "follows instructions more literally"; Anthropic: "explain what exactly you mean" | Strong |
| JSON as structural format | The Stack v2 | OpenAI: structured outputs; all three: named structured containers | Moderate |
| Separating structure from content | Decoupling (2510.03595); StructuredRAG (2408.11061) | OpenAI GPT-4.1 template: Role / Instructions / Output as separate sections | Strong |
| Global reading before execution | Plan-over-Graph (2502.14563); GoalAct (2504.16563) | — | Moderate |
| Intelligence/execution separation | MCP Workflow Engine (2605.00827) | Anthropic BEA: workflow vs. agent distinction | Moderate |
| role field (personas) | — | All three: role definition is the first section of every system prompt | Strong — unanimous |
| model tiers per task | — | Anthropic: Opus orchestrator + Haiku workers (measured); OpenAI: reasoning vs. standard; Google: Pro vs. Flash | Strong — all three, with Anthropic providing performance data |
| Human-in-the-loop / process decomposition | Ambiguity paper (2404.11972) | Anthropic BEA: "checkpoints before irreversible actions" | Strong for the principle; Moderate for process decomposition specifically |
| Parallelization inferred, not prescribed | Plan-over-Graph (2502.14563) | Anthropic: "90% time reduction"; Google: "aggregate responses" pattern | Strong |
| AGENT/SPAWN context boundaries | A2A protocol (A2A v1.0) | Anthropic BEA: worker subagents with bounded context | Moderate |
| Semantic model tiers (fast/balanced/smart) as vocabulary | — | Partial: all three use tiered model families; none use this specific three-tier vocabulary | Moderate — concept validated, vocabulary is SOL's own |
