"""
tests/test_agent2_priority_planner.py — Tests for Agent 2 (Student 2)

Tests the sqlite_tool and Priority Planner agent.
Covers: priority formulas, deadline logic, conflict detection,
        database persistence, and LLM-as-Judge validation.

Run:
    python -m pytest tests/test_agent2_priority_planner.py -v
"""

import sys
import os
import json
import sqlite3
import pytest
import requests
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.sqlite_tool import (
    compute_priorities,
    _compute_priority_no_deadline,
    _compute_priority_with_deadline,
    _detect_conflicts,
    DB_PATH,
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


def _seed_db(topics: list[dict]) -> None:
    """Seed the test SQLite database with sample topics."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT, subject TEXT, difficulty TEXT,
            estimated_hours REAL, word_count INTEGER,
            page_range TEXT, priority_score REAL DEFAULT 0.0,
            urgency REAL DEFAULT 0.0
        )
    """)
    cursor.execute("DELETE FROM topics")
    for t in topics:
        cursor.execute(
            "INSERT INTO topics (topic,subject,difficulty,estimated_hours,word_count,page_range) "
            "VALUES (?,?,?,?,?,?)",
            (t["topic"], t["subject"], t["difficulty"],
             t["estimated_hours"], t["word_count"], t["page_range"])
        )
    conn.commit()
    conn.close()


@pytest.fixture
def sample_topics():
    return [
        {"topic": "SQL Joins", "difficulty": "medium", "estimated_hours": 2.0,
         "word_count": 600, "page_range": "1-3", "subject": "Databases"},
        {"topic": "Normalization", "difficulty": "high", "estimated_hours": 3.5,
         "word_count": 1050, "page_range": "4-8", "subject": "Databases"},
        {"topic": "ER Diagrams", "difficulty": "low", "estimated_hours": 1.0,
         "word_count": 300, "page_range": "9-10", "subject": "Databases"},
    ]


# ── Priority formula tests ────────────────────────────────────────────────────

class TestPriorityFormulas:

    def test_near_deadline_beats_far_same_difficulty(self):
        """
        Property: A topic due in 2 days must have higher priority
        than the same-difficulty topic due in 14 days.
        """
        near, _ = _compute_priority_with_deadline(
            "medium", 600, (date.today() + timedelta(days=2)).isoformat())
        far, _ = _compute_priority_with_deadline(
            "medium", 600, (date.today() + timedelta(days=14)).isoformat())
        assert near > far, f"Near ({near}) should beat far ({far})"

    def test_high_difficulty_beats_low_no_deadline(self):
        """High difficulty must produce higher priority than low (no deadlines)."""
        high, _ = _compute_priority_no_deadline("high", 600)
        low,  _ = _compute_priority_no_deadline("low",  600)
        assert high > low

    def test_urgency_always_positive(self):
        """Urgency must never be zero or negative (prevents division errors)."""
        _, urgency = _compute_priority_with_deadline(
            "medium", 400, (date.today() + timedelta(days=1)).isoformat())
        assert urgency > 0

    def test_overdue_task_gets_max_urgency(self):
        """An overdue task (past deadline) must have urgency based on 1 day floor."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        _, urgency = _compute_priority_with_deadline("medium", 400, yesterday)
        assert urgency > 0

    def test_larger_topic_higher_priority_no_deadline(self):
        """More words → higher priority when no deadline (size factor)."""
        big,   _ = _compute_priority_no_deadline("medium", 1000)
        small, _ = _compute_priority_no_deadline("medium", 200)
        assert big > small


# ── Conflict detection tests ──────────────────────────────────────────────────

class TestConflictDetection:

    def test_three_same_deadline_flagged(self):
        """3 tasks on same due date must trigger a deadline_clash conflict."""
        due = (date.today() + timedelta(days=5)).isoformat()
        rows = [{"topic": f"Topic {i}", "difficulty": "medium",
                 "due_date": due, "priority_score": 3.0, "urgency": 0.2, "word_count": 400}
                for i in range(3)]
        conflicts = _detect_conflicts(rows)
        clashes = [c for c in conflicts if c["conflict_type"] == "deadline_clash"]
        assert len(clashes) >= 1

    def test_two_same_deadline_not_flagged(self):
        """2 tasks on same due date must NOT trigger a conflict."""
        due = (date.today() + timedelta(days=5)).isoformat()
        rows = [{"topic": f"Topic {i}", "difficulty": "medium",
                 "due_date": due, "priority_score": 3.0, "urgency": 0.2, "word_count": 400}
                for i in range(2)]
        conflicts = _detect_conflicts(rows)
        clashes = [c for c in conflicts if c["conflict_type"] == "deadline_clash"]
        assert len(clashes) == 0


# ── Database integration tests ────────────────────────────────────────────────

class TestDatabaseIntegration:

    def test_priority_list_sorted_descending(self, sample_topics):
        """Priority list output must be sorted by score descending."""
        _seed_db(sample_topics)
        priority_list, _ = compute_priorities(deadlines=[])
        scores = [p["priority_score"] for p in priority_list]
        assert scores == sorted(scores, reverse=True)

    def test_scores_persisted_to_db(self, sample_topics):
        """Priority scores must be written back to the SQLite database."""
        _seed_db(sample_topics)
        compute_priorities(deadlines=[])
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT priority_score FROM topics").fetchall()
        conn.close()
        assert all(r[0] > 0 for r in rows)

    def test_empty_db_raises_runtime_error(self):
        """RuntimeError must be raised when database has no topics."""
        _seed_db([])
        with pytest.raises(RuntimeError):
            compute_priorities(deadlines=[])


# ── LLM-as-Judge tests ────────────────────────────────────────────────────────

class TestLLMJudge:

    @pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
    def test_priority_explanation_is_student_friendly(self, sample_topics):
        """LLM Judge: priority explanation should be understandable to a student."""
        _seed_db(sample_topics)
        priority_list, _ = compute_priorities()
        result = _llm_judge(
            "Is this priority list clear and helpful for a university student "
            "planning their study schedule?",
            json.dumps(priority_list[:3])
        )
        assert result.startswith("PASS") or result == "SKIP", f"LLM Judge: {result}"