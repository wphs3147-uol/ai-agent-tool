"""
LLM-based task router for the AI Agent system.

Replaces keyword matching with GPT-powered intent classification.
The router examines user input and returns a structured routing
decision including which agent to invoke and why.
"""

import json
from core.logger import get_logger, retry

logger = get_logger("core.router")

# Registry of available agents and their capabilities
AGENT_REGISTRY = {
    "file_sorter": {
        "description": "Organises files in a directory by type (documents, images, videos, etc.)",
        "triggers": "file organisation, sorting downloads, cleaning up folders, grouping files",
    },
    "daily_briefing": {
        "description": "Captures screenshots of messaging apps (WhatsApp, Outlook, Messages), "
                       "runs OCR to extract text, and summarises communications via GPT",
        "triggers": "daily briefing, message summary, check messages, communication overview",
    },
}


def _build_routing_prompt(memory_context=None):
    """Construct the system prompt for the routing LLM call."""
    agent_descriptions = "\n".join(
        f"  - {name}: {info['description']} (typical triggers: {info['triggers']})"
        for name, info in AGENT_REGISTRY.items()
    )

    memory_section = ""
    if memory_context and memory_context != "No prior task history available.":
        memory_section = (
            f"\n\nPast interaction history (use this to inform your decision):\n"
            f"{memory_context}\n"
        )

    return (
        "You are a task routing engine for an AI automation system running on macOS.\n"
        "Given a user's natural language request, determine which agent should handle it.\n\n"
        f"Available agents:\n{agent_descriptions}\n"
        f"{memory_section}\n"
        "Respond with a JSON object (no markdown fencing) containing:\n"
        '  "agent": the agent name from the list above, or "none" if no agent matches,\n'
        '  "confidence": a float between 0 and 1,\n'
        '  "reasoning": a brief explanation of why this agent was selected,\n'
        '  "plan": a short step-by-step plan for executing the task.\n'
    )


@retry(max_attempts=3, base_delay=1.0)
def route_task(client, user_input, memory_context=None):
    """
    Use the LLM to classify user intent and select the appropriate agent.

    Args:
        client: An initialised OpenAI client.
        user_input: The raw natural language request from the user.
        memory_context: Optional string of past task history for context.

    Returns:
        dict with keys: agent, confidence, reasoning, plan
    """
    logger.info("Routing task: '%s'", user_input[:80])

    system_prompt = _build_routing_prompt(memory_context)

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        temperature=0.1,  # low temperature for consistent classification
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
    )

    raw = response.choices[0].message.content.strip()

    # Parse the JSON response, handling possible markdown fencing
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        decision = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON routing response, falling back to 'none'")
        decision = {
            "agent": "none",
            "confidence": 0.0,
            "reasoning": "Could not parse routing response.",
            "plan": raw,
        }

    # Validate the agent name
    if decision.get("agent") not in AGENT_REGISTRY and decision.get("agent") != "none":
        logger.warning("LLM routed to unknown agent '%s', falling back", decision.get("agent"))
        decision["agent"] = "none"
        decision["confidence"] = 0.0

    logger.info(
        "Routed to '%s' (confidence: %.2f): %s",
        decision.get("agent"),
        decision.get("confidence", 0),
        decision.get("reasoning", ""),
    )

    return decision
