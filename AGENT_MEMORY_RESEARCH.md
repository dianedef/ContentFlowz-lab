# Agent Memory & Learning Frameworks Research

> Research conducted 2026-02-03 to evaluate frameworks for building agents that learn about projects and create tailored, cohesive content.

## The Problem

Current CrewAI setup runs agents as **stateless, task-based workflows**. Each run starts fresh without knowledge of:
- Past content generated
- Brand voice and guidelines
- What worked or didn't work
- Existing content inventory

**Goal**: Agents that truly understand the project, maintain consistency, and improve over time.

---

## Three Types of Intelligence Needed

| Type | What It Means | Example |
|------|---------------|---------|
| **Project Knowledge** | Static facts about the business | Brand voice, topic clusters, site structure |
| **Memory** | What the agent learned from past runs | "Last newsletter covered X, avoid duplicates" |
| **Context Awareness** | Current state of the project | Existing content, internal links, gaps |

---

## Framework Comparison

### 1. Mem0 (Memory Layer)

**What it is**: Universal memory layer that sits between your app and LLMs. Automatically extracts, stores, and retrieves relevant information from conversations.

**Key Stats** (2025):
- 26% accuracy improvement over baseline
- 91% lower p95 latency
- 90% token savings
- 41,000+ GitHub stars
- Native integration with CrewAI, Flowise, Langflow
- AWS selected as exclusive memory provider for Agent SDK

**How it works**:
```python
from openai import OpenAI
from mem0 import Memory

memory = Memory()

# Search for relevant memories
relevant_memories = memory.search(
    query="brand voice and content strategy",
    user_id="contentflowz-project",
    limit=3
)

# Add new memories from interactions
memory.add(messages, user_id="contentflowz-project")
```

**Memory Types**:
- Short-term: Immediate context within a single interaction
- Long-term: Persists across sessions, tasks, and time
- Graph-based: Captures complex relational structures

**Pros**:
- Drop-in integration with existing CrewAI setup
- Proven performance improvements
- Open source (Apache 2.0)
- Multi-level memory (User, Session, Agent state)

**Cons**:
- Memory is an add-on, not core to architecture
- Requires explicit search/add calls

**Links**:
- [GitHub](https://github.com/mem0ai/mem0)
- [Research Paper](https://arxiv.org/abs/2504.19413)
- [Documentation](https://mem0.ai/)

---

### 2. CrewAI Built-in Memory

**What it is**: Native memory system in CrewAI with short-term, long-term, entity, and contextual memory.

**Activation**:
```python
crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,  # Enables all memory types
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"}
    }
)
```

**Memory Components**:
| Component | Storage | Purpose |
|-----------|---------|---------|
| Short-Term | ChromaDB + RAG | Recent interactions, current context |
| Long-Term | SQLite3 | Insights and learnings across sessions |
| Entity | RAG | People, places, concepts encountered |
| Contextual | Combined | Coherent, relevant responses |

**Storage Locations**:
- macOS: `~/Library/Application Support/CrewAI/{project_name}/`
- Linux: `~/.local/share/CrewAI/{project_name}/`
- Windows: `C:\Users\{username}\AppData\Local\CrewAI\{project_name}\`

**Custom Storage**:
```python
import os
os.environ["CREWAI_STORAGE_DIR"] = "./my_project_storage"
```

**Embedding Providers**: OpenAI (default), Ollama, Google AI, Vertex AI, Azure OpenAI, Cohere, VoyageAI, Bedrock, Hugging Face, Watson

**Pros**:
- No new dependencies
- Simple activation
- Multiple embedding provider options

**Cons**:
- Less sophisticated than dedicated memory solutions
- Memory is per-crew, not global across all agents

**Links**:
- [CrewAI Memory Docs](https://docs.crewai.com/en/concepts/memory)
- [Deep Dive Article](https://sparkco.ai/blog/deep-dive-into-crewai-memory-systems)

---

### 3. Letta (Stateful Agents Platform)

**What it is**: Platform specifically designed for building stateful AI agents with persistent memory as a core architectural principle.

**Core Philosophy**: Agents "remember, learn, and improve over time" - memory isn't an add-on but fundamental to how agents work.

**Key Features**:
- Persistent memory blocks always visible to agents
- Archival memory for long-term storage with search
- Shared memory for multi-agent systems
- Memory variables for dynamic context
- Agent Development Environment (ADE) for visual building

**Agent Patterns Supported**:
- Supervisor-worker
- Parallel execution
- Hierarchical orchestration

**Memory Architecture**:
```python
from letta import create_client

client = create_client()

agent = client.create_agent(
    name="content-strategist",
    memory_blocks=[
        {"label": "project_context", "value": "Brand: Content Flows..."},
        {"label": "content_strategy", "value": "Topic clusters: ..."},
        {"label": "past_content", "value": "Previously published: ..."},
    ],
    tools=["web_search", "code_execution"]
)

# Agent remembers everything across sessions
response = agent.send_message("Write a newsletter about AI agents")
```

**Pros**:
- Memory is core architecture, not bolted on
- Agents genuinely evolve and learn
- Shared memory between agents
- Built-in MCP (Model Context Protocol) support
- Visual development environment

**Cons**:
- Requires migration from CrewAI
- Newer platform, smaller ecosystem

**Links**:
- [Letta Documentation](https://docs.letta.com/quickstart)
- [Letta Introduction](https://docs.letta.com/introduction)

---

### 4. LangGraph + Memory Stores

**What it is**: Low-level orchestration framework for stateful workflows with pluggable memory backends.

**Memory Scopes**:
1. **Short-Term**: State flowing through graph during single invocation (checkpointed)
2. **Long-Term**: Persists across sessions via external stores (MongoDB, Redis, etc.)

**Checkpointing**:
```python
from langgraph.checkpoint.sqlite import SqliteSaver  # Local dev
from langgraph.checkpoint.redis import RedisSaver    # Production
```

**Database Integrations**:
- MongoDB Store: Flexible, scalable long-term memory
- Redis: Thread-level persistence + cross-thread memory
- PostgreSQL, SQLite for checkpoints

**Production Users**: Klarna, Replit, Elastic

**Pros**:
- Maximum flexibility and control
- Production-proven at scale
- Strong typing with TypedDict schemas
- Robust checkpointing for crash recovery

**Cons**:
- More complex setup
- You manage memory architecture yourself
- Steeper learning curve

**Links**:
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph + MongoDB](https://www.mongodb.com/company/blog/product-release-announcements/powering-long-term-memory-for-agents-langgraph)
- [LangGraph + Redis](https://redis.io/blog/langgraph-redis-build-smarter-ai-agents-with-memory-persistence/)

---

## Recommendation: Hybrid Architecture

Given the existing CrewAI investment and the goal of cohesive, tailored content:

```
┌─────────────────────────────────────────────────────────────┐
│                    PROJECT BRAIN (Mem0)                     │
│  - Brand voice & guidelines                                 │
│  - Content inventory (what exists)                          │
│  - Topic clusters & internal linking map                    │
│  - Historical performance data                              │
│  - What content was sent/published (avoid duplicates)       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   SEO Robot   │   │ Newsletter Agent│   │ Article Generator│
│   (CrewAI)    │   │   (PydanticAI)  │   │    (CrewAI)     │
│               │   │                 │   │                 │
│ Queries brain │   │ Queries brain   │   │ Queries brain   │
│ before writing│   │ for past sends  │   │ for content gaps│
└───────────────┘   └─────────────────┘   └─────────────────┘
```

### Implementation Steps

#### Step 1: Set Up Project Brain with Mem0

```python
from mem0 import Memory

memory = Memory()

# Initialize with project knowledge
project_knowledge = [
    {
        "role": "system",
        "content": """
        Project: contentflowz
        Brand Voice: Technical but accessible, informal French (tutoiement)
        Main Topics: AI agents, automation, SEO, newsletters
        Target Audience: French-speaking developers and marketers
        """
    }
]
memory.add(project_knowledge, user_id="contentflowz-project")
```

#### Step 2: Add Context Loader to Each Agent

```python
def load_project_context(topic: str) -> str:
    """Load relevant context before any content generation."""
    relevant = memory.search(
        query=f"brand voice, existing content, and strategy for {topic}",
        user_id="contentflowz-project",
        limit=5
    )
    return "\n".join(f"- {entry['memory']}" for entry in relevant["results"])
```

#### Step 3: Add Memory Writer After Each Run

```python
def save_to_memory(content_type: str, title: str, topics: list, summary: str):
    """Store what was generated for future reference."""
    memory.add([
        {
            "role": "assistant",
            "content": f"""
            Generated {content_type}: {title}
            Topics covered: {', '.join(topics)}
            Summary: {summary}
            Date: {datetime.now().isoformat()}
            """
        }
    ], user_id="contentflowz-project")
```

#### Step 4: CrewAI + Mem0 Integration

```python
from crewai import Crew
from crewai.memory.external.external_memory import ExternalMemory

external_memory = ExternalMemory(
    embedder_config={
        "provider": "mem0",
        "config": {
            "user_id": "contentflowz-project",
        }
    }
)

crew = Crew(
    agents=[research_analyst, content_strategist, copywriter, editor],
    tasks=[...],
    memory=True,  # Built-in memory
    external_memory=external_memory  # Mem0 for cross-session learning
)
```

---

## What Each Robot Gains

| Robot | Memory Benefits |
|-------|-----------------|
| **SEO Robot** | Knows existing content → avoids duplication, maintains topical flow, consistent internal linking |
| **Newsletter Agent** | Remembers past newsletters → no duplicate topics, evolving content strategy, reader preference learning |
| **Article Generator** | Knows content gaps → targeted generation, consistent voice, builds on existing pillar content |
| **Scheduling Robot** | Historical performance data → optimal timing, learns what works |

---

## Next Steps

1. [ ] Install Mem0: `pip install mem0ai`
2. [ ] Create project brain initialization script
3. [ ] Prototype with Newsletter Agent (simplest to test)
4. [ ] Measure content quality improvement
5. [ ] Roll out to other robots

---

## Alternative: Full Migration to Letta

If the hybrid approach proves insufficient, consider full migration to Letta for agents that require deep personalization. Best candidates:
- Newsletter Agent (benefits most from learning reader preferences)
- Any future conversational/assistant-style agents

---

## References

- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Mem0 Research Paper](https://arxiv.org/abs/2504.19413)
- [CrewAI Memory Docs](https://docs.crewai.com/en/concepts/memory)
- [Letta Documentation](https://docs.letta.com/quickstart)
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph + MongoDB](https://www.mongodb.com/company/blog/product-release-announcements/powering-long-term-memory-for-agents-langgraph)
- [Agentic Frameworks Guide 2025](https://mem0.ai/blog/agentic-frameworks-ai-agents)
