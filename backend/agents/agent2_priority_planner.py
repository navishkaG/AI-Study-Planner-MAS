"""
agents/agent2_priority_planner.py — Agent 2: Deadline & Priority Planner

Persona:
    Academic priority advisor that ranks study tasks based on deadlines
    and difficulty, detecting scheduling conflicts before planning begins.

Responsibilities:
    - Fetch topics from SQLite via the sqlite_tool
    - Compute priority scores (deadline-aware or deadline-free formulas)
    - Detect scheduling conflicts (deadline clashes, consecutive hard tasks)
    - Explain the priority ranking to the student via LLM

LLM Role:
    Explains the computed priority order in plain English.
    Does NOT change numeric scores — tool output is authoritative.

Tool Used:
    tools/sqlite_tool.py → compute_priorities()

Student: Student 2
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import StudyPlanState
from tools.sqlite_tool import compute_priorities
from utils import call_ollama, log_trace


SYSTEM_PROMPT = """
You are an academic priority advisor. Your job is to explain the 
priority ranking produced by the scheduling tool in plain English.

CONSTRAINTS:
- Never change the numeric priority scores — those are computed by the tool.
- Only interpret and explain what the scores mean for the student.
- If conflicts are detected, describe them clearly and briefly.
- Keep your response under 150 words.
- Do not suggest study strategies — only explain the priority order.
"""


def run(state: StudyPlanState) -> StudyPlanState:
    """
    Execute Agent 2 — Deadline & Priority Planner.

    Reads topics from the database, computes priority scores using two
    formulas (with/without deadlines), detects conflicts, updates state.

    Priority formulas:
        With deadline:    priority = difficulty_score + (1 / days_remaining * 10)
        Without deadline: priority = difficulty_score + (word_count / 500)

    Args:
        state: Shared StudyPlanState. Reads: topics, deadlines.

    Returns:
        Updated state with 'priority_scores' and 'conflicts' populated.
    """
    print("\n[Agent 2] Priority Planner — starting...")

    priority_list, conflicts = compute_priorities(state.get("deadlines", []))

    # LLM explanation — only natural language, not score changes
    top3 = json.dumps(priority_list[:3], indent=2)
    conflict_info = f"{len(conflicts)} conflict(s) detected." if conflicts else "No conflicts found."
    llm_response = call_ollama(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"Top 3 priority topics: {top3}. "
            f"{conflict_info} "
            f"Please explain this priority order to a student in plain English."
        )
    )
    print(f"  → LLM: {llm_response[:100]}...")

    state["priority_scores"] = priority_list
    state["conflicts"] = conflicts

    log_trace(
        state=state,
        agent="Priority Planner",
        tool="sqlite_tool.compute_priorities",
        input_summary=f"{len(state['topics'])} topics, {len(state.get('deadlines', []))} deadlines provided",
        output_summary=f"{len(priority_list)} priorities ranked, {len(conflicts)} conflict(s) flagged"
    )

    print(f"  ✓ {len(priority_list)} topics ranked. Conflicts: {len(conflicts)}")
    return state