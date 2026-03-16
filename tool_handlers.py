"""
tool_handlers.py — Tool handler factories

Each agent gets its own handler factory. Handlers share state via closure,
enabling data to flow between agents without global variables.

To integrate with external systems (Confluence, Jira, Notion, etc.),
only this file needs to change — agent.py and prompts stay untouched.
"""

import json
from knowledge_base import search_similar_projects


def make_research_handler(state: dict):
    """
    Tool handler for the research agent.
    ask_question reads from stdin in CLI mode.
    Replace with WebSocket or message queue for a web interface.
    """
    def handler(tool_name: str, tool_input: dict) -> str:

        # ── Search knowledge base ─────────────────────────
        if tool_name == "search_knowledge_base":
            try:
                results = search_similar_projects(
                    query=tool_input["query"],
                    n_results=3,
                )
                if results["total_projects_in_kb"] == 0:
                    return json.dumps({
                        "message": "Knowledge base is empty — this is the first project of this type.",
                        "similar_projects": [],
                        "lessons_learned": [],
                        "requirement_patterns": [],
                    })
                return json.dumps(results)
            except Exception as e:
                return json.dumps({
                    "message": f"Knowledge base query failed ({e}). Proceeding without it.",
                    "similar_projects": [],
                    "lessons_learned": [],
                })

        # ── Ask the user a question ───────────────────────
        if tool_name == "ask_question":
            question = tool_input["question"]
            print(f"\n[Interview] {question}")
            answer = input("Answer > ").strip()
            return json.dumps({"question": question, "answer": answer})

        # ── Save interview notes ──────────────────────────
        if tool_name == "save_interview_notes":
            state["interview_notes"] = tool_input
            return json.dumps({"success": True})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    return handler


def make_document_handler(state: dict):
    """Tool handler for the document agent."""
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_interview_notes":
            notes = state.get("interview_notes")
            if not notes:
                return json.dumps({"error": "Interview notes not yet generated"})
            return json.dumps(notes)

        if tool_name == "search_prd_templates":
            try:
                results = search_similar_projects(
                    query=tool_input.get("project_type", ""),
                    n_results=2,
                )
                return json.dumps({
                    "similar_projects": results.get("similar_projects", []),
                    "default_template": {
                        "name": "Standard B2B SaaS Template",
                        "sections": ["Background", "User Stories", "NFR", "MoSCoW", "Open Questions"]
                    }
                })
            except Exception:
                return json.dumps({
                    "templates": [
                        {"name": "Standard B2B SaaS Template",
                         "sections": ["Background", "User Stories", "NFR", "MoSCoW"]}
                    ]
                })

        if tool_name == "save_prd":
            state["prd_document"] = tool_input["prd_markdown"]
            state["prd_metadata"] = tool_input.get("metadata", {})
            return json.dumps({"success": True})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    return handler


def make_prototype_handler(state: dict):
    """Tool handler for the prototype agent (legacy — use make_prototype_handler_v2)."""
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_prd":
            prd = state.get("prd_document")
            if not prd:
                return json.dumps({"error": "PRD not yet generated"})
            return json.dumps({"prd": prd})

        if tool_name == "save_prototype":
            state["prototype_html"] = tool_input["html"]
            return json.dumps({"success": True})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    return handler


def make_prototype_handler_v2(state: dict):
    """
    Tool handler for the prototype agent (v2).
    Injects the PRD review report alongside the PRD, and enforces
    closure verification before save_prototype is allowed.
    """
    def handler(tool_name: str, tool_input: dict) -> str:

        if tool_name == "get_prd":
            prd = state.get("prd_document")
            if not prd:
                return json.dumps({"error": "PRD not yet generated"})
            review = state.get("prd_review", {})
            return json.dumps({
                "prd": prd,
                "prd_review_report": {
                    "missing_scenarios": review.get("missing_scenarios", []),
                    "closure_gaps": review.get("closure_gaps", []),
                    "multi_role_gaps": review.get("multi_role_gaps", []),
                    "prototype_notes": review.get("overall_assessment", {}).get(
                        "recommendation", "No special notes"
                    ),
                }
            })

        if tool_name == "check_closure":
            review = state.get("prd_review", {})
            # Collect critical/major scenarios that must be covered
            expected_scenarios = [
                s.get("scenario", "")
                for s in review.get("missing_scenarios", [])
                if s.get("severity") in ("critical", "major")
            ]
            coverage = tool_input.get("missing_scenarios_coverage", [])
            uncovered = [
                s for s in expected_scenarios
                if not any(
                    c.get("covered") and s in c.get("scenario", "")
                    for c in coverage
                )
            ]
            pages = tool_input.get("pages", [])
            dead_ends = [p["page_name"] for p in pages if not p.get("exit_to")]

            passed = len(uncovered) == 0 and len(dead_ends) == 0
            state["closure_check"] = {
                "passed": passed,
                "uncovered_scenarios": uncovered,
                "dead_end_pages": dead_ends,
            }
            return json.dumps({
                "passed": passed,
                "uncovered_critical_scenarios": uncovered,
                "dead_end_pages": dead_ends,
                "message": (
                    "✅ Closure check passed. You may now call save_prototype." if passed
                    else f"⚠️  Closure check failed: {len(uncovered)} scenario(s) uncovered, "
                         f"{len(dead_ends)} dead-end page(s). Fix and recheck before saving."
                )
            })

        if tool_name == "save_prototype":
            if not tool_input.get("closure_verified", False):
                return json.dumps({
                    "error": "You must call check_closure and confirm it passed before saving. Set closure_verified to true."
                })
            state["prototype_html"] = tool_input["html"]
            state["prototype_pages"] = tool_input.get("pages", [])
            return json.dumps({"success": True})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    return handler
