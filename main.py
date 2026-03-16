"""
main.py — Orchestrator entry point

Usage:
    python main.py --project-name "Supply Chain Dashboard" --brief "Background..."
    python main.py --interactive
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime

from agent import run_agent
from tools.definitions import RESEARCH_TOOLS, DOCUMENT_TOOLS, PROTOTYPE_TOOLS
from tool_handlers import make_research_handler, make_document_handler, make_prototype_handler_v2
from review_agent import run_review
from prd_review_agent import run_prd_review, format_review_report
from knowledge_base import save_project, get_stats


def load_prompt(name: str) -> str:
    path = Path(__file__).parent / "prompts" / "api" / f"{name}_system.txt"
    return path.read_text(encoding="utf-8")


def check_env():
    """Verify API key is configured before starting."""
    has_anthropic  = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    if not has_anthropic and not has_openrouter:
        print("Error: no API key found.")
        print("Copy .env.example to .env and add your ANTHROPIC_API_KEY or OPENROUTER_API_KEY.")
        return False
    provider = "OpenRouter" if has_openrouter else "Anthropic"
    print(f"[startup] using {provider} API")
    return True


def hitl_check(title: str, summary: str, data: dict = None) -> tuple[bool, str]:
    """
    Human-in-the-loop checkpoint.
    Returns (approved, feedback).
    """
    print(f"\n{'='*60}")
    print(f"Checkpoint: {title}")
    print(f"{'='*60}")
    print(summary)
    if data:
        print("\nFull data:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:800] + "...")

    while True:
        choice = input("\n[Approve (y) / Request changes (n)] > ").strip().lower()
        if choice in ("y", "yes", ""):
            return True, ""
        elif choice in ("n", "no"):
            feedback = input("Describe the changes needed > ").strip()
            if feedback:
                return False, feedback
            print("Feedback cannot be empty. Please try again.")


def run_layer_one(project_name: str, project_brief: str, output_dir: str = "outputs"):
    """Run the full pipeline: research → PRD → PRD review → prototype → retrospective."""

    if not check_env():
        return

    use_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    MODEL_STRONG = "anthropic/claude-opus-4-5"   if use_openrouter else "claude-opus-4-5"
    MODEL_FAST   = "anthropic/claude-sonnet-4-6" if use_openrouter else "claude-sonnet-4-6"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = Path(output_dir) / f"{project_name}_{ts}"
    project_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {project_dir}")

    state = {
        "project_name": project_name,
        "project_brief": project_brief,
        "interview_notes": None,
        "prd_document": None,
        "prd_review": None,
        "prototype_html": None,
    }

    # ── Stage 1: Research interview ────────────────────────
    print("\n▶ Stage 1/4: Requirements interview")
    research_history = []
    max_revisions = 3

    for attempt in range(max_revisions):
        handler = make_research_handler(state)
        _, research_history = run_agent(
            agent_name="research",
            system_prompt=load_prompt("research"),
            tools=RESEARCH_TOOLS,
            tool_handler=handler,
            initial_message=f"Project name: {project_name}\n\nBrief: {project_brief}\n\nPlease begin the requirements interview.",
            history=research_history if attempt > 0 else [],
            model=MODEL_STRONG,
            temperature=0.3,
        )

        notes = state.get("interview_notes")
        approved, feedback = hitl_check(
            "Interview notes review",
            f"Roles identified: {len(notes.get('user_roles', []))}\n"
            f"Pain points: {len(notes.get('pain_points', []))}\n"
            f"Requirements: {len(notes.get('requirements', []))}\n"
            f"Confidence: {notes.get('confidence_level', '?')}",
            notes,
        )

        if approved:
            notes_path = project_dir / "interview_notes.json"
            notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2))
            print(f"✓ Interview notes saved: {notes_path}")
            break
        else:
            research_history.append({
                "role": "user",
                "content": f"Please expand the interview based on this feedback: {feedback}"
            })
    else:
        print("✗ Max revisions reached on interview stage. Manual intervention required.")
        return

    # ── Stage 2: PRD generation ────────────────────────────
    print("\n▶ Stage 2/4: Generate PRD")
    document_history = []

    for attempt in range(max_revisions):
        handler = make_document_handler(state)
        _, document_history = run_agent(
            agent_name="document",
            system_prompt=load_prompt("document"),
            tools=DOCUMENT_TOOLS,
            tool_handler=handler,
            initial_message="Please read the interview notes and generate a complete PRD.",
            history=document_history if attempt > 0 else [],
            model=MODEL_FAST,
            max_tokens=8192,
            temperature=0.1,
        )

        prd = state.get("prd_document", "")

        # ── Stage 2.5: Automated PRD review ───────────────
        print("\n  ▷ Running PRD review agent...")
        prd_review = run_prd_review(
            prd_document=prd,
            interview_notes=state.get("interview_notes", {}),
        )
        state["prd_review"] = prd_review

        review_report_path = project_dir / "prd_review_report.json"
        review_report_path.write_text(json.dumps(prd_review, ensure_ascii=False, indent=2))
        print(f"  ✓ PRD review report saved: {review_report_path}")

        approved, feedback = hitl_check(
            "PRD + Review report",
            format_review_report(prd_review),
        )

        if approved:
            prd_path = project_dir / "prd.md"
            prd_path.write_text(prd, encoding="utf-8")
            print(f"✓ PRD saved: {prd_path}")
            break
        else:
            auto_issues = format_review_report(prd_review)
            document_history.append({
                "role": "user",
                "content": (
                    f"The PRD review found these issues — please revise:\n{auto_issues}"
                    + (f"\n\nAdditional feedback: {feedback}" if feedback else "")
                )
            })
    else:
        print("✗ Max revisions reached on PRD stage. Manual intervention required.")
        return

    # ── Stage 3: HTML prototype ────────────────────────────
    print("\n▶ Stage 3/4: Generate HTML prototype")
    handler = make_prototype_handler_v2(state)
    run_agent(
        agent_name="prototype",
        system_prompt=load_prompt("prototype"),
        tools=PROTOTYPE_TOOLS,
        tool_handler=handler,
        initial_message=(
            "Please read the PRD and review report, then follow these steps:\n"
            "1. Map the information architecture (page list)\n"
            "2. Confirm every flow has an exit (no dead ends)\n"
            "3. Generate the HTML prototype, covering all missing_scenarios from the review report\n"
            "4. Call check_closure to verify completeness\n"
            "5. Call save_prototype only after check_closure passes"
        ),
        model=MODEL_FAST,
        max_tokens=16384,
        temperature=0.2,
    )

    html = state.get("prototype_html", "")
    proto_path = project_dir / "prototype.html"
    proto_path.write_text(html, encoding="utf-8")
    print(f"✓ Prototype saved: {proto_path}")

    # ── Stage 4: Retrospective + knowledge base ────────────
    print("\n▶ Stage 4/4: Retrospective & knowledge base")

    industry  = input("Industry tag (e.g. retail / healthcare / education, Enter to skip) > ").strip() or "general"
    proj_type = input("Project type (e.g. internal tool / SaaS / mobile app, Enter to skip) > ").strip() or "B2B system"

    review = run_review(
        project_name=project_name,
        industry=industry,
        project_type=proj_type,
        interview_notes=state.get("interview_notes", {}),
        prd_document=state.get("prd_document", ""),
    )

    review_path = project_dir / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2))
    print(f"✓ Retrospective saved: {review_path}")

    save_project(
        project_id=ts,
        project_name=project_name,
        industry=industry,
        project_type=proj_type,
        interview_notes=state.get("interview_notes", {}),
        prd_document=state.get("prd_document", ""),
        lessons_learned=review.get("lessons_learned", []),
        common_missed_requirements=review.get("missed_requirements", []),
    )

    stats = get_stats()
    print(f"  Knowledge base now contains {stats['total_projects']} project(s)")

    # ── Summary ────────────────────────────────────────────
    prd_review = state.get("prd_review", {})
    closure = state.get("closure_check", {})
    print(f"\n{'='*60}")
    print(f"Done! All files saved to: {project_dir}")
    print(f"  - interview_notes.json      Interview notes")
    print(f"  - prd.md                    PRD document")
    print(f"  - prd_review_report.json    PRD review report")
    print(f"  - prototype.html            Interactive prototype")
    print(f"  - review.json               Retrospective (written to knowledge base)")
    print(f"\nQuality summary:")
    assessment = prd_review.get("overall_assessment", {})
    print(f"  PRD review: Critical {assessment.get('critical_count',0)} / "
          f"Major {assessment.get('major_count',0)} / "
          f"Minor {assessment.get('minor_count',0)}")
    if closure:
        status = "✅ passed" if closure.get("passed") else "⚠️  has uncovered items"
        print(f"  Prototype closure: {status}")
    print(f"{'='*60}")

    if review.get("lessons_learned"):
        print("\nLessons learned this project:")
        for i, l in enumerate(review["lessons_learned"], 1):
            print(f"  {i}. {l}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Requirements agent pipeline")
    parser.add_argument("--project-name", help="Project name")
    parser.add_argument("--brief", help="Project brief")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    if args.interactive or not args.project_name:
        print("=== Requirements Agent Pipeline ===")
        name = input("Project name > ").strip()
        brief = input("Project brief (multi-line, blank line to finish) >\n")
        lines = [brief]
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        brief = "\n".join(lines)
    else:
        name = args.project_name
        brief = args.brief

    run_layer_one(name, brief)
