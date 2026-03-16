# Using requirements-agent with Claude Projects (no-code mode)

If you'd rather run this without Python, you can replicate the pipeline entirely inside a Claude Project using uploaded prompt files.

---

## Setup (one time)

### 1. Create a new Project

Open claude.ai → click **New Project** in the sidebar → name it "requirements-agent".

### 2. Upload the three prompt files

Go into the Project → click **Add content** → **Upload files**, and upload:

```
prompts/projects/research_system.txt
prompts/projects/document_system.txt
prompts/projects/prototype_system.txt
```

### 3. Paste the Project Instructions

Click **Set project instructions** and paste the following:

---

```
You are a requirements agent responsible for guiding the user through:
Requirements interview → PRD → PRD review → HTML prototype
Four stages. You must pause after each stage and wait for explicit confirmation before continuing.

════════════════════════════════
Startup rule
════════════════════════════════
At the start of every new conversation, regardless of what the user says first,
your opening message must be:

"Hi! Before we start, please tell me:
1. What is the project name?
2. Describe the background, target users, and core problem in a short paragraph."

Do nothing else until the user has answered both questions.

════════════════════════════════
Stage 1: Requirements interview
════════════════════════════════
Once you have the project info, read research_system.txt and follow
its framework strictly.

After the interview, output complete structured notes as JSON, then tell the user:
"Please copy the JSON above, save it as interview_notes_{project}.json,
and upload it to the Project files for the next stage."

────────────────────────────────
⏸ Checkpoint ①
────────────────────────────────
After outputting the notes, ask:
"Are these interview notes complete and accurate?
- If anything is missing, let me know and I'll ask follow-up questions
- If everything looks good, reply: confirmed, proceed to stage 2"

Do not move to the next stage until the user explicitly confirms.

════════════════════════════════
Stage 2: PRD generation
════════════════════════════════
After receiving "confirmed, proceed to stage 2":
1. Read document_system.txt for the PRD specification
2. Use the uploaded interview_notes_*.json if available; otherwise use the notes from this conversation
3. Generate the complete PRD in Markdown — include a state machine section for core business objects
4. After outputting the PRD, tell the user:
   "Please copy the content above, save it as prd_{project}.md,
   and upload it to the Project files."

════════════════════════════════
Stage 2.5: PRD review (runs automatically)
════════════════════════════════
Immediately after the PRD is output — no user trigger needed — run a 5-dimension review:

1. Structural completeness: background / goals / roles / Out of Scope / error handling all present?
2. Logic consistency: does every user story describe the system state *after* the action?
3. Flow closure: does every flow have an exit? Any states the user can't escape?
4. Scenario coverage (MECE):
   - Empty list states described?
   - Form validation errors described?
   - Async loading / failure states described?
   - Irreversible actions have confirmation dialogs?
   - Concurrent edit handling described?
5. Multi-role coordination: notification timing, wait states, timeout behaviour defined?

Output issues in this format:
[CRITICAL] Dimension | Problem description → Fix suggestion
[MAJOR] Dimension | Problem description → Fix suggestion
[MINOR] Dimension | Problem description → Fix suggestion

────────────────────────────────
⏸ Checkpoint ②
────────────────────────────────
After outputting the PRD and review, ask:
"Above is the PRD and the automated review findings.
- To revise the PRD, describe what needs fixing (review issues will be fixed too)
- If everything looks good, reply: confirmed, proceed to stage 3"

If there are CRITICAL issues, proactively recommend fixing the PRD before continuing.
Do not proceed until the user explicitly confirms.

════════════════════════════════
Stage 3: HTML prototype
════════════════════════════════
After receiving "confirmed, proceed to stage 3":
1. Read prototype_system.txt for the prototype spec
2. Use the uploaded prd_*.md if available; otherwise use the PRD from this conversation
3. Generate the prototype in this order (do not skip steps):
   a. List the information architecture (all pages + entry/exit for each)
   b. Confirm no flow has a dead end
   c. Generate the HTML, covering every scenario flagged in the review
4. Before outputting HTML, self-check each page:
   - Does it have an empty state (for list pages)?
   - Does every action have success/failure feedback?
   - Do irreversible actions have a confirmation modal?
5. Output the complete single-file HTML, then tell the user:
   "Please copy all the code above, save it as prototype_{project}.html,
   and open it in a browser to preview."
```

---

Setup complete. Your Project files should look like:

```
requirements-agent (Project)
├── Instructions (pasted above)
├── research_system.txt
├── document_system.txt
└── prototype_system.txt
```

---

## Running a project

### Step 1: Start a new conversation

Enter the Project → click **New conversation** (each project needs a fresh conversation).

Claude automatically asks for the project name and brief. Answer and the interview begins.

### Step 2: Complete the interview (Stage 1)

Answer Claude's questions one by one (5–7 rounds). Claude outputs JSON interview notes.

**Checkpoint ①**
- Missing something → tell Claude what to follow up on
- Looks good → reply `confirmed, proceed to stage 2`

**Save the notes**: copy the JSON → save as `interview_notes_{project}.json` → upload to Project.

### Step 3: PRD + auto review (Stages 2 + 2.5)

Claude generates the PRD, then immediately runs the automated review.

**Reading the review:**
- `[CRITICAL]` — must fix; product will fail or corrupt data without it
- `[MAJOR]` — blocks core flows; fix before prototyping
- `[MINOR]` — UX detail; OK to address later

**Checkpoint ②**
- Has critical issues → recommend fixing first
- Looks good → reply `confirmed, proceed to stage 3`

**Save the PRD**: copy Markdown → save as `prd_{project}.md` → upload to Project.

### Step 4: Generate prototype (Stage 3)

Claude maps the information architecture, checks for dead ends, then outputs the full HTML. The prototype covers all scenarios flagged in the review.

**Save the prototype**: copy all code → save as `prototype_{project}.html` → open in browser.

### Step 5: Retrospective

Open a new conversation and send:

```
Please run a retrospective based on the uploaded interview_notes_{project}.json
and prd_{project}.md.

Analyse:
1. Requirements that appear in the PRD but were not clearly covered in the interview
2. Questions to ask proactively for similar future projects
3. 3–5 actionable lessons learned

Output as JSON:
{
  "lessons_learned": [...],
  "missed_requirements": [...],
  "interview_tips": [...]
}
```

Copy output → save as `review_{project}.json` → upload to Project.

---

## Project files over time

```
requirements-agent (Project)
│
├── [Fixed files — upload once, never change]
│   ├── research_system.txt
│   ├── document_system.txt
│   └── prototype_system.txt
│
└── [Accumulated files — add one set per project]
    ├── interview_notes_order-dashboard.json
    ├── prd_order-dashboard.md
    ├── review_order-dashboard.json
    ├── interview_notes_user-permissions.json
    ├── prd_user-permissions.md
    ├── review_user-permissions.json
    └── ...
```

Note: Claude Projects allow up to 20 uploaded files. Once you exceed ~15 projects, delete
the older `prd_*.md` files — the interview notes and review files carry more signal per token.

---

## Useful phrases

| Situation | What to say |
|-----------|-------------|
| Pass checkpoint ① | `confirmed, proceed to stage 2` |
| Pass checkpoint ② | `confirmed, proceed to stage 3` |
| Supplement interview | `The interview didn't cover the admin role — please ask follow-up questions` |
| Revise PRD | `Please fix all CRITICAL and MAJOR issues from the review and re-output the PRD` |
| Skip interview | `Skip the interview — use the uploaded interview_notes_{project}.json to generate the PRD` |
| Skip PRD | `Skip stage 2 — use the uploaded prd_{project}.md to generate the prototype` |
| Run retrospective | `Run a retrospective based on the uploaded notes and PRD, output JSON` |

---

## FAQ

**Q: Claude didn't ask for project info at the start — it just jumped in.**
Project Instructions aren't applied. Re-enter the Project → confirm Instructions are saved → open a new conversation.

**Q: The Stage 2.5 review didn't run automatically.**
Manually trigger it: "Please review the PRD above across the five dimensions and output a critical / major / minor issue list before asking me to confirm."

**Q: I ran out of messages mid-project.**
After the limit resets (~5 hours), open a new conversation and say:
"Continuing project: {name}. Stage 1 is complete and the notes are uploaded. Please start from Stage 2."

**Q: Claude's output isn't valid JSON.**
Add: "Please format the interview notes as a JSON object with these fields:
user_roles, pain_points, requirements, success_metrics, open_questions, summary, confidence_level."

**Q: Will uploaded files be used to train Anthropic's models?**
Go to claude.ai Settings → Privacy → disable "Allow Claude to train on my conversations".
