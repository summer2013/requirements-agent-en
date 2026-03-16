"""
prd_review_agent.py — PRD Review Agent

Runs automatically after PRD generation and before prototyping begins.
Checks the PRD across 5 dimensions and outputs a structured review report
for human confirmation and prototype agent consumption.

Review dimensions:
  1. Structural completeness  — background, goals, roles, scope, error handling
  2. Logic consistency        — preconditions, post-states, reversibility
  3. Flow closure             — every flow has an exit, every action has feedback
  4. Scenario coverage (MECE) — empty states, errors, timeouts, concurrent edits
  5. Multi-role coordination  — handoffs, notifications, wait states, timeouts
"""

import json
import os
from agent import run_agent


def _get_model() -> str:
    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    return "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"


PRD_REVIEW_SYSTEM = """You are a senior requirements review expert. Your job is to find all logic gaps and missing scenarios in a PRD before it reaches the prototype stage.

Review the PRD across five dimensions and produce a structured report.

---

## Dimension 1: Structural Completeness

Check that the PRD contains:
- Background & goals (why build this? what are the measurable success metrics?)
- User roles (with explicit permission boundaries for each)
- Scope (both In Scope and Out of Scope clearly stated)
- Error & edge case handling (empty data, network failure, insufficient permissions)
- Dependencies (external systems, APIs, teams)

Any missing item = critical issue.

---

## Dimension 2: Logic Consistency

For each user story, challenge it with:
1. Precondition: What state must the system/user be in before this action?
2. Trigger: What causes this feature to activate?
3. Post-state: What state are the system and user in after the action? Is it explicit?
4. Reversibility: Can this action be undone? If not, is there a confirmation step?

Missing post-state on any story = major issue.

---

## Dimension 3: Flow Closure

For each business flow, check:
- Every branch of every decision point has an exit
- No dead ends — user cannot get stuck with no way forward or back
- Every completed action has clear feedback (success/failure message)
- Data flow is defined: where it comes from, where it goes, who is notified of changes

---

## Dimension 4: Scenario Coverage (MECE)

For each core business object (e.g. Order, Request, Task), enumerate all states and check:
- Does the PRD describe the UI and available actions for each state?

Required checklist:
□ List views: empty state described?
□ List views: pagination/loading strategy for large data sets?
□ Forms: validation rules and error messages for each field?
□ Forms: what happens to entered data on submission failure?
□ Async operations: loading/in-progress state described?
□ Network errors/timeouts: retry or error message described?
□ Concurrent edits: two users editing the same record simultaneously?
□ Mid-flow exit: draft saving or data loss warning?

---

## Dimension 5: Multi-Role Coordination

If the PRD involves multiple roles (approval flows, notifications):
- Is the actor and recipient defined for every step?
- Is there a visual state for "waiting" (pending approval, awaiting confirmation)?
- Are notification trigger timing and content explicitly defined?
- What happens when a step times out with no action?

---

## Output

Call save_prd_review with results strictly matching the tool schema.

Severity definitions:
- critical: missing this would cause the product to fail or corrupt data
- major: blocks core user flows; must be fixed before prototyping
- minor: UX detail; can be addressed in a later iteration

Set overall_assessment.ready_for_prototype to false if critical_count > 0.
"""


PRD_REVIEW_TOOLS = [
    {
        "name": "save_prd_review",
        "description": "Save the PRD review report",
        "input_schema": {
            "type": "object",
            "properties": {
                "structural_issues": {
                    "type": "array",
                    "description": "Structural completeness issues",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            "dimension": {"type": "string", "description": "Which review dimension"},
                            "issue": {"type": "string", "description": "Description of the problem"},
                            "location": {"type": "string", "description": "Where in the PRD (story ID or section)"},
                            "suggestion": {"type": "string", "description": "How to fix it"}
                        },
                        "required": ["severity", "dimension", "issue", "suggestion"]
                    }
                },
                "missing_scenarios": {
                    "type": "array",
                    "description": "Missing scenarios (empty states, errors, edge cases, concurrency)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object": {"type": "string", "description": "Business object involved, e.g. 'Order'"},
                            "scenario": {"type": "string", "description": "The missing scenario"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            "suggested_handling": {"type": "string", "description": "Recommended approach"}
                        },
                        "required": ["object", "scenario", "severity", "suggested_handling"]
                    }
                },
                "closure_gaps": {
                    "type": "array",
                    "description": "Flow closure problems (dead ends, missing exits, no feedback)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flow": {"type": "string", "description": "The affected flow"},
                            "gap": {"type": "string", "description": "Description of the closure gap"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]}
                        },
                        "required": ["flow", "gap", "severity"]
                    }
                },
                "multi_role_gaps": {
                    "type": "array",
                    "description": "Multi-role coordination issues",
                    "items": {
                        "type": "object",
                        "properties": {
                            "roles_involved": {"type": "array", "items": {"type": "string"}},
                            "gap": {"type": "string"},
                            "severity": {"type": "string", "enum": ["critical", "major", "minor"]}
                        },
                        "required": ["roles_involved", "gap", "severity"]
                    }
                },
                "overall_assessment": {
                    "type": "object",
                    "properties": {
                        "ready_for_prototype": {
                            "type": "boolean",
                            "description": "Whether it's safe to proceed to prototyping"
                        },
                        "critical_count": {"type": "integer"},
                        "major_count": {"type": "integer"},
                        "minor_count": {"type": "integer"},
                        "summary": {
                            "type": "string",
                            "description": "Overall assessment in under 100 words"
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "Key things the prototype agent must ensure are covered"
                        }
                    },
                    "required": ["ready_for_prototype", "critical_count", "major_count", "minor_count", "summary", "recommendation"]
                }
            },
            "required": ["structural_issues", "missing_scenarios", "closure_gaps", "overall_assessment"]
        }
    }
]


def run_prd_review(prd_document: str, interview_notes: dict) -> dict:
    """
    Run the PRD review agent.

    Args:
        prd_document    Full PRD in Markdown
        interview_notes Original interview notes dict (for cross-checking)

    Returns:
        Structured review report dict
    """
    review_result = {}

    def handler(tool_name: str, tool_input: dict) -> str:
        if tool_name == "save_prd_review":
            review_result.update(tool_input)
            return json.dumps({"success": True})
        return json.dumps({"error": "unknown tool"})

    roles_summary = ", ".join(
        r.get("role", "") for r in interview_notes.get("user_roles", [])
    )
    requirements_summary = "\n".join(
        f"- [{r.get('priority')}] {r.get('feature')}"
        for r in interview_notes.get("requirements", [])
    )

    initial_msg = f"""Please review the following PRD.

## Context (from interview notes)
User roles: {roles_summary}
Core requirements:
{requirements_summary}

## PRD to review

{prd_document}

---

Review across all five dimensions, then call save_prd_review with your findings.
Pay special attention to: empty states, error flows, flow exits, and multi-role wait states.
""".strip()

    print("\n  [PRD review agent] reviewing...")

    run_agent(
        agent_name="prd_review",
        system_prompt=PRD_REVIEW_SYSTEM,
        tools=PRD_REVIEW_TOOLS,
        tool_handler=handler,
        initial_message=initial_msg,
        model=_get_model(),
        max_tokens=4096,
        temperature=0.1,
    )

    assessment = review_result.get("overall_assessment", {})
    c = assessment.get("critical_count", 0)
    m = assessment.get("major_count", 0)
    n = assessment.get("minor_count", 0)
    print(f"  [PRD review agent] {c} critical / {m} major / {n} minor")

    return review_result


def format_review_report(review: dict) -> str:
    """Format a review report dict as a readable string for HITL display."""
    lines = []
    assessment = review.get("overall_assessment", {})

    lines.append(f"Summary: {assessment.get('summary', '')}")
    lines.append(
        f"Issues: Critical {assessment.get('critical_count', 0)} / "
        f"Major {assessment.get('major_count', 0)} / "
        f"Minor {assessment.get('minor_count', 0)}"
    )
    lines.append(
        f"Ready for prototype: {'✅ Yes' if assessment.get('ready_for_prototype') else '⚠️  Recommend fixing PRD first'}"
    )

    for label, key in [
        ("Structural issues", "structural_issues"),
        ("Missing scenarios", "missing_scenarios"),
        ("Closure gaps", "closure_gaps"),
        ("Multi-role gaps", "multi_role_gaps"),
    ]:
        items = review.get(key, [])
        if not items:
            continue
        lines.append(f"\n── {label} ({len(items)}) ──")
        for item in items:
            sev = item.get("severity", "").upper()
            if key == "missing_scenarios":
                lines.append(
                    f"  [{sev}] [{item.get('object')}] {item.get('scenario')}\n"
                    f"    → {item.get('suggested_handling')}"
                )
            elif key == "multi_role_gaps":
                roles = " + ".join(item.get("roles_involved", []))
                lines.append(f"  [{sev}] [{roles}] {item.get('gap')}")
            elif key == "closure_gaps":
                lines.append(f"  [{sev}] [{item.get('flow')}] {item.get('gap')}")
            else:
                lines.append(
                    f"  [{sev}] {item.get('issue')}\n"
                    f"    → {item.get('suggestion')}"
                )

    if assessment.get("recommendation"):
        lines.append(f"\nPrototype agent notes:\n  {assessment['recommendation']}")

    return "\n".join(lines)
