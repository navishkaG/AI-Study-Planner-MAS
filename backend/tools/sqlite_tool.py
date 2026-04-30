"""
tools/sqlite_tool.py — Custom tool for Agent 2 (Deadline & Priority Planner).

Reads ALL topics from SQLite (all PDFs, not just the current run),
computes priority scores using deadline-aware and deadline-free formulas,
detects conflicts, and writes results back.

FIXED:
  - Now reads all rows from the topics table regardless of pdf_filename,
    so topics from every uploaded PDF contribute to the schedule.
  - Passes pdf_filename and color_index through to priority output so
    Agent 3 / frontend can colour-code cards by source document.

Author: Student 2
"""

import sqlite3
import os
import re
from datetime import date, datetime
from typing import Optional
from difflib import SequenceMatcher

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "study_planner.db")

DIFFICULTY_SCORES = {"high": 3.0, "medium": 2.0, "low": 1.0}


def _normalize_topic_text(text: str) -> str:
    """Normalize topic text for fuzzy matching."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _topic_match_score(topic: str, candidate: str) -> float:
    """Return a similarity score for deadline/topic matching."""
    topic_key = _normalize_topic_text(topic)
    candidate_key = _normalize_topic_text(candidate)
    if not topic_key or not candidate_key:
        return 0.0
    if topic_key == candidate_key:
        return 1.0
    if topic_key in candidate_key or candidate_key in topic_key:
        return 0.9

    topic_tokens = set(topic_key.split())
    candidate_tokens = set(candidate_key.split())
    union = len(topic_tokens | candidate_tokens) or 1
    token_score = len(topic_tokens & candidate_tokens) / union
    sequence_score = SequenceMatcher(None, topic_key, candidate_key).ratio()
    return max(token_score, sequence_score)


def _find_matching_deadline(topic: str, deadlines: list[dict]) -> Optional[str]:
    """Find the best deadline for a topic using fuzzy matching."""
    best_due_date: Optional[str] = None
    best_score = 0.0
    for deadline in deadlines:
        score = _topic_match_score(topic, deadline.get("topic", ""))
        if score > best_score:
            best_score = score
            best_due_date = deadline.get("due_date")

    if best_score >= 0.6:
        return best_due_date
    return None


def _get_conn() -> sqlite3.Connection:
    """Return a sqlite3 connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_priority_columns() -> None:
    """Add priority_score and urgency columns to topics table if missing."""
    conn = _get_conn()
    cursor = conn.cursor()
    existing = [row[1] for row in cursor.execute("PRAGMA table_info(topics)")]
    for col, definition in [
        ("urgency",       "REAL DEFAULT 0.0"),
        ("pdf_filename",  "TEXT DEFAULT ''"),
        ("color_index",   "INTEGER DEFAULT 0"),
    ]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE topics ADD COLUMN {col} {definition}")
    conn.commit()
    conn.close()


def _compute_priority_no_deadline(difficulty: str, word_count: int) -> tuple[float, float]:
    """
    Compute priority score when no deadline is provided.

    Formula: priority = (difficulty_score * 1.7) + min(word_count / 700, 2.0)
    Urgency defaults to 0.45 (neutral).

    Args:
        difficulty: Topic difficulty string.
        word_count: Word count of the topic.

    Returns:
        Tuple of (priority_score, urgency).
    """
    diff_score = DIFFICULTY_SCORES.get(difficulty, 2.0)
    size_factor = min(word_count / 700, 2.0)
    priority = round((diff_score * 1.7) + size_factor, 2)
    return priority, 0.45


def _compute_priority_with_deadline(
    difficulty: str,
    word_count: int,
    due_date_str: str
) -> tuple[float, float]:
    """
    Compute priority score when a deadline exists.

    Formula:
        days_remaining = (due_date - today).days
        urgency = 1 / max(days_remaining, 1)
        priority = (difficulty_score * 1.7) + (urgency * 12) + size_factor

    Args:
        difficulty: Topic difficulty string.
        due_date_str: ISO date string "YYYY-MM-DD".

    Returns:
        Tuple of (priority_score, urgency).

    Raises:
        ValueError: If due_date_str is not a valid ISO date.
    """
    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    today = date.today()
    days_remaining = max((due_date - today).days, 1)
    urgency = round(1 / days_remaining, 4)
    diff_score = DIFFICULTY_SCORES.get(difficulty, 2.0)
    size_factor = min(word_count / 900, 1.5)
    priority = round((diff_score * 1.7) + (urgency * 12) + size_factor, 2)
    return priority, urgency


def _detect_conflicts(rows: list[dict]) -> list[dict]:
    """
    Detect scheduling conflicts across all prioritised topics.

    Conflict types detected:
        1. deadline_clash: 3+ tasks share the same due date
        2. consecutive_hard: More than 3 consecutive high-priority topics

    Args:
        rows: List of topic dicts with priority, due_date, difficulty.

    Returns:
        List of ConflictAlert-compatible dicts.
    """
    conflicts = []

    # Deadline clash detection
    deadline_groups: dict[str, list[str]] = {}
    for r in rows:
        if r.get("due_date"):
            deadline_groups.setdefault(r["due_date"], []).append(r["topic"])
    for due, topics in deadline_groups.items():
        if len(topics) >= 3:
            conflicts.append({
                "conflict_type": "deadline_clash",
                "affected_topics": topics,
                "affected_day": due,
                "description": f"{len(topics)} tasks due on {due}: {', '.join(topics)}"
            })

    # Consecutive high-difficulty detection
    high_streak = []
    for r in sorted(rows, key=lambda x: x["priority_score"], reverse=True):
        if r["difficulty"] == "high":
            high_streak.append(r["topic"])
        else:
            if len(high_streak) >= 3:
                conflicts.append({
                    "conflict_type": "consecutive_hard",
                    "affected_topics": high_streak[:],
                    "affected_day": None,
                    "description": f"{len(high_streak)} consecutive high-difficulty topics detected"
                })
            high_streak = []

    if len(high_streak) >= 3:
        conflicts.append({
            "conflict_type": "consecutive_hard",
            "affected_topics": high_streak[:],
            "affected_day": None,
            "description": f"{len(high_streak)} consecutive high-difficulty topics detected"
        })

    return conflicts


def compute_priorities(deadlines: Optional[list[dict]] = None) -> tuple[list[dict], list[dict]]:
    """
    Main entry: fetch ALL topics from the DB (every PDF), compute priority
    scores, detect conflicts, update the database, and return results.

    All PDFs' topics are included so the schedule always reflects the full
    set of uploaded documents.

    Args:
        deadlines: Optional list of DeadlineDict with keys: topic, due_date.
                   If None or empty, uses deadline-free formula for all topics.

    Returns:
        Tuple of (priority_list, conflict_list).
            priority_list: List of PriorityDict-compatible dicts.
            conflict_list: List of ConflictAlert-compatible dicts.

    Raises:
        RuntimeError: If no topics found in the database.
    """
    _ensure_priority_columns()
    conn = _get_conn()
    # Fetch ALL topics from every PDF — no filter on pdf_filename.
    rows = [dict(r) for r in conn.execute("SELECT rowid AS row_id, * FROM topics").fetchall()]
    conn.close()

    if not rows:
        raise RuntimeError("No topics found in database. Run Document Analyzer first.")

    priority_list = []
    for row in rows:
        due_date = _find_matching_deadline(row["topic"], deadlines or [])

        if due_date:
            priority, urgency = _compute_priority_with_deadline(
                row["difficulty"], row["word_count"], due_date
            )
        else:
            priority, urgency = _compute_priority_no_deadline(
                row["difficulty"], row["word_count"]
            )

        row["priority_score"] = priority
        row["urgency"] = urgency
        row["due_date"] = due_date

        priority_list.append({
            "topic":           row["topic"],
            "priority_score":  priority,
            "urgency":         urgency,
            "difficulty_score": DIFFICULTY_SCORES.get(row["difficulty"], 2.0),
            "difficulty":      row["difficulty"],
            "estimated_hours": row["estimated_hours"],
            "due_date":        due_date,
            # Pass colour info through so the schedule can colour cards.
            "pdf_filename":    row.get("pdf_filename", ""),
            "color_index":     row.get("color_index", 0),
        })

    # Persist back to DB
    conn = _get_conn()
    cursor = conn.cursor()
    for row, p in zip(rows, priority_list):
        cursor.execute(
            "UPDATE topics SET priority_score=?, urgency=? WHERE rowid=?",
            (p["priority_score"], p["urgency"], row["row_id"])
        )
    conn.commit()
    conn.close()

    priority_list.sort(key=lambda x: x["priority_score"], reverse=True)
    conflicts = _detect_conflicts(priority_list)

    return priority_list, conflicts