# requirements-agent

> An AI agent pipeline that gives solo developers a product manager's instincts — before writing a single line of code.

---

## The problem

Every side project I've shipped had the same post-launch regrets:

- "My delete button had no confirmation. A user wiped their entire account by accident."
- "Someone navigated away mid-form and lost 20 minutes of work. They emailed me. I had no idea that could happen."
- "There's no way to undo this and I never added a confirmation dialog."

I don't have a PM. No design reviews. Just me making all the product decisions alone. So I built this to catch those gaps *before* they become bugs.

---

## What it does

A 4-stage agent pipeline built on Claude:

```
Project brief
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Stage 1      Stage 2       Stage 2.5      Stage 3      │
│  Interview → PRD gen → PRD review → Prototype           │
└─────────────────────────────────────────────────────────┘
     │              │                           │
  HITL ①         HITL ②                  Stage 4: retro
                (w/ review)               → knowledge base
```

**Stage 1 — Structured interview**
JTBD-style questioning to understand *why*, not just *what*. Automatically references past similar projects from the knowledge base.

**Stage 2 — PRD generation**
Produces a complete spec with user stories, Gherkin acceptance criteria, and — critically — a full state machine for every core business object.

**Stage 2.5 — Automated PRD review** *(the part I'm most proud of)*
Before a single prototype screen is drawn, automatically checks 5 dimensions:

| Dimension | What it checks |
|-----------|---------------|
| Structural completeness | Background, goals, roles, Out of Scope, error handling |
| Logic consistency | Preconditions, post-states, reversibility |
| Flow closure | No dead ends, every action has feedback |
| Scenario coverage (MECE) | Empty states, errors, timeouts, concurrent edits |
| Multi-role coordination | Handoffs, wait states, notifications, timeouts |

Issues come back ranked **critical / major / minor**.

**Stage 3 — HTML prototype**
Single-file HTML wireframe. The agent *cannot* call `save_prototype` without first passing `check_closure` — a tool that verifies no dead-end pages exist and every flagged missing scenario is covered. Enforced at the system level, not just prompt level.

**Stage 4 — Retrospective**
After each project, a retrospective agent compares the interview notes against the final PRD, extracts lessons, and writes them to a local vector database. Future projects automatically benefit from past experience.

---

## Two ways to use it

### Option A — Claude Projects (free, no code required)

The easiest way to start. Upload the prompt files to a Claude Project and run the
entire pipeline through conversation — no Python, no API key, no setup cost.

**→ See [docs/project_guide.md](docs/project_guide.md) for the full setup guide.**

Good for: trying it out, occasional use, non-technical users.

### Option B — Python API (full pipeline)

Run the complete automated pipeline locally. Stages chain automatically,
the knowledge base persists across projects, and human checkpoints appear in your terminal.

```bash
# 1. Install dependencies
pip install anthropic chromadb python-dotenv

# 2. Configure API key
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (or OPENROUTER_API_KEY)

# 3. Run (interactive mode)
python main.py --interactive

# 4. Or pass arguments directly
python main.py --project-name "Order Management System" \
               --brief "Warehouse team needs to manage outbound orders..."
```

Good for: regular use, accumulating a knowledge base across projects, automation.

---

## Output files

Each API run creates `outputs/{project_name}_{timestamp}/`:

| File | Contents |
|------|----------|
| `interview_notes.json` | Structured interview notes |
| `prd.md` | PRD with state machine |
| `prd_review_report.json` | 5-dimension review report (critical/major/minor) |
| `prototype.html` | Interactive low-fi wireframe |
| `review.json` | Retrospective lessons (also written to knowledge base) |

---

## Project structure

```
requirements-agent/
├── main.py                  Orchestrator
├── agent.py                 Generic agentic loop (reusable)
├── prd_review_agent.py      PRD review agent
├── review_agent.py          Retrospective agent
├── tool_handlers.py         Tool implementations
├── knowledge_base.py        Chroma vector DB (local)
├── tools/
│   └── definitions.py       Tool schemas
├── prompts/
│   ├── api/                 Prompts for the Python pipeline
│   └── projects/            Prompts for Claude Projects mode
└── docs/
    ├── project_guide.md     Step-by-step guide for Claude Projects mode
    └── architecture.md      System design and extension guide
```

---

## Using OpenRouter (optional)

Set `OPENROUTER_API_KEY` instead of `ANTHROPIC_API_KEY` to route through OpenRouter.
The orchestrator auto-detects which key is present and adjusts model names accordingly.

---

## License

MIT
