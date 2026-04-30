"""
tools/schedule_editor.py — Prompt-driven schedule update helper.

Takes an existing generated schedule, applies a bounded set of edits based on a
user prompt, rebalances overloaded days, and persists the updated JSON and ICS
artifacts.
"""

import copy
import json
import os
import re
from datetime import datetime, date, timedelta

from tools.ics_generator import write_schedule_to_ics

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
FINAL_SCHEDULE_PATH = os.path.join(OUTPUT_DIR, "final_schedule.json")


def _date_from_str(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _extract_dates_from_prompt(prompt: str) -> list[date]:
    """
    Extract specific dates from natural language prompt.
    Recognizes patterns like "May 2nd", "May 3rd", "2nd May", etc.
    Returns list of date objects for the current year.
    """
    dates_found = []
    
    # Pattern: "Month Day(st|nd|rd|th)" or "Day(st|nd|rd|th) Month"
    # Examples: "May 2nd", "3rd May", "December 25th"
    month_names = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    day_suffix = r"(?:\d{1,2}(?:st|nd|rd|th)?)"
    
    # Pattern 1: "Month Day" (e.g., "May 2nd")
    pattern1 = rf"\b({month_names})\s+({day_suffix})\b"
    # Pattern 2: "Day Month" (e.g., "2nd May")
    pattern2 = rf"\b({day_suffix})\s+({month_names})\b"
    
    current_year = datetime.now().year
    
    # Find all matches in pattern 1 (Month Day)
    for match in re.finditer(pattern1, prompt, re.IGNORECASE):
        month_str = match.group(1)
        day_str = re.sub(r'[a-z]+', '', match.group(2))  # Remove st/nd/rd/th suffix
        try:
            day_num = int(day_str)
            month_num = datetime.strptime(month_str, "%B").month
            parsed_date = date(current_year, month_num, day_num)
            dates_found.append(parsed_date)
        except (ValueError, AttributeError):
            pass
    
    # Find all matches in pattern 2 (Day Month)
    for match in re.finditer(pattern2, prompt, re.IGNORECASE):
        day_str = re.sub(r'[a-z]+', '', match.group(1))  # Remove st/nd/rd/th suffix
        month_str = match.group(2)
        try:
            day_num = int(day_str)
            month_num = datetime.strptime(month_str, "%B").month
            parsed_date = date(current_year, month_num, day_num)
            dates_found.append(parsed_date)
        except (ValueError, AttributeError):
            pass
    
    # Remove duplicates while preserving order
    seen = set()
    unique_dates = []
    for d in dates_found:
        if d not in seen:
            seen.add(d)
            unique_dates.append(d)
    
    return unique_dates


def _extract_recurring_days_from_prompt(prompt: str) -> list[int]:
    """
    Extract recurring day patterns from natural language prompt.
    Returns list of weekday numbers (0=Monday, 6=Sunday) to be blocked.
    
    Examples:
        "every sunday" -> [6]
        "all sundays" -> [6]
        "every saturday and sunday" -> [5, 6]
        "weekends" -> [5, 6]
        "all weekdays" -> [0, 1, 2, 3, 4]
    """
    lower = prompt.lower()
    blocked_weekdays = set()
    
    # Map day names to weekday numbers (0=Monday, 6=Sunday)
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    # Check for "every X" or "all X" or "X only" patterns
    for day_name, day_num in day_map.items():
        patterns = [
            rf"every\s+{day_name}",
            rf"all\s+{day_name}s",
            rf"{day_name}\s+only",
            rf"on\s+{day_name}s",
        ]
        if any(re.search(pattern, lower) for pattern in patterns):
            blocked_weekdays.add(day_num)
    
    # Check for "weekends" or "weekend"
    if re.search(r"\bweekends?\b", lower):
        blocked_weekdays.add(5)  # Saturday
        blocked_weekdays.add(6)  # Sunday
    
    # Check for "weekdays" or "weekday"
    if re.search(r"\bweekdays?\b", lower):
        blocked_weekdays.update([0, 1, 2, 3, 4])
    
    # Check for "every day" or "all days"
    if re.search(r"every\s+day|all\s+days", lower):
        blocked_weekdays.update(range(7))
    
    return sorted(list(blocked_weekdays))


def _get_dates_for_weekdays(schedule: list[dict], weekday_nums: list[int]) -> list[str]:
    """
    Find all ISO date strings in the schedule that fall on the specified weekdays.
    
    Args:
        schedule: The schedule list with day_blocks containing "date" fields.
        weekday_nums: List of weekday numbers (0=Monday, 6=Sunday).
    
    Returns:
        List of ISO date strings (YYYY-MM-DD) for matching days.
    """
    matching_dates = []
    for day_block in schedule:
        day_date = _date_from_str(day_block["date"])
        if day_date.weekday() in weekday_nums:
            matching_dates.append(day_block["date"])
    return matching_dates

def _recalculate_totals(schedule: list[dict]) -> None:
    for day_block in schedule:
        day_block["total_hours"] = round(
            sum(task["duration_hours"] for task in day_block.get("tasks", [])), 1
        )


def _build_day_block(reference_date: date, buffer_hours: float = 0.8) -> dict:
    return {
        "day": reference_date.strftime("%A %Y-%m-%d"),
        "date": reference_date.isoformat(),
        "tasks": [],
        "total_hours": 0.0,
        "buffer_hours": buffer_hours,
    }


def _schedule_topics(schedule: list[dict]) -> list[str]:
    topics = []
    for day_block in schedule:
        for task in day_block.get("tasks", []):
            topic = task.get("topic", "")
            if topic and topic not in topics:
                topics.append(topic)
    return topics


def _topic_similarity(a: str, b: str) -> float:
    a_key = _normalize_text(a)
    b_key = _normalize_text(b)
    if not a_key or not b_key:
        return 0.0
    if a_key == b_key:
        return 1.0
    if a_key in b_key or b_key in a_key:
        return 0.9
    a_tokens = set(a_key.split())
    b_tokens = set(b_key.split())
    union = len(a_tokens | b_tokens) or 1
    return len(a_tokens & b_tokens) / union


def _match_topics(prompt: str, schedule: list[dict], limit: int = 3) -> list[str]:
    prompt_key = _normalize_text(prompt)
    topics = _schedule_topics(schedule)
    scored = sorted(
        ((topic, _topic_similarity(prompt_key, topic)) for topic in topics),
        key=lambda item: item[1],
        reverse=True,
    )
    return [topic for topic, score in scored if score >= 0.25][:limit]


def _find_task_location(schedule: list[dict], topic: str) -> tuple[int, int] | None:
    best = None
    best_score = 0.0
    for day_index, day_block in enumerate(schedule):
        for task_index, task in enumerate(day_block.get("tasks", [])):
            score = _topic_similarity(topic, task.get("topic", ""))
            if score > best_score:
                best_score = score
                best = (day_index, task_index)
    if best_score >= 0.4:
        return best
    return None


def _ensure_day_index(schedule: list[dict], index: int) -> int:
    while index >= len(schedule):
        last_date = _date_from_str(schedule[-1]["date"])
        new_day = _build_day_block(last_date + timedelta(days=1), schedule[-1]["buffer_hours"])
        schedule.append(new_day)
    return index


def _move_task(schedule: list[dict], topic: str, direction: str, days: int = 1) -> bool:
    location = _find_task_location(schedule, topic)
    if location is None:
        return False

    source_index, task_index = location
    target_index = source_index - days if direction == "earlier" else source_index + days

    if target_index < 0:
        insert_count = abs(target_index)
        for _ in range(insert_count):
            first_date = _date_from_str(schedule[0]["date"])
            new_day = _build_day_block(first_date - timedelta(days=1), schedule[0]["buffer_hours"])
            schedule.insert(0, new_day)
        source_index += insert_count
        target_index = 0
    else:
        target_index = _ensure_day_index(schedule, target_index)

    source_day = schedule[source_index]
    target_day = schedule[target_index]

    task = source_day["tasks"].pop(task_index)
    target_day["tasks"].append(task)
    _recalculate_totals([source_day, target_day])
    return True


def _swap_topics(schedule: list[dict], topic_a: str, topic_b: str) -> bool:
    loc_a = _find_task_location(schedule, topic_a)
    loc_b = _find_task_location(schedule, topic_b)
    if loc_a is None or loc_b is None:
        return False

    day_a, task_a = loc_a
    day_b, task_b = loc_b
    schedule[day_a]["tasks"][task_a], schedule[day_b]["tasks"][task_b] = (
        schedule[day_b]["tasks"][task_b],
        schedule[day_a]["tasks"][task_a],
    )
    _recalculate_totals([schedule[day_a], schedule[day_b]])
    return True


def _lighten_weekends(schedule: list[dict]) -> bool:
    moved = False
    for day_index, day_block in enumerate(list(schedule)):
        weekday = _date_from_str(day_block["date"]).weekday()
        if weekday not in {5, 6} or not day_block.get("tasks"):
            continue

        task = min(day_block["tasks"], key=lambda item: item.get("priority_score", 0.0))
        target_index = day_index + 1 if day_index + 1 < len(schedule) else day_index - 1
        if target_index < 0:
            continue

        day_block["tasks"].remove(task)
        schedule[target_index]["tasks"].append(task)
        _recalculate_totals([day_block, schedule[target_index]])
        moved = True

    return moved


def _rebalance_overloaded_days(schedule: list[dict], max_daily_hours: float) -> bool:
    changed = False
    guard = max(len(schedule) * 3, 1)

    while guard > 0:
        overloaded = [
            (index, day)
            for index, day in enumerate(schedule)
            if day.get("total_hours", 0.0) > max_daily_hours
        ]
        if not overloaded:
            break

        day_index, day_block = max(overloaded, key=lambda item: item[1].get("total_hours", 0.0))
        movable = [task for task in day_block.get("tasks", []) if not task.get("locked", False)]
        if not movable:
            break

        task = min(movable, key=lambda item: item.get("priority_score", 0.0))
        target_index = _ensure_day_index(schedule, day_index + 1)
        day_block["tasks"].remove(task)
        schedule[target_index]["tasks"].append(task)
        _recalculate_totals([day_block, schedule[target_index]])
        changed = True
        guard -= 1

    return changed


def _skip_date_tasks(schedule: list[dict], date_strs: list[str]) -> bool:
    """
    Move all tasks off the specified dates to other days.
    
    Args:
        schedule: The schedule list to modify.
        date_strs: List of ISO date strings (YYYY-MM-DD) to clear.
    
    Returns:
        True if any tasks were moved.
    """
    blocked_dates = {date_str for date_str in date_strs}
    moved = False
    
    for day_index, day_block in enumerate(list(schedule)):
        if day_block["date"] not in blocked_dates:
            continue
        
        # Move all tasks off this blocked date
        tasks_to_move = list(day_block.get("tasks", []))
        for task in tasks_to_move:
            # Find the next non-blocked day (prefer one day after)
            target_index = day_index + 1
            target_index = _ensure_day_index(schedule, target_index)
            
            # Keep searching if that day is also blocked
            while target_index < len(schedule) and schedule[target_index]["date"] in blocked_dates:
                target_index += 1
            target_index = _ensure_day_index(schedule, target_index)
            
            day_block["tasks"].remove(task)
            schedule[target_index]["tasks"].append(task)
            moved = True
    
            _recalculate_totals([day_block, schedule[target_index]])
    return moved


def _parse_actions(prompt: str, schedule: list[dict]) -> list[dict]:
    lower = prompt.lower()
    actions: list[dict] = []
    matched_topics = _match_topics(prompt, schedule)

    # Check for recurring day patterns first (e.g., "every sunday", "all weekends")
    recurring_weekdays = _extract_recurring_days_from_prompt(prompt)
    if recurring_weekdays:
        recurring_dates = _get_dates_for_weekdays(schedule, recurring_weekdays)
        if recurring_dates:
            actions.append({"type": "skip_recurring_days", "dates": recurring_dates})
    # Only use lighten_weekends if no specific recurring pattern was detected
    elif any(keyword in lower for keyword in ["weekend", "saturday", "sunday"]):
        actions.append({"type": "lighten_weekends"})

    # Check for specific date constraints (e.g., "May 2nd and May 3rd")
    blocked_dates = _extract_dates_from_prompt(prompt)
    if blocked_dates:
        actions.append({"type": "skip_dates", "dates": [d.isoformat() for d in blocked_dates]})

    if any(keyword in lower for keyword in ["rebalance", "less busy", "lighter", "spread out", "balance", "improve"]):
        actions.append({"type": "rebalance"})

    direction = None
    if any(keyword in lower for keyword in ["earlier", "sooner", "advance", "bring forward"]):
        direction = "earlier"
    elif any(keyword in lower for keyword in ["later", "postpone", "delay", "push back"]):
        direction = "later"

    if direction and matched_topics:
        for topic in matched_topics:
            actions.append({"type": "move_topic", "topic": topic, "direction": direction, "days": 1})

    if "swap" in lower and len(matched_topics) >= 2:
        actions.append({"type": "swap_topics", "topic_a": matched_topics[0], "topic_b": matched_topics[1]})

    return actions


def _apply_actions(schedule: list[dict], actions: list[dict]) -> list[str]:
    notes: list[str] = []
    for action in actions:
        action_type = action.get("type")
        if action_type == "move_topic":
            topic = action.get("topic", "")
            direction = action.get("direction", "earlier")
            days = int(action.get("days", 1))
            if _move_task(schedule, topic, direction, days):
                notes.append(f"Moved {topic} {direction} by {days} day(s).")
        elif action_type == "lighten_weekends":
            if _lighten_weekends(schedule):
                notes.append("Shifted work away from the weekend.")
        elif action_type == "rebalance":
            notes.append("Marked for rebalancing.")
        elif action_type == "swap_topics":
            topic_a = action.get("topic_a", "")
            topic_b = action.get("topic_b", "")
            if _swap_topics(schedule, topic_a, topic_b):
                notes.append(f"Swapped {topic_a} with {topic_b}.")

        elif action_type == "skip_dates":
            date_strs = action.get("dates", [])
            if date_strs and _skip_date_tasks(schedule, date_strs):
                formatted_dates = ", ".join(date_strs)
                notes.append(f"Moved all tasks away from {formatted_dates}.")

        elif action_type == "skip_recurring_days":
            date_strs = action.get("dates", [])
            if date_strs and _skip_date_tasks(schedule, date_strs):
                notes.append(f"Moved all work away from those days to maintain the schedule.")

    return notes


def _write_schedule_json(schedule: list[dict]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(FINAL_SCHEDULE_PATH, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)


def apply_schedule_change(
    schedule: list[dict],
    prompt: str,
    available_hours: float,
    optimize: bool = True,
) -> dict:
    """
    Apply a user prompt to an existing schedule and persist the result.

    Returns a dictionary with the updated schedule, summary text, change log,
    and the generated ICS path.
    """
    if not schedule:
        raise ValueError("Schedule is empty.")
    if not prompt.strip():
        raise ValueError("Prompt is empty.")

    updated = copy.deepcopy(schedule)
    actions = _parse_actions(prompt, updated)
    action_notes = _apply_actions(updated, actions)

    if any(action.get("type") == "rebalance" for action in actions) or optimize:
        _rebalance_overloaded_days(updated, available_hours)

    _recalculate_totals(updated)
    _write_schedule_json(updated)
    ics_path = write_schedule_to_ics(updated)

    summary = "; ".join(action_notes) if action_notes else "Applied the requested schedule update."
    return {
        "schedule": updated,
        "summary": summary,
        "actions": actions,
        "log": action_notes,
        "ics_path": ics_path,
    }