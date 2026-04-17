"""
agents/agent3_schedule_generator.py — Agent 3: Study Schedule Generator

Persona:
    Study schedule advisor that converts a prioritized task list into a
    realistic day-by-day time-blocked plan with a downloadable calendar file.

Responsibilities:
    - Read prioritized topics and available hours from state
    - Generate a time-blocked schedule using the ics_generator tool
    - Apply the "no hard topic last" scheduling rule
    - Export a real .ics file importable to Google/Apple Calendar
    - Present the schedule to the student via LLM

LLM Role:
    Presents the generated schedule in friendly plain language.
    Does NOT modify schedule structure — tool output is authoritative.

Tool Used:
    tools/ics_generator.py → generate_schedule_and_ics()

Student: Student 3
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import StudyPlanState
from tools.ics_generator import generate_schedule_and_ics
from utils import call_ollama, log_trace


SYSTEM_PROMPT = """
You are a study schedule advisor. Your job is to present the generated
schedule to the student clearly and concisely.

CONSTRAINTS:
- Never modify the schedule — it is produced by the ICS tool.
- Mention the .ics file path so the student knows where to find it.
- Highlight that high-difficulty topics are never scheduled last in a day.
- Keep your response under 200 words.
- Use plain, friendly language.
"""


def run(state: StudyPlanState) -> StudyPlanState:
    """
    Execute Agent 3 — Study Schedule Generator.

    Takes the prioritized task list from state and produces a day-by-day
    time-blocked schedule. Exports a real iCalendar (.ics) file.

    Scheduling rules applied by the tool:
        - Highest priority tasks fill earliest available slots
        - High-difficulty tasks are never placed last in a day
        - Each day reserves a 20% buffer slot for overruns

    Args:
        state: Shared StudyPlanState. Reads: priority_scores,
               available_hours_per_day, start_date.

    Returns:
        Updated state with 'schedule' and 'ics_path' populated.
    """
    print("\n[Agent 3] Schedule Generator — starting...")

    start_date = state.get("start_date") or datetime.now().strftime("%Y-%m-%d")
    available_hours = state.get("available_hours_per_day", 4.0)

    schedule, ics_path = generate_schedule_and_ics(
        priority_list=state["priority_scores"],
        available_hours=available_hours,
        start_date=start_date,
        filename="study_plan.ics"
    )

    # LLM presentation
    day_preview = json.dumps(schedule[:3], indent=2)
    llm_response = call_ollama(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"I generated a {len(schedule)}-day study schedule "
            f"({available_hours}h available per day). "
            f"First 3 days: {day_preview}. "
            f"Calendar saved to: {ics_path}. "
            f"Please present this to the student."
        )
    )
    print(f"  → LLM: {llm_response[:100]}...")

    state["schedule"] = schedule
    state["ics_path"] = ics_path

    log_trace(
        state=state,
        agent="Schedule Generator",
        tool="ics_generator.generate_schedule_and_ics",
        input_summary=f"{len(state['priority_scores'])} topics, {available_hours}h/day from {start_date}",
        output_summary=f"{len(schedule)}-day schedule created, .ics saved to {ics_path}"
    )

    print(f"  ✓ {len(schedule)}-day schedule generated. ICS → {ics_path}")
    return state