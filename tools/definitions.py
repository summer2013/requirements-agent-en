"""
tools/definitions.py — Tool schemas for all agents

All tool definitions live here, decoupled from system prompts.
Updating a tool schema never requires touching a prompt file.
"""

# ── Research agent tools ───────────────────────────────────
RESEARCH_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the internal knowledge base for similar past projects, "
            "industry best practices, and competitive insights. "
            "Must be called at the start of every interview before asking any questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords, e.g. 'e-commerce inventory management' or 'medical SaaS permissions'"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["similar_projects", "industry_research", "competitive_analysis"],
                    "description": "Type of search to perform"
                }
            },
            "required": ["query", "search_type"]
        }
    },
    {
        "name": "ask_question",
        "description": (
            "Ask the user/product owner a single interview question and wait for their answer. "
            "Ask one question at a time. Decide the next question only after receiving the answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The interview question"
                },
                "phase": {
                    "type": "string",
                    "enum": ["background", "pain_points", "validation"],
                    "description": "Current interview phase"
                },
                "internal_note": {
                    "type": "string",
                    "description": "Why you're asking this question (not shown to the user)"
                }
            },
            "required": ["question", "phase"]
        }
    },
    {
        "name": "save_interview_notes",
        "description": (
            "Save structured interview notes after the interview is complete. "
            "Only call this when you have a thorough understanding of the user's needs. "
            "Calling this tool signals the end of the interview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_roles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "description": {"type": "string"},
                            "technical_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high"]
                            },
                            "headcount": {"type": "integer"}
                        },
                        "required": ["role", "description"]
                    }
                },
                "pain_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job": {"type": "string", "description": "The job-to-be-done"},
                            "current_solution": {"type": "string", "description": "How it's handled today"},
                            "pain": {"type": "string", "description": "Specific pain point"},
                            "severity": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "description": "Severity score 1-10"
                            },
                            "frequency": {
                                "type": "string",
                                "enum": ["daily", "weekly", "monthly"],
                                "description": "How often this occurs"
                            }
                        },
                        "required": ["job", "pain", "severity"]
                    }
                },
                "requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "feature": {"type": "string"},
                            "source_quote": {"type": "string", "description": "Direct quote from the user"},
                            "priority": {
                                "type": "string",
                                "enum": ["Must", "Should", "Could", "Won't"]
                            }
                        },
                        "required": ["feature", "priority"]
                    }
                },
                "success_metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quantifiable success metrics"
                },
                "open_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Questions that still need clarification"
                },
                "summary": {
                    "type": "string",
                    "description": "Interview summary in under 200 words, written for downstream agents"
                },
                "confidence_level": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Confidence in understanding the requirements"
                }
            },
            "required": ["user_roles", "pain_points", "requirements", "summary", "confidence_level"]
        }
    }
]

# ── Document agent tools ───────────────────────────────────
DOCUMENT_TOOLS = [
    {
        "name": "get_interview_notes",
        "description": "Read the structured interview notes produced by the research agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "search_prd_templates",
        "description": "Search the knowledge base for PRD templates from similar past projects",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "description": "Project type, e.g. 'e-commerce', 'SaaS dashboard', 'mobile app'"
                },
                "industry": {
                    "type": "string",
                    "description": "Industry, e.g. 'retail', 'healthcare', 'education'"
                }
            },
            "required": ["project_type"]
        }
    },
    {
        "name": "save_prd",
        "description": "Save the completed PRD Markdown document to shared state",
        "input_schema": {
            "type": "object",
            "properties": {
                "prd_markdown": {
                    "type": "string",
                    "description": "Full PRD document in Markdown format"
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "total_stories": {"type": "integer"},
                        "must_have_count": {"type": "integer"},
                        "total_story_points": {"type": "integer"},
                        "estimated_sprints": {"type": "number"}
                    }
                }
            },
            "required": ["prd_markdown"]
        }
    }
]

# ── Prototype agent tools ──────────────────────────────────
PROTOTYPE_TOOLS = [
    {
        "name": "get_prd",
        "description": (
            "Read the PRD document and the PRD review report. "
            "The review report's missing_scenarios and closure_gaps are the required coverage checklist for the prototype."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "check_closure",
        "description": (
            "Submit a closure self-check report before saving the prototype. "
            "Lists all pages with their entry/exit points and confirms all flagged missing scenarios are covered. "
            "Returns whether the check passed, plus any uncovered scenarios or dead-end pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pages": {
                    "type": "array",
                    "description": "Closure check data for every page in the prototype",
                    "items": {
                        "type": "object",
                        "properties": {
                            "page_name": {"type": "string"},
                            "entry_from": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Pages/actions that lead to this page"
                            },
                            "exit_to": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Where the user can go from this page"
                            },
                            "states_covered": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "States implemented: empty / loading / success / error / disabled"
                            }
                        },
                        "required": ["page_name", "entry_from", "exit_to", "states_covered"]
                    }
                },
                "missing_scenarios_coverage": {
                    "type": "array",
                    "description": "Coverage status for each scenario flagged in the PRD review report",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scenario": {"type": "string"},
                            "covered": {"type": "boolean"},
                            "covered_in_page": {"type": "string", "description": "Which page or modal handles it"}
                        },
                        "required": ["scenario", "covered"]
                    }
                }
            },
            "required": ["pages", "missing_scenarios_coverage"]
        }
    },
    {
        "name": "save_prototype",
        "description": "Save the HTML prototype. Only callable after check_closure has passed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "Complete single-file HTML prototype"
                },
                "pages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of pages included in the prototype"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes for reviewers — must confirm closure check passed"
                },
                "closure_verified": {
                    "type": "boolean",
                    "description": "Must be true — confirms check_closure was called and passed"
                }
            },
            "required": ["html", "closure_verified"]
        }
    }
]
