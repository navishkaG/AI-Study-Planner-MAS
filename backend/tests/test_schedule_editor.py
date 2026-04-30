"""
Tests for the prompt-driven schedule editor.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.schedule_editor import apply_schedule_change


def _make_day(day_date, tasks):
    return {
        "day": day_date.strftime("%A %Y-%m-%d"),
        "date": day_date.isoformat(),
        "tasks": tasks,
        "total_hours": round(sum(task["duration_hours"] for task in tasks), 1),
        "buffer_hours": 0.8,
    }


def _sample_schedule():
    start = date.today() + timedelta(days=3)
    return [
        _make_day(start, [
            {"topic": "Normalization", "duration_hours": 2.0, "difficulty": "high", "priority_score": 8.5, "locked": False},
        ]),
        _make_day(start + timedelta(days=1), [
            {"topic": "SQL Joins", "duration_hours": 2.0, "difficulty": "medium", "priority_score": 4.2, "locked": False},
        ]),
        _make_day(start + timedelta(days=2), [
            {"topic": "ER Diagrams", "duration_hours": 3.5, "difficulty": "low", "priority_score": 1.6, "locked": False},
            {"topic": "Transactions", "duration_hours": 2.5, "difficulty": "high", "priority_score": 7.1, "locked": False},
        ]),
    ]


def test_move_topic_earlier():
    schedule = _sample_schedule()
    result = apply_schedule_change(schedule, "Move SQL Joins earlier", 4.0, optimize=False)
    moved_topic_days = [day["date"] for day in result["schedule"] if any(task["topic"] == "SQL Joins" for task in day["tasks"])]
    assert moved_topic_days[0] == schedule[0]["date"]


def test_rebalance_reduces_heavy_day():
    schedule = _sample_schedule()
    result = apply_schedule_change(schedule, "Rebalance this schedule and make it less busy", 3.5, optimize=True)
    totals = [day["total_hours"] for day in result["schedule"]]
    assert max(totals) <= 3.5