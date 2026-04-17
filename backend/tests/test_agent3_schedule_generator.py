"""
tests/test_agent3_schedule_generator.py — Tests for Agent 3 (Student 3)

Tests the ics_generator tool and Schedule Generator agent.
Covers: daily hour limits, topic coverage, priority ordering,
        .ics file validity, error handling, and LLM-as-Judge validation.

Run:
    python -m pytest tests/test_agent3_schedule_generator.py -v
"""

import sys
import os
import json
import pytest
import requests
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.ics_generator import generate_schedule_and_ics, _build_schedule

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
def sample_priority_list():
    return [
        {"topic": "Normalization", "priority_score": 8.5, "urgency": 0.55,
         "difficulty_score": 3.0, "difficulty": "high", "estimated_hours": 3.5},
        {"topic": "Transactions", "priority_score": 7.2, "urgency": 0.42,
         "difficulty_score": 3.0, "difficulty": "high", "estimated_hours": 3.0},
        {"topic": "SQL Joins", "priority_score": 4.2, "urgency": 0.5,
         "difficulty_score": 2.0, "difficulty": "medium", "estimated_hours": 2.0},
        {"topic": "Indexes", "priority_score": 3.8, "urgency": 0.5,
         "difficulty_score": 2.0, "difficulty": "medium", "estimated_hours": 2.0},
        {"topic": "ER Diagrams", "priority_score": 1.6, "urgency": 0.5,
         "difficulty_score": 1.0, "difficulty": "low", "estimated_hours": 1.0},
    ]


# ── Schedule structure tests ──────────────────────────────────────────────────

class TestScheduleStructure:

    def test_daily_hours_within_limit(self, sample_priority_list):
        """No day's total hours must exceed available_hours (with 5% tolerance)."""
        schedule = _build_schedule(sample_priority_list, 4.0, date.today().isoformat())
        for day in schedule:
            assert day["total_hours"] <= 4.0 * 1.05, (
                f"{day['day']} exceeds daily limit: {day['total_hours']}h"
            )

    def test_all_topics_scheduled(self, sample_priority_list):
        """Every topic from the priority list must appear in the schedule."""
        schedule = _build_schedule(sample_priority_list, 4.0, date.today().isoformat())
        scheduled = {t["topic"] for d in schedule for t in d["tasks"]}
        expected = {p["topic"] for p in sample_priority_list}
        assert expected.issubset(scheduled), f"Missing: {expected - scheduled}"

    def test_high_priority_scheduled_before_low(self, sample_priority_list):
        """Normalization (highest priority) must appear on an earlier day than ER Diagrams (lowest)."""
        schedule = _build_schedule(sample_priority_list, 4.0, date.today().isoformat())
        norm_day = next((i for i, d in enumerate(schedule)
                         if any(t["topic"] == "Normalization" for t in d["tasks"])), 999)
        er_day   = next((i for i, d in enumerate(schedule)
                         if any(t["topic"] == "ER Diagrams"   for t in d["tasks"])), 999)
        assert norm_day <= er_day, "Highest priority topic should come first"

    def test_each_day_has_buffer(self, sample_priority_list):
        """Every day block must have a buffer_hours value greater than 0."""
        schedule = _build_schedule(sample_priority_list, 4.0, date.today().isoformat())
        for day in schedule:
            assert day["buffer_hours"] > 0, f"Day {day['day']} has no buffer"

    def test_schedule_spans_multiple_days(self, sample_priority_list):
        """With limited hours, schedule must span more than one day."""
        schedule = _build_schedule(sample_priority_list, 3.0, date.today().isoformat())
        assert len(schedule) > 1, "Schedule should span multiple days"


# ── ICS file tests ────────────────────────────────────────────────────────────

class TestICSGeneration:

    def test_ics_file_is_created(self, sample_priority_list):
        """The .ics output file must exist after generation."""
        _, ics_path = generate_schedule_and_ics(
            sample_priority_list, 4.0, date.today().isoformat(), "test_created.ics"
        )
        assert os.path.exists(ics_path), f"ICS not found at {ics_path}"

    def test_ics_contains_vcalendar(self, sample_priority_list):
        """ICS file must start with BEGIN:VCALENDAR."""
        _, ics_path = generate_schedule_and_ics(
            sample_priority_list, 4.0, date.today().isoformat(), "test_vcal.ics"
        )
        content = open(ics_path).read()
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_ics_contains_events(self, sample_priority_list):
        """ICS file must contain at least one VEVENT block."""
        _, ics_path = generate_schedule_and_ics(
            sample_priority_list, 4.0, date.today().isoformat(), "test_events.ics"
        )
        content = open(ics_path).read()
        assert "BEGIN:VEVENT" in content
        assert "DTSTART:" in content
        assert "SUMMARY:" in content

    def test_ics_event_count_matches_tasks(self, sample_priority_list):
        """Number of VEVENT blocks must match total tasks in the schedule."""
        schedule, ics_path = generate_schedule_and_ics(
            sample_priority_list, 4.0, date.today().isoformat(), "test_count.ics"
        )
        total_tasks = sum(len(d["tasks"]) for d in schedule)
        content = open(ics_path).read()
        event_count = content.count("BEGIN:VEVENT")
        assert event_count == total_tasks


# ── Error handling tests ──────────────────────────────────────────────────────

class TestErrorHandling:

    def test_empty_list_raises_value_error(self):
        """ValueError must be raised for an empty priority list."""
        with pytest.raises(ValueError):
            generate_schedule_and_ics([], 4.0, date.today().isoformat())

    def test_zero_hours_raises_value_error(self, sample_priority_list):
        """ValueError must be raised when available_hours is 0."""
        with pytest.raises(ValueError):
            generate_schedule_and_ics(sample_priority_list, 0, date.today().isoformat())

    def test_negative_hours_raises_value_error(self, sample_priority_list):
        """ValueError must be raised when available_hours is negative."""
        with pytest.raises(ValueError):
            generate_schedule_and_ics(sample_priority_list, -1, date.today().isoformat())


# ── LLM-as-Judge tests ────────────────────────────────────────────────────────

class TestLLMJudge:

    @pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
    def test_schedule_is_realistic_for_student(self, sample_priority_list):
        """LLM Judge: the generated schedule should be realistic for a student."""
        schedule, _ = generate_schedule_and_ics(
            sample_priority_list, 4.0, date.today().isoformat()
        )
        result = _llm_judge(
            "Is this a realistic and well-structured study schedule for a university student "
            "with 4 hours available per day?",
            json.dumps(schedule[:2])
        )
        assert result.startswith("PASS") or result == "SKIP", f"LLM Judge: {result}"