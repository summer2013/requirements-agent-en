# requirements-agent — Architecture

## Overview

```
User input
  ↓
main.py (orchestrator)
  ↓
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1        Stage 2        Stage 2.5       Stage 3          │
│  research   →  document   →  prd_review   →  prototype          │
└─────────────────────────────────────────────────────────────────┘
  ↓                   ↓                               ↓
HITL ①            HITL ②                      Stage 4: retrospective
                (with review report)                  ↓
                                               Chroma vector DB
                                                      ↑
                                               read at next project start
```

---

## File responsibilities

```
requirements-agent/
│
├── main.py                  Orchestrator
│   Owns: stage sequencing, HITL checkpoints, file saving
│   Does not contain: business logic or prompts
│
├── agent.py                 Generic agentic loop
│   Owns: request → tool_use handling → loop until end_turn
│   Does not contain: any business logic; reusable by all agents
│
├── prd_review_agent.py      PRD review agent
│   Owns: 5-dimension PRD review, structured issue report
│   Triggers: automatically after document agent saves PRD, before prototype starts
│   Dimensions: structural completeness / logic consistency / flow closure /
│               scenario coverage (MECE) / multi-role coordination
│
├── tool_handlers.py         Tool implementation layer
│   Owns: what each tool actually does (file I/O, external API calls, state updates)
│   Change when: integrating real external systems (Confluence, Jira, Notion, etc.)
│
├── knowledge_base.py        Long-term memory
│   Owns: vector DB read/write, semantic similarity search
│   Backend: Chroma (local) — swap for Pinecone for cloud/multi-user
│
├── review_agent.py          Retrospective agent
│   Owns: compare interview notes vs PRD, extract lessons, write to knowledge base
│   Triggers: automatically at end of every project
│
├── prompts/                 Prompts (the only directory PMs need to touch)
│   ├── research_system.txt   Research agent
│   ├── document_system.txt   Document agent (v2: state machine + reinforced checklist)
│   └── prototype_system.txt  Prototype agent (v2: IA-first + closure enforcement)
│
├── tools/
│   └── definitions.py       Tool schemas (v2: adds check_closure tool)
│
├── examples/                Sample project outputs (for reference)
│
├── kb_data/                 Vector DB data (auto-generated, do not edit manually)
│
└── outputs/                 Per-run outputs (auto-generated)
    └── project_name_timestamp/
        ├── interview_notes.json
        ├── prd.md
        ├── prd_review_report.json
        ├── prototype.html
        └── review.json
```

---

## Data flow

### Between stages

```
Research agent
  └─ save_interview_notes(JSON)
        ↓ stored in state["interview_notes"]
Document agent
  └─ get_interview_notes()
  └─ save_prd(markdown)
        ↓ stored in state["prd_document"]
PRD review agent
  └─ reads state["prd_document"] + state["interview_notes"]
  └─ outputs structured review report
        ↓ stored in state["prd_review"]
Prototype agent
  └─ get_prd() → returns prd_document + prd_review together
  └─ check_closure() → validates page exits + scenario coverage
  └─ save_prototype(html, closure_verified=true)
        ↓ stored in state["prototype_html"]
```

Key design: each agent receives only the *result* of the previous stage, never its conversation history. Context stays bounded regardless of how many stages run.

The PRD review report travels to the prototype agent via the `get_prd` tool response, alongside the PRD text. The `check_closure` tool validates that every critical/major scenario flagged in the review is covered before saving is allowed.

### Knowledge base flow

```
Project completes
  → retrospective agent compares interview notes vs PRD
  → extracts lessons_learned + missed_requirements
  → knowledge_base.save_project() → written to Chroma

Next project starts
  → search_knowledge_base tool fires
  → knowledge_base.search_similar_projects() → semantic search
  → returns top-3 similar project summaries + lessons
  → injected into research agent context
```

---

## Design decisions

### Why prompts live in .txt files
Prompts iterate far more frequently than code. Keeping them in plain text files lets anyone edit them without touching Python.

### Why context doesn't cross stage boundaries
The document agent doesn't need every line of the interview — just the structured notes. The prototype agent doesn't need the PRD discussion — just the final text and review summary. Passing only results (not process) keeps context windows predictable and bounded.

### Why the PRD review runs before prototyping, not after
The cost of fixing a problem grows with each stage: interview fix < PRD fix < prototype fix < post-dev fix. Catching issues at the PRD stage is the cheapest possible intervention point. The review report also becomes a concrete checklist that drives the prototype — turning reactive gap-filling into proactive coverage.

### Why check_closure is a tool call, not just a prompt instruction
Prompt-level instructions are suggestions the model can skip. Tool-call enforcement means `save_prototype` returns an error if `closure_verified` is false — no prototype is saved until the check passes. This removes reliance on model self-discipline.

### Why a vector database instead of stuffing history into context
Once you accumulate 20+ projects, putting everything in context exceeds token limits and floods the model with irrelevant information. Semantic search returns only the top-3 most relevant past projects — precise and token-efficient.

---

## Extension guide

### Integrating external systems

Only `tool_handlers.py` needs to change:

```python
# Save PRD to Confluence
if tool_name == "save_prd":
    confluence.create_page(title=project_name, body=tool_input["prd_markdown"])

# Create Jira epic from interview notes
if tool_name == "save_interview_notes":
    jira.create_epic(summary=project_name, description=tool_input["summary"])
```

### Switching models

Change the `model=` parameters in `main.py`:

```python
# GPT-4o via OpenRouter
model="openai/gpt-4o"

# Free model for testing
model="meta-llama/llama-3.3-70b-instruct:free"
```

### Upgrading the vector database

When projects exceed ~100 or you need multi-user sharing, swap Chroma for Pinecone in `knowledge_base.py`:

```python
import pinecone
pinecone.init(api_key=os.environ["PINECONE_API_KEY"])
```

---

## Agent parameters

| Agent | Model | temp | max_tokens | Rationale |
|-------|-------|------|------------|-----------|
| Research | claude-opus-4-5 | 0.3 | 4096 | Strong reasoning for interviews; slight randomness makes questions feel natural |
| Document | claude-sonnet-4-6 | 0.1 | 8192 | PRD needs consistency; near-zero randomness |
| PRD review | claude-sonnet-4-6 | 0.1 | 4096 | Review conclusions need objectivity; low temp reduces false positives |
| Prototype | claude-sonnet-4-6 | 0.2 | 16384 | Code generation needs stability; large window for full HTML output |
| Retrospective | claude-sonnet-4-6 | 0.2 | 2048 | Analysis task; consistency preferred |
