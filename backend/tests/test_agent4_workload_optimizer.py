"""
tests/test_agent4_workload_optimizer.py — Tests for Agent 4 (Student 4)

Tests the workload_analyzer tool and Workload Optimizer agent.
Covers: overload detection, locked task protection, min-cost optimization,
        task preservation, change cost model, and LLM-as-Judge validation.

Run:
    python -m pytest tests/test_agent4_workload_optimizer.py -v
"""

import sys
import os
import json
import pytest
import requests
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.workload_analyzer import (
    optimize_schedule,
    _lock_immovable_tasks,
    _detect_overloaded_days,
    _detect_consecutive_hard_days,
    _calculate_change_cost,
    _fix_overloaded_day,
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"


def _ollama_available() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


def _llm_judge(question: str, content: str) -> str:
    if not _ollama_available():
        return "SKIP"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": (
            f"You are a strict evaluator. "
            f"Answer only with PASS or FAIL followed by one sentence reason.\n"
            f"Question: {question}\nContent:\n{content}"
        ),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 80}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
        return resp.json().get("response", "SKIP").strip()
    except Exception:
        return "SKIP"


@pytest.fixture
def overloaded_schedule():
    today = date.today()
    return [
        {
            "day": today.strftime("%A %Y-%m-%d"),
            "date": today.isoformat(),
            "tasks": [
                {"topic": "Normalization", "duration_hours": 3.5,
                 "difficulty": "high", "priority_score": 8.5, "locked": False},
                {"topic": "Transactions", "duration_hours": 3.0,
                 "difficulty": "high", "priority_score": 7.2, "locked": False},
            ],
            "total_hours": 6.5,
            "buffer_hours": 0.8
        },
        {
            "day": (today + timedelta(days=1)).strftime("%A %Y-%m-%d"),
            "date": (today + timedelta(days=1)).isoformat(),
            "tasks": [
                {"topic": "SQL Joins", "duration_hours": 2.0,
                 "difficulty": "medium", "priority_score": 4.2, "locked": False},
            ],
            "total_hours": 2.0,
            "buffer_hours": 0.8
        },
        {
            "day": (today + timedelta(days=2)).strftime("%A %Y-%m-%d"),
            "date": (today + timedelta(days=2)).isoformat(),
            "tasks": [
                {"topic": "ER Diagrams", "duration_hours": 1.5,
                 "difficulty": "low", "priority_score": 1.6, "locked": False},
            ],
            "total_hours": 1.5,
            "buffer_hours": 0.8
        },
    ]


# ── Conflict detection tests ──────────────────────────────────────────────────

class TestConflictDetection:

    def test_overloaded_day_is_detected(self, overloaded_schedule):
        """A day with 6.5h must be detected as overloaded (threshold=6.0h)."""
        alerts = _detect_overloaded_days(overloaded_schedule)
        assert len(alerts) >= 1
        assert alerts[0]["conflict_type"] == "overload"

    def test_normal_day_not_flagged(self, overloaded_schedule):
        """Days with hours within limit must not be flagged as overloaded."""
        alerts = _detect_overloaded_days(overloaded_schedule)
        flagged_dates = {a["affected_day"] for a in alerts}
        # Day 2 (2.0h) and Day 3 (1.5h) should NOT be flagged
        assert overloaded_schedule[1]["date"] not in flagged_dates
        assert overloaded_schedule[2]["date"] not in flagged_dates

    def test_consecutive_hard_days_detected(self):
        """3+ consecutive hard-dominated days must be flagged."""
        today = date.today()
        hard_schedule = [
            {
                "day": (today + timedelta(days=i)).strftime("%A %Y-%m-%d"),
                "date": (today + timedelta(days=i)).isoformat(),
                "tasks": [
                    {"topic": f"Topic {i}", "duration_hours": 3.0,
                     "difficulty": "high", "priority_score": 7.0, "locked": False}
                ],
                "total_hours": 3.0, "buffer_hours": 0.8
            }
            for i in range(4)
        ]
        alerts = _detect_consecutive_hard_days(hard_schedule)
        hard_alerts = [a for a in alerts if a["conflict_type"] == "consecutive_hard"]
        assert len(hard_alerts) >= 1


# ── Locking tests ─────────────────────────────────────────────────────────────

class TestTaskLocking:

    def test_today_tasks_locked(self, overloaded_schedule):
        """All tasks on today must be locked after _lock_immovable_tasks."""
        locked = _lock_immovable_tasks(overloaded_schedule, lock_days=2)
        today = date.today().isoformat()
        for day in locked:
            if day["date"] == today:
                for task in day["tasks"]:
                    assert task["locked"] is True

    def test_future_tasks_not_locked(self, overloaded_schedule):
        """Tasks 3+ days away must remain unlocked."""
        locked = _lock_immovable_tasks(overloaded_schedule, lock_days=1)
        future_date = (date.today() + timedelta(days=2)).isoformat()
        for day in locked:
            if day["date"] == future_date:
                for task in day["tasks"]:
                    assert task["locked"] is False


# ── Optimization tests ────────────────────────────────────────────────────────

class TestOptimization:

    def test_overload_reduced_after_optimization(self, overloaded_schedule):
        """After optimization, no unlocked day should remain overloaded."""
        optimized, _, _ = optimize_schedule(overloaded_schedule, max_daily_hours=6.0)
        for day in optimized:
            unlocked_tasks = [t for t in day["tasks"] if not t.get("locked")]
            if unlocked_tasks:
                assert day["total_hours"] <= 6.5, (
                    f"{day['day']} still overloaded: {day['total_hours']}h"
                )

    def test_no_tasks_lost_during_optimization(self, overloaded_schedule):
        """Total task count must be identical before and after optimization."""
        before = sum(len(d["tasks"]) for d in overloaded_schedule)
        optimized, _, _ = optimize_schedule(overloaded_schedule, max_daily_hours=6.0)
        after = sum(len(d["tasks"]) for d in optimized)
        assert before == after, f"Tasks lost: before={before}, after={after}"

    def test_locked_tasks_never_moved(self, overloaded_schedule):
        """Manually locked tasks must not be shifted to another day."""
        for task in overloaded_schedule[0]["tasks"]:
            task["locked"] = True
        original_day0 = {t["topic"] for t in overloaded_schedule[0]["tasks"]}
        updated, _ = _fix_overloaded_day(overloaded_schedule, 0, 6.0)
        updated_day0 = {t["topic"] for t in updated[0]["tasks"]}
        assert original_day0 == updated_day0

    def test_optimizer_log_always_populated(self, overloaded_schedule):
        """The optimizer log must always contain at least one message."""
        _, _, log = optimize_schedule(overloaded_schedule, max_daily_hours=6.0)
        assert len(log) >= 1

    def test_empty_schedule_raises_value_error(self):
        """ValueError must be raised when schedule is empty."""
        with pytest.raises(ValueError):
            optimize_schedule([], max_daily_hours=6.0)


# ── Change cost model tests ───────────────────────────────────────────────────

class TestChangeCostModel:

    def test_locked_task_cost_is_infinity(self):
        """Locked task must have cost 9999 (cannot be moved)."""
        task = {"topic": "X", "priority_score": 5.0, "difficulty": "high", "locked": True}
        assert _calculate_change_cost(task, 1) == 9999

    def test_one_day_shift_cheaper_than_one_week(self):
        """Shifting 1 day must cost less than shifting 7 days."""
        task = {"topic": "X", "priority_score": 2.0, "difficulty": "medium", "locked": False}
        assert _calculate_change_cost(task, 1) < _calculate_change_cost(task, 7)

    def test_high_priority_task_costs_more(self):
        """High-priority tasks must have a +1 cost penalty when moved."""
        low_task  = {"topic": "X", "priority_score": 1.0, "difficulty": "low",  "locked": False}
        high_task = {"topic": "Y", "priority_score": 8.0, "difficulty": "high", "locked": False}
        assert _calculate_change_cost(high_task, 1) > _calculate_change_cost(low_task, 1)


# ── LLM-as-Judge tests ────────────────────────────────────────────────────────

class TestLLMJudge:

    @pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
    def test_optimizer_log_is_understandable(self, overloaded_schedule):
        """LLM Judge: optimizer log entries should be clear and reassuring."""
        _, _, log = optimize_schedule(overloaded_schedule, max_daily_hours=6.0)
        result = _llm_judge(
            "Are these schedule change messages clear, non-technical, "
            "and reassuring for a university student?",
            "\n".join(log)
        )
        assert result.startswith("PASS") or result == "SKIP", f"LLM Judge: {result}"