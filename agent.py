"""
agent.py — Core agentic loop

Runs any agent with tool-calling support. Business logic and tool handling
are injected via callbacks, keeping this module fully reusable.

Usage:
    result = run_agent(
        agent_name="research",
        system_prompt=open("prompts/research_system.txt").read(),
        tools=RESEARCH_TOOLS,
        model="claude-sonnet-4-6",
        tool_handler=my_handler,
        initial_message="Let's start the interview...",
        history=[],   # pass existing history to resume a conversation
    )
"""

import os
import anthropic
from typing import Callable

# Choose between OpenRouter and Anthropic direct API:
#   OpenRouter: set OPENROUTER_API_KEY, prefix model names with "anthropic/"
#   Anthropic:  set ANTHROPIC_API_KEY, use model names as-is
_openrouter_key = os.environ.get("OPENROUTER_API_KEY")
_anthropic_key  = os.environ.get("ANTHROPIC_API_KEY")

if _openrouter_key:
    client = anthropic.Anthropic(
        base_url="https://openrouter.ai/api/v1",
        api_key=_openrouter_key,
    )
elif _anthropic_key:
    client = anthropic.Anthropic(api_key=_anthropic_key)
else:
    raise EnvironmentError(
        "No API key found.\n"
        "Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY in your .env file.\n"
        "See .env.example for reference."
    )


def run_agent(
    agent_name: str,
    system_prompt: str,
    tools: list[dict],
    tool_handler: Callable[[str, dict], str],
    initial_message: str = "",
    history: list[dict] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    on_tool_call: Callable[[str, dict], None] = None,
) -> tuple[str, list[dict]]:
    """
    Run a single agent with multi-turn tool calling (agentic loop).

    Args:
        agent_name      Name used in logs
        system_prompt   System prompt text
        tools           Tool definition list
        tool_handler    Callback: (tool_name, tool_input) -> result string
        initial_message First user message (used when history is empty)
        history         Existing message history — pass to resume a conversation
        model           Model name
        max_tokens      Max output tokens
        temperature     Sampling temperature
        on_tool_call    Optional callback fired before each tool call (logging/UI)

    Returns:
        (final_text, updated_history)
        final_text      The agent's final text output
        updated_history Full message history for resuming later
    """
    msgs = list(history) if history else []

    if not msgs and initial_message:
        msgs.append({"role": "user", "content": initial_message})

    print(f"\n[{agent_name}] starting")

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            tools=tools,
            messages=msgs,
        )

        msgs.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"[{agent_name}] done")
            return final_text, msgs

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if on_tool_call:
                        on_tool_call(block.name, block.input)
                    print(f"  [{agent_name}] tool: {block.name}")
                    result = tool_handler(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            msgs.append({"role": "user", "content": tool_results})
