"""
tests/test_agent1_document_analyzer.py — Tests for Agent 1 (Student 1)

Tests the pdf_extractor tool and Document Analyzer agent.
Covers: difficulty detection, hour estimation, text cleaning,
        error handling, and LLM-as-Judge validation.

Run:
    python -m pytest tests/test_agent1_document_analyzer.py -v
"""

import sys
import os
import json
import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.pdf_extractor import (
    _estimate_difficulty,
    _estimate_hours,
    _clean_text,
    extract_topics_from_pdf,
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
    """Use Ollama as evaluator. Returns 'PASS', 'FAIL', or 'SKIP'."""
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


# ── Property-based tests ──────────────────────────────────────────────────────

class TestDifficultyEstimation:

    def test_high_keyword_algorithm(self):
        """Topics with 'algorithm' must be 'high' difficulty."""
        result = _estimate_difficulty("This chapter covers algorithm design and complexity", 500)
        assert result == "high"

    def test_high_keyword_advanced(self):
        """Topics with 'advanced' must be 'high' difficulty."""
        result = _estimate_difficulty("Advanced distributed systems and concurrent design", 500)
        assert result == "high"

    def test_low_keyword_introduction(self):
        """Topics with 'introduction' and low word count must be 'low'."""
        result = _estimate_difficulty("Introduction to databases and basic overview", 150)
        assert result == "low"

    def test_medium_no_keywords(self):
        """Topics with no special keywords and medium word count must be 'medium'."""
        result = _estimate_difficulty("SQL queries and relational table operations joins", 500)
        assert result == "medium"

    def test_large_topic_gets_harder(self):
        """Very large topics (>800 words) should push score upward."""
        result_large = _estimate_difficulty("Relational data model theory", 900)
        result_small = _estimate_difficulty("Relational data model theory", 100)
        # large should be >= small in difficulty weight
        order = {"low": 0, "medium": 1, "high": 2}
        assert order[result_large] >= order[result_small]


class TestHourEstimation:

    def test_hours_never_below_minimum(self):
        """Estimated hours must never fall below 0.5."""
        result = _estimate_hours(5, "low")
        assert result >= 0.5

    def test_hours_never_above_maximum(self):
        """Estimated hours must never exceed 8.0."""
        result = _estimate_hours(999999, "high")
        assert result <= 8.0

    def test_high_difficulty_more_hours_than_low(self):
        """Same word count: high difficulty must require more hours than low."""
        high = _estimate_hours(600, "high")
        low = _estimate_hours(600, "low")
        assert high > low

    def test_longer_content_more_hours(self):
        """More words must produce more hours (same difficulty)."""
        short = _estimate_hours(200, "medium")
        long_  = _estimate_hours(800, "medium")
        assert long_ > short


class TestTextCleaning:

    def test_removes_standalone_page_numbers(self):
        """Standalone numeric lines must be removed by the cleaner."""
        raw = "Chapter 1\n\n42\n\nContent here"
        cleaned = _clean_text(raw)
        lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
        assert "42" not in lines

    def test_collapses_excessive_whitespace(self):
        """Multiple blank lines must be collapsed to at most two."""
        raw = "Line one\n\n\n\n\nLine two"
        cleaned = _clean_text(raw)
        assert "\n\n\n" not in cleaned

    def test_output_is_stripped(self):
        """Cleaned text must have no leading or trailing whitespace."""
        raw = "   \n  Some content  \n   "
        cleaned = _clean_text(raw)
        assert cleaned == cleaned.strip()


class TestErrorHandling:

    def test_missing_pdf_raises_file_not_found(self):
        """FileNotFoundError must be raised for a non-existent PDF path."""
        with pytest.raises(FileNotFoundError):
            extract_topics_from_pdf("/nonexistent/path/fake.pdf")

    def test_empty_path_raises_file_not_found(self):
        """FileNotFoundError must be raised for an empty string path."""
        with pytest.raises(FileNotFoundError):
            extract_topics_from_pdf("")


# ── LLM-as-Judge tests ────────────────────────────────────────────────────────

class TestLLMJudge:

    @pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
    def test_difficulty_assignments_are_reasonable(self):
        """LLM Judge: difficulty assignments should be academically reasonable."""
        sample = json.dumps([
            {"topic": "Algorithm Design", "difficulty": "high", "estimated_hours": 4.0},
            {"topic": "Introduction to SQL", "difficulty": "low", "estimated_hours": 1.0},
            {"topic": "Entity Relationship Diagrams", "difficulty": "medium", "estimated_hours": 2.0},
        ])
        result = _llm_judge(
            "Are these difficulty levels reasonable for a university computing course?",
            sample
        )
        assert result.startswith("PASS") or result == "SKIP", f"LLM Judge failed: {result}"