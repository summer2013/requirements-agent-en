"""
knowledge_base.py — Long-term memory module

Uses a local Chroma vector database to store and retrieve knowledge from
past projects. No cloud services required — data lives in ./kb_data/.

Dependencies: pip install chromadb anthropic

Each project is stored as three document types:
  1. project_summary       — project overview (used for similarity search)
  2. lessons_learned       — actionable takeaways (used to improve interviews)
  3. requirements_patterns — commonly missed requirements (used to avoid gaps)
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


# ── Initialisation ─────────────────────────────────────────
KB_DIR = Path(__file__).parent / "kb_data"
KB_DIR.mkdir(exist_ok=True)


def _get_client():
    """Lazy-load the Chroma client."""
    if not CHROMA_AVAILABLE:
        raise ImportError(
            "chromadb not installed. Run: pip install chromadb\n"
            "Without it, the knowledge base falls back to file-based search."
        )
    return chromadb.PersistentClient(path=str(KB_DIR))


def _get_collections():
    """Return the three Chroma collections."""
    client = _get_client()
    ef = embedding_functions.DefaultEmbeddingFunction()
    return {
        "summaries": client.get_or_create_collection(
            "project_summaries", embedding_function=ef
        ),
        "lessons": client.get_or_create_collection(
            "lessons_learned", embedding_function=ef
        ),
        "patterns": client.get_or_create_collection(
            "requirements_patterns", embedding_function=ef
        ),
    }


# ── Write — call after each project completes ──────────────
def save_project(
    project_id: str,
    project_name: str,
    industry: str,
    project_type: str,
    interview_notes: dict,
    prd_document: str,
    lessons_learned: list[str],
    common_missed_requirements: list[str],
):
    """
    Save project knowledge to the vector database.
    Called at the end of run_layer_one() in main.py.
    """
    cols = _get_collections()
    metadata = {
        "project_id": project_id,
        "project_name": project_name,
        "industry": industry,
        "project_type": project_type,
        "date": datetime.now().isoformat(),
    }

    # 1. Project summary (used for "find similar projects")
    summary_text = f"""
Project: {project_name}
Industry: {industry}
Type: {project_type}
User roles: {", ".join(r["role"] for r in interview_notes.get("user_roles", []))}
Core pain points: {"; ".join(p["pain"] for p in interview_notes.get("pain_points", []))}
Requirements summary: {interview_notes.get("summary", "")}
""".strip()

    cols["summaries"].upsert(
        ids=[project_id],
        documents=[summary_text],
        metadatas=[metadata],
    )

    # 2. Lessons learned (used for "improve interview quality")
    if lessons_learned:
        lessons_text = "\n".join(f"- {l}" for l in lessons_learned)
        cols["lessons"].upsert(
            ids=[f"{project_id}_lessons"],
            documents=[f"Project: {project_name}\nLessons:\n{lessons_text}"],
            metadatas=[metadata],
        )

    # 3. Missed requirements patterns (used for "avoid gaps")
    if common_missed_requirements:
        patterns_text = "\n".join(f"- {r}" for r in common_missed_requirements)
        cols["patterns"].upsert(
            ids=[f"{project_id}_patterns"],
            documents=[f"Project: {project_name}\nCommonly missed requirements:\n{patterns_text}"],
            metadatas=[metadata],
        )

    # JSON backup alongside the vector DB
    backup_path = KB_DIR / f"{project_id}.json"
    backup_path.write_text(json.dumps({
        "project_id": project_id,
        "project_name": project_name,
        "industry": industry,
        "project_type": project_type,
        "interview_notes": interview_notes,
        "lessons_learned": lessons_learned,
        "common_missed_requirements": common_missed_requirements,
        "date": metadata["date"],
    }, ensure_ascii=False, indent=2))

    print(f"  [knowledge base] saved: {project_name}")


# ── Read — call before each new project starts ─────────────
def search_similar_projects(query: str, n_results: int = 3) -> dict:
    """
    Semantic search for similar past projects.
    Results are injected into the research agent's context.
    """
    if not CHROMA_AVAILABLE:
        return _fallback_file_search(query, n_results)

    cols = _get_collections()

    summary_results = cols["summaries"].query(
        query_texts=[query], n_results=min(n_results, 3)
    )
    lesson_results = cols["lessons"].query(
        query_texts=[query], n_results=min(n_results, 3)
    )
    pattern_results = cols["patterns"].query(
        query_texts=[query], n_results=min(n_results, 2)
    )

    results = []
    for doc, meta, distance in zip(
        summary_results["documents"][0],
        summary_results["metadatas"][0],
        summary_results["distances"][0],
    ):
        relevance = round(1 - distance, 2)
        if relevance < 0.3:
            continue
        results.append({
            "type": "similar_project",
            "project_name": meta["project_name"],
            "relevance": relevance,
            "summary": doc,
        })

    lessons = [
        {"project": meta["project_name"], "content": doc}
        for doc, meta in zip(
            lesson_results["documents"][0],
            lesson_results["metadatas"][0],
        )
    ]

    patterns = [
        {"project": meta["project_name"], "content": doc}
        for doc, meta in zip(
            pattern_results["documents"][0],
            pattern_results["metadatas"][0],
        )
    ]

    return {
        "similar_projects": results,
        "lessons_learned": lessons,
        "requirement_patterns": patterns,
        "total_projects_in_kb": cols["summaries"].count(),
    }


def _fallback_file_search(query: str, n_results: int) -> dict:
    """
    Fallback when chromadb is not installed.
    Returns the most recent projects without semantic ranking.
    """
    files = sorted(KB_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    results = []
    for f in files[:n_results]:
        try:
            data = json.loads(f.read_text())
            results.append({
                "type": "similar_project",
                "project_name": data.get("project_name", ""),
                "relevance": 0.5,
                "summary": data.get("interview_notes", {}).get("summary", ""),
            })
        except Exception:
            continue
    return {
        "similar_projects": results,
        "lessons_learned": [],
        "requirement_patterns": [],
        "total_projects_in_kb": len(files),
        "note": "chromadb not installed — using file fallback (no semantic search)",
    }


def get_stats() -> dict:
    """Return knowledge base statistics."""
    if not CHROMA_AVAILABLE:
        files = list(KB_DIR.glob("*.json"))
        return {"total_projects": len(files), "mode": "file_fallback"}
    cols = _get_collections()
    return {
        "total_projects": cols["summaries"].count(),
        "total_lessons": cols["lessons"].count(),
        "total_patterns": cols["patterns"].count(),
        "mode": "chroma_vector_db",
        "storage_path": str(KB_DIR),
    }
