"""
AI Agent Tool — Main Entry Point

An AI automation system that takes natural language input and executes
tasks locally on macOS. Integrates OCR for visual input, SQLite for
persistent memory (learning from past interactions), and LLM-based
reasoning to structure decisions.

Architecture:
    User Input → LLM Router → Agent Execution → Memory Store
                      ↑                              │
                      └──── past context ─────────────┘
"""

import sys
import os
from dotenv import load_dotenv
from openai import OpenAI

from core.logger import get_logger, TaskTimer, print_system_health
from core.router import route_task
from memory.memory_store import (
    log_task,
    update_task_outcome,
    log_interaction,
    log_error,
    build_memory_context,
)

load_dotenv()
logger = get_logger("main")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Agent dispatch table
# ---------------------------------------------------------------------------

def _run_file_sorter():
    from agents.file_sorter import sort_downloads_by_type
    return sort_downloads_by_type()


def _run_daily_briefing():
    from agents.daily_briefing import run_daily_briefing
    return run_daily_briefing()


AGENT_DISPATCH = {
    "file_sorter":    _run_file_sorter,
    "daily_briefing": _run_daily_briefing,
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(user_input):
    """
    Full pipeline: route → confirm → execute → record.

    Every step is logged and persisted to SQLite so the system
    learns from past successes and failures.
    """
    logger.info("New task received: '%s'", user_input[:100])

    # 1. Build memory context from past interactions
    memory_context = build_memory_context(user_input)
    if memory_context != "No prior task history available.":
        logger.info("Memory context loaded — %d chars of history", len(memory_context))

    # 2. Route the task via LLM
    try:
        decision = route_task(client, user_input, memory_context)
    except Exception as e:
        logger.error("Routing failed: %s", e)
        task_id = log_task(user_input, routed_to=None)
        update_task_outcome(task_id, "failure", error_type="routing_error", error_msg=str(e))
        log_error("routing_error", str(e), component="router", task_id=task_id)
        print(f"\n[ERROR] Could not process your request: {e}")
        return

    agent_name = decision.get("agent", "none")
    confidence = decision.get("confidence", 0)
    plan = decision.get("plan", "")

    # 3. Log the task to persistent memory
    task_id = log_task(user_input, routed_to=agent_name, plan=plan)
    log_interaction(task_id, "user", user_input)
    log_interaction(task_id, "assistant", f"Routed to: {agent_name} ({confidence:.0%} confidence)")

    # 4. Present the plan
    print(f"\n--- Task Plan ---")
    print(f"Agent:      {agent_name}")
    print(f"Confidence: {confidence:.0%}")
    print(f"Reasoning:  {decision.get('reasoning', 'N/A')}")
    print(f"Plan:       {plan}")
    print(f"-----------------\n")

    # 5. Handle unroutable tasks
    if agent_name == "none" or agent_name not in AGENT_DISPATCH:
        msg = (
            "This task could not be matched to an available agent.\n"
            "The plan above may still be useful as guidance."
        )
        print(msg)
        update_task_outcome(task_id, "cancelled")
        log_interaction(task_id, "assistant", msg)
        return

    # 6. Confirm with the user before executing
    confirm = input(f"Run '{agent_name}' now? (y/n): ").strip().lower()
    if confirm != "y":
        print("Task cancelled.")
        update_task_outcome(task_id, "cancelled")
        log_interaction(task_id, "user", "User cancelled execution")
        return

    # 7. Execute the agent with timing and error handling
    logger.info("Executing agent: %s", agent_name)
    timer = TaskTimer()

    try:
        with timer:
            result = AGENT_DISPATCH[agent_name]()

        update_task_outcome(
            task_id,
            outcome="success",
            duration_ms=timer.elapsed_ms,
            metadata=result if isinstance(result, dict) else {"result": str(result)},
        )
        log_interaction(task_id, "assistant", f"Completed in {timer.elapsed_ms}ms")
        logger.info("Task completed successfully in %dms", timer.elapsed_ms)

    except Exception as e:
        duration = timer.elapsed_ms if timer.elapsed_ms else None
        error_type = type(e).__name__

        update_task_outcome(
            task_id,
            outcome="failure",
            error_type=error_type,
            error_msg=str(e),
            duration_ms=duration,
        )
        log_error(error_type, str(e), component=agent_name, task_id=task_id)
        log_interaction(task_id, "assistant", f"Failed: {error_type} — {e}")

        logger.error("Task failed: %s — %s", error_type, e, exc_info=True)
        print(f"\n[ERROR] Task failed: {e}")
        print("This error has been recorded. The system will account for it in future tasks.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Support --health flag to print system monitoring summary
    if len(sys.argv) > 1 and sys.argv[1] == "--health":
        print_system_health()
        sys.exit(0)

    user_input = input("What task would you like to automate? ").strip()

    if not user_input:
        print("No input provided.")
        sys.exit(1)

    run(user_input)
