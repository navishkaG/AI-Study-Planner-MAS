"""
tools/ics_generator.py — Custom tool for Agent 3 (Schedule Generator).

Converts a structured day-by-day study schedule into a valid iCalendar
(.ics) file that can be imported into Google Calendar or Apple Calendar.

FIXED:
  - Task blocks now include pdf_filename and color_index so the frontend
    can render each card with the colour of its source PDF.

Author: Student 3
"""

import os
import uuid
from datetime import datetime, date, timedelta

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

DIFFICULTY_MULTIPLIERS = {"high": 1.4, "medium": 1.0, "low": 0.75}
BUFFER_RATIO  = 0.20
MAX_DAILY_HOURS  = 6.0
STUDY_START_HOUR = 9


def _date_from_str(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _build_schedule(
    priority_list: list[dict],
    available_hours: float,
    start_date: str
) -> list[dict]:
    """
    Build a day-by-day time-blocked schedule from the prioritised topic list.

    Rules applied:
        1. Highest priority tasks fill earliest available slots.
        2. High-difficulty tasks are never placed last in a day.
        3. Each day reserves a 20% buffer slot.
        4. Total daily allocation never exceeds available_hours.
        5. pdf_filename and color_index are carried through to each task block.

    Args:
        priority_list: Sorted list of PriorityDict-compatible dicts.
        available_hours: Max study hours per day.
        start_date: ISO date string for day 1.

    Returns:
        List of DayBlock-compatible dicts.
    """
    start = _date_from_str(start_date)
    usable_hours = min(available_hours, MAX_DAILY_HOURS)
    buffer = round(usable_hours * BUFFER_RATIO, 1)
    slot_hours = usable_hours - buffer

    days: list[dict] = []
    current_day = start
    remaining_slot = slot_hours
    current_tasks: list[dict] = []

    tasks = sorted(priority_list, key=lambda x: x["priority_score"], reverse=True)

    for task in tasks:
        hours_needed = round(
            task["estimated_hours"] * DIFFICULTY_MULTIPLIERS.get(task["difficulty"], 1.0),
            1
        )
        hours_needed = min(hours_needed, slot_hours)

        while hours_needed > 0:
            if remaining_slot <= 0:
                # Apply "no hard topic last" rule before closing the day.
                if (current_tasks
                        and current_tasks[-1]["difficulty"] == "high"
                        and len(current_tasks) > 1):
                    current_tasks[-1], current_tasks[-2] = current_tasks[-2], current_tasks[-1]

                days.append({
                    "day":          current_day.strftime("%A %Y-%m-%d"),
                    "date":         current_day.isoformat(),
                    "tasks":        list(current_tasks),
                    "total_hours":  round(slot_hours - remaining_slot, 1),
                    "buffer_hours": buffer
                })
                current_day += timedelta(days=1)
                remaining_slot = slot_hours
                current_tasks = []

            allocate = min(hours_needed, remaining_slot)
            current_tasks.append({
                "topic":         task["topic"],
                "duration_hours": allocate,
                "difficulty":    task["difficulty"],
                "priority_score": task["priority_score"],
                "locked":        False,
                # Colour info for the frontend card border.
                "pdf_filename":  task.get("pdf_filename", ""),
                "color_index":   task.get("color_index", 0),
            })
            remaining_slot = round(remaining_slot - allocate, 1)
            hours_needed   = round(hours_needed   - allocate, 1)

    if current_tasks:
        days.append({
            "day":          current_day.strftime("%A %Y-%m-%d"),
            "date":         current_day.isoformat(),
            "tasks":        list(current_tasks),
            "total_hours":  round(slot_hours - remaining_slot, 1),
            "buffer_hours": buffer
        })

    return days


def _format_ics_datetime(day_date: date, hour_offset: float) -> str:
    total_minutes = int(hour_offset * 60)
    h, m = divmod(total_minutes, 60)
    dt = datetime(day_date.year, day_date.month, day_date.day, h, m)
    return dt.strftime("%Y%m%dT%H%M%S")


def _write_ics(schedule: list[dict], output_path: str) -> None:
    """
    Write a schedule list to a valid .ics iCalendar file.

    Args:
        schedule: List of DayBlock-compatible dicts.
        output_path: Full path for the .ics output file.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Study Planner//MAS//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for day_block in schedule:
        day_date = _date_from_str(day_block["date"])
        current_hour = float(STUDY_START_HOUR)

        for task in day_block["tasks"]:
            start_str = _format_ics_datetime(day_date, current_hour)
            end_hour  = current_hour + task["duration_hours"]
            end_str   = _format_ics_datetime(day_date, end_hour)
            uid = str(uuid.uuid4())

            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",
                f"SUMMARY:Study: {task['topic']}",
                f"DESCRIPTION:Difficulty: {task['difficulty']} | Priority: {task['priority_score']} | Duration: {task['duration_hours']}h | Source: {task.get('pdf_filename','')}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
            current_hour = end_hour + 0.25

    lines.append("END:VCALENDAR")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))


def generate_schedule_and_ics(
    priority_list: list[dict],
    available_hours: float,
    start_date: str,
    filename: str = "study_plan.ics"
) -> tuple[list[dict], str]:
    """
    Main entry: build the study schedule and export it as an .ics file.

    Args:
        priority_list: Sorted list of PriorityDict from Agent 2.
        available_hours: User's daily study capacity in hours.
        start_date: ISO date string for the first day of the plan.
        filename: Output .ics filename (default: study_plan.ics).

    Returns:
        Tuple of (schedule_list, ics_file_path).

    Raises:
        ValueError: If priority_list is empty or available_hours <= 0.
    """
    if not priority_list:
        raise ValueError("Priority list is empty. Run Priority Planner first.")
    if available_hours <= 0:
        raise ValueError("available_hours must be greater than 0.")

    schedule    = _build_schedule(priority_list, available_hours, start_date)
    output_path = os.path.join(OUTPUT_DIR, filename)
    _write_ics(schedule, output_path)

    return schedule, os.path.abspath(output_path)