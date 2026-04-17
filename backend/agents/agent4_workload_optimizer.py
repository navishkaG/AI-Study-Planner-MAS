"""
agents/agent4_workload_optimizer.py — Agent 4: Workload Conflict Optimizer

Persona:
    Study plan optimizer that detects schedule overloads and applies
    minimum-cost fixes to future tasks while preserving near-term stability.

Responsibilities:
    - Analyze the generated schedule for overloads and hard-day streaks
    - Lock today's and tomorrow's tasks (they cannot be moved)
    - Apply minimum-cost algorithmic fixes to future unlocked tasks
    - Generate a user-friendly change notification via LLM

LLM Role:
    ONLY generates the natural-language notification message.
    ALL conflict detection and optimization logic is pure Python (no LLM).
    This is a deliberate design choice: deterministic code is more reliable
    and testable than asking an LLM to reason about scheduling constraints.

Tool Used:
    tools/workload_analyzer.py → optimize_schedule()

Student: Student 4
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import StudyPlanState
from tools.workload_analyzer import optimize_schedule
from utils import call_ollama, log_trace


SYSTEM_PROMPT = """
You are a study plan optimizer assistant. Your job is to write a short,
friendly message to a student explaining what changes were made to their
study plan and why.

CONSTRAINTS:
- NEVER invent changes that are not in the provided optimizer log.
- Only describe changes that appear in the log.
- Be reassuring — emphasize the core plan is preserved.
- Mention that today's and tomorrow's tasks were NOT changed.
- Keep your response under 150 words.
- Use plain, friendly language. Avoid technical terms.
"""


def run(state: StudyPlanState) -> StudyPlanState:
    """
    Execute Agent 4 — Workload Conflict Optimizer.

    Analyzes the schedule using the workload_analyzer tool (pure Python).
    Applies minimum-cost fixes: shifts lowest-priority unlocked tasks to
    the next day when overload is detected.

    Cost model for changes:
        - Shift 1 day   → cost 1  (lowest disruption)
        - Shift 2-6 days → cost 2  (medium disruption)
        - Shift 7+ days  → cost 3  (high disruption)
        - Locked tasks   → cost ∞  (cannot be moved)

    The LLM is invoked ONLY at the end to phrase the change log
    in natural language for the student.

    Args:
        state: Shared StudyPlanState. Reads: schedule,
               available_hours_per_day.

    Returns:
        Updated state with 'optimized_schedule', 'optimizer_log',
        and 'resolved_conflicts' populated.
    """
    print("\n[Agent 4] Workload Optimizer — starting...")

    max_hours = state.get("available_hours_per_day", 4.0)

    optimized, resolved_conflicts, optimizer_log = optimize_schedule(
        schedule=state["schedule"],
        max_daily_hours=max_hours
    )

    # LLM notification — natural language only, not logic
    log_text = "\n".join(optimizer_log)
    llm_response = call_ollama(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"The optimizer made the following changes:\n{log_text}\n\n"
            f"Write a short friendly message to the student about these changes."
        )
    )
    print(f"  → LLM notification: {llm_response[:100]}...")
    print(f"\n  Student message:\n  {llm_response}\n")

    state["optimized_schedule"] = optimized
    state["optimizer_log"] = optimizer_log
    state["resolved_conflicts"] = [c["description"] for c in resolved_conflicts]

    log_trace(
        state=state,
        agent="Workload Optimizer",
        tool="workload_analyzer.optimize_schedule",
        input_summary=f"{len(state['schedule'])} days analyzed, max {max_hours}h/day",
        output_summary=f"{len(resolved_conflicts)} conflict(s) resolved, {len(optimizer_log)} log entries"
    )

    print(f"  ✓ Optimization done. {len(resolved_conflicts)} conflict(s) resolved.")
    return state