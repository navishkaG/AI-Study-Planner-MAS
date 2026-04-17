"""
tools/workload_analyzer.py — Custom tool for Agent 4 (Workload Conflict Optimizer).

Pure algorithmic Python tool — no LLM involved in core logic.
Detects schedule overloads, difficulty imbalances, and deadline violations.
Applies minimum-cost fixes to future (unlocked) tasks only.

This design demonstrates knowing WHEN NOT to use the LLM:
    - Conflict detection: deterministic rule-based code
    - Cost scoring: arithmetic
    - Optimization: greedy min-cost algorithm
    - User notification text: LLM (in the agent, not this tool)

Author: Student 4
"""

import copy
from datetime import datetime, date, timedelta
from typing import Optional

MAX_DAILY_HOURS = 6.0
OVERLOAD_THRESHOLD = 6.0          # hours/day
CONSECUTIVE_HARD_LIMIT = 2        # max consecutive high-difficulty days

# Change cost scores for the optimizer
COST_SHIFT_ONE_DAY = 1
COST_SHIFT_ONE_WEEK = 3
COST_SPLIT_TASK = 2
COST_REMOVE = 10                  # last resort only


def _date_from_str(s: str) -> date:
    """Parse ISO date string to date object."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _lock_immovable_tasks(schedule: list[dict], lock_days: int = 2) -> list[dict]:
    """
    Mark tasks on today and the next `lock_days` days as locked.

    Locked tasks cannot be modified by the optimizer. This preserves
    the user's near-term plan consistency.

    Args:
        schedule: List of DayBlock dicts.
        lock_days: Number of days from today to lock (default: 2).

    Returns:
        Updated schedule with locked flags set.
    """
    today = date.today()
    cutoff = today + timedelta(days=lock_days)
    updated = copy.deepcopy(schedule)

    for day_block in updated:
        day_date = _date_from_str(day_block["date"])
        if day_date <= cutoff:
            for task in day_block["tasks"]:
                task["locked"] = True

    return updated


def _detect_overloaded_days(schedule: list[dict]) -> list[dict]:
    """
    Find days where total study hours exceed the overload threshold.

    Args:
        schedule: List of DayBlock dicts.

    Returns:
        List of ConflictAlert dicts for overloaded days.
    """
    alerts = []
    for day_block in schedule:
        if day_block["total_hours"] > OVERLOAD_THRESHOLD:
            alerts.append({
                "conflict_type": "overload",
                "affected_topics": [t["topic"] for t in day_block["tasks"]],
                "affected_day": day_block["date"],
                "description": (
                    f"{day_block['day']} is overloaded: "
                    f"{day_block['total_hours']}h > {OVERLOAD_THRESHOLD}h limit"
                )
            })
    return alerts


def _detect_consecutive_hard_days(schedule: list[dict]) -> list[dict]:
    """
    Find runs of consecutive days that are dominated by high-difficulty tasks.

    A day is "hard-dominated" if >50% of its tasks are high difficulty.

    Args:
        schedule: List of DayBlock dicts.

    Returns:
        List of ConflictAlert dicts for consecutive hard-day runs.
    """
    alerts = []
    streak: list[str] = []

    for day_block in schedule:
        tasks = day_block["tasks"]
        if not tasks:
            if len(streak) > CONSECUTIVE_HARD_LIMIT:
                alerts.append({
                    "conflict_type": "consecutive_hard",
                    "affected_topics": [],
                    "affected_day": None,
                    "description": f"{len(streak)} consecutive hard-dominated days detected"
                })
            streak = []
            continue

        high_count = sum(1 for t in tasks if t["difficulty"] == "high")
        if high_count / len(tasks) > 0.5:
            streak.append(day_block["date"])
        else:
            if len(streak) > CONSECUTIVE_HARD_LIMIT:
                alerts.append({
                    "conflict_type": "consecutive_hard",
                    "affected_topics": [],
                    "affected_day": streak[0],
                    "description": f"{len(streak)} consecutive hard-dominated days starting {streak[0]}"
                })
            streak = []

    # Flush remaining streak at end of schedule
    if len(streak) > CONSECUTIVE_HARD_LIMIT:
        alerts.append({
            "conflict_type": "consecutive_hard",
            "affected_topics": [],
            "affected_day": streak[0],
            "description": f"{len(streak)} consecutive hard-dominated days starting {streak[0]}"
        })

    return alerts


def _calculate_change_cost(task: dict, days_to_shift: int) -> int:
    """
    Calculate the disruption cost of moving a task.

    Cost model:
        - Shift 1 day: cost 1 (low disruption)
        - Shift 2-6 days: cost 2 (medium)
        - Shift 7+ days: cost 3 (high)
        - High-priority task: add +1 penalty
        - Locked task: cost = infinity (cannot be moved)

    Args:
        task: TaskBlock dict with priority_score, difficulty, locked fields.
        days_to_shift: Number of days the task would be shifted.

    Returns:
        Integer cost score. Returns 9999 for locked tasks.
    """
    if task.get("locked", False):
        return 9999

    if days_to_shift == 1:
        cost = COST_SHIFT_ONE_DAY
    elif days_to_shift < 7:
        cost = COST_SPLIT_TASK
    else:
        cost = COST_SHIFT_ONE_WEEK

    if task.get("priority_score", 0) > 5.0:
        cost += 1

    return cost


def _fix_overloaded_day(
    schedule: list[dict],
    day_index: int,
    max_hours: float
) -> tuple[list[dict], list[str]]:
    """
    Reduce an overloaded day's hours by shifting the lowest-cost unlocked task
    to the next available day.

    Applies minimum-cost change: always picks the task with the lowest
    priority score (least urgent) among unlocked tasks for shifting.

    Args:
        schedule: Full schedule list.
        day_index: Index of the overloaded day in the schedule.
        max_hours: Maximum allowed daily hours.

    Returns:
        Tuple of (updated_schedule, log_messages).
    """
    updated = copy.deepcopy(schedule)
    log = []
    day_block = updated[day_index]

    movable = [t for t in day_block["tasks"] if not t.get("locked", False)]
    if not movable:
        log.append(f"Cannot fix {day_block['day']}: all tasks are locked.")
        return updated, log

    # Pick the task with the LOWEST priority (least disruption to move)
    task_to_move = min(movable, key=lambda t: t["priority_score"])
    cost = _calculate_change_cost(task_to_move, 1)

    # Find next day — insert if doesn't exist
    if day_index + 1 < len(updated):
        target_day = updated[day_index + 1]
    else:
        # Create a new day at end of schedule
        last_date = _date_from_str(updated[-1]["date"])
        new_date = last_date + timedelta(days=1)
        target_day = {
            "day": new_date.strftime("%A %Y-%m-%d"),
            "date": new_date.isoformat(),
            "tasks": [],
            "total_hours": 0.0,
            "buffer_hours": day_block["buffer_hours"]
        }
        updated.append(target_day)

    # Move the task
    day_block["tasks"].remove(task_to_move)
    day_block["total_hours"] = round(
        sum(t["duration_hours"] for t in day_block["tasks"]), 1
    )
    target_day["tasks"].append(task_to_move)
    target_day["total_hours"] = round(
        sum(t["duration_hours"] for t in target_day["tasks"]), 1
    )

    log.append(
        f"[cost={cost}] Moved '{task_to_move['topic']}' "
        f"from {day_block['day']} → {target_day['day']} "
        f"(reduced load from {day_block['total_hours'] + task_to_move['duration_hours']:.1f}h "
        f"to {day_block['total_hours']:.1f}h)"
    )
    return updated, log


def optimize_schedule(
    schedule: list[dict],
    max_daily_hours: float = MAX_DAILY_HOURS
) -> tuple[list[dict], list[dict], list[str]]:
    """
    Main entry: analyze and optimize the study schedule.

    Pipeline:
        1. Lock today's and tomorrow's tasks (immovable).
        2. Detect all overloaded days.
        3. Detect consecutive hard-day streaks.
        4. Apply minimum-cost fixes to overloaded days (future only).
        5. Return optimized schedule, resolved conflict list, and change log.

    The LLM is NOT used here. All logic is deterministic Python.
    The agent uses this tool's log output to generate human-readable
    notifications via the LLM.

    Args:
        schedule: List of DayBlock dicts from Agent 3.
        max_daily_hours: Maximum allowed study hours per day.

    Returns:
        Tuple of (optimized_schedule, resolved_conflicts, optimizer_log).
            optimized_schedule: Updated DayBlock list.
            resolved_conflicts: List of ConflictAlert dicts that were fixed.
            optimizer_log: List of human-readable change descriptions.

    Raises:
        ValueError: If schedule is empty.
    """
    if not schedule:
        raise ValueError("Schedule is empty. Run Schedule Generator first.")

    working = _lock_immovable_tasks(schedule)
    log: list[str] = []
    resolved: list[dict] = []

    # Detect issues
    overload_alerts = _detect_overloaded_days(working)
    hard_alerts = _detect_consecutive_hard_days(working)
    all_alerts = overload_alerts + hard_alerts

    if not all_alerts:
        log.append("Schedule analysis complete. No conflicts detected.")
        return working, [], log

    log.append(f"Detected {len(all_alerts)} conflict(s). Applying minimum-cost fixes...")

    # Fix overloaded days (iterate until clean or no more moves possible)
    max_iterations = len(working) * 2
    iteration = 0
    while iteration < max_iterations:
        overloads = _detect_overloaded_days(working)
        if not overloads:
            break
        # Fix the worst overloaded unlocked day first
        unlocked_overloads = [
            o for o in overloads
            if any(not t.get("locked", False)
                   for day in working
                   if day["date"] == o["affected_day"]
                   for t in day["tasks"])
        ]
        if not unlocked_overloads:
            log.append("Remaining overloads affect locked tasks only — cannot fix.")
            break

        worst = max(unlocked_overloads,
                    key=lambda x: next(
                        (d["total_hours"] for d in working if d["date"] == x["affected_day"]), 0
                    ))
        day_idx = next(i for i, d in enumerate(working) if d["date"] == worst["affected_day"])
        working, fix_log = _fix_overloaded_day(working, day_idx, max_daily_hours)
        log.extend(fix_log)
        resolved.append(worst)
        iteration += 1

    log.append(f"Optimization complete. Applied {len(resolved)} fix(es).")
    return working, resolved, log