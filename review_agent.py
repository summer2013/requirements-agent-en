"""
review_agent.py — Retrospective agent

Runs automatically after each project completes. Compares interview notes
against the final PRD to extract lessons learned, then writes them back to
the knowledge base — creating a self-improving feedback loop.

Usage:
    result = run_review(
        project_name="Supply Chain Platform",
        interview_notes=notes_dict,
        prd_document=prd_text,
    )
    # result contains lessons_learned and missed_requirements
"""

import json
import os
from agent import run_agent


def _get_model() -> str:
    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    return "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"


REVIEW_SYSTEM = """You are an experienced product consultant specialising in project retrospectives.

Your task is to compare a project's interview notes against the final PRD and identify:
1. Important requirements that were missed during the interview (appear in PRD but not in notes)
2. Questions that should be asked proactively in future interviews for similar projects
3. Recurring patterns of requirements that users tend to overlook

Output format:
- lessons_learned: 3-5 actionable takeaways, one sentence each
- missed_requirements: list of requirements missed this time
- interview_tips: suggested interview questions for similar future projects

Format: strict JSON only, no extra text."""


REVIEW_TOOLS = [
    {
        "name": "save_review",
        "description": "Save the retrospective results",
        "input_schema": {
            "type": "object",
            "properties": {
                "lessons_learned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Actionable lessons, one sentence each"
                },
                "missed_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Requirements missed during the interview"
                },
                "interview_tips": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested interview questions for similar projects"
                },
                "project_type_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Project tags, e.g. ['internal tool', 'retail', 'B2B', 'automation']"
                }
            },
            "required": ["lessons_learned", "missed_requirements", "interview_tips"]
        }
    }
]


def run_review(
    project_name: str,
    industry: str,
    project_type: str,
    interview_notes: dict,
    prd_document: str,
) -> dict:
    """
    Run the retrospective agent and return extracted lessons.

    Args:
        project_name    Project name
        industry        Industry
        project_type    Project type
        interview_notes Structured interview notes dict
        prd_document    Final PRD text

    Returns:
        {
            "lessons_learned": [...],
            "missed_requirements": [...],
            "interview_tips": [...],
            "project_type_tags": [...]
        }
    """
    review_result = {}

    def handler(tool_name: str, tool_input: dict) -> str:
        if tool_name == "save_review":
            review_result.update(tool_input)
            return json.dumps({"success": True})
        return json.dumps({"error": "unknown tool"})

    initial_msg = f"""
Please run a retrospective on the following project:

Project name: {project_name}
Industry: {industry}
Type: {project_type}

[Interview Notes]
{json.dumps(interview_notes, ensure_ascii=False, indent=2)}

[Final PRD (key sections)]
{prd_document[:3000]}{"..." if len(prd_document) > 3000 else ""}

Please analyse:
1. Which requirements appear in the PRD but were not clearly covered in the interview notes?
2. For a "{project_type}" project, what questions should be asked proactively next time?
3. Extract 3-5 actionable lessons learned.

Call save_review when done.
""".strip()

    print("\n  [retrospective agent] analysing...")

    run_agent(
        agent_name="review",
        system_prompt=REVIEW_SYSTEM,
        tools=REVIEW_TOOLS,
        tool_handler=handler,
        initial_message=initial_msg,
        model=_get_model(),
        max_tokens=2048,
        temperature=0.2,
    )

    if review_result:
        print(f"  [retrospective agent] extracted {len(review_result.get('lessons_learned', []))} lessons")

    return review_result
