"""
tools/pdf_extractor.py — Custom tool for Agent 1 (Document Analyzer).

Extracts structured topic data from uploaded PDF lecture notes using pypdf2.
Performs text cleaning, topic detection, difficulty estimation, and
writes results to a local SQLite database.

Author: Student 1
"""

import re
import sqlite3
import os
from typing import Optional
import pypdf


# ── Difficulty keyword lists ──────────────────────────────────────────────────
HIGH_KEYWORDS = [
    "advanced", "complex", "algorithm", "theorem", "proof",
    "optimization", "derivation", "analysis", "architecture",
    "concurrent", "distributed", "cryptography", "complexity"
]
LOW_KEYWORDS = [
    "introduction", "overview", "basic", "simple", "definition",
    "what is", "getting started", "fundamentals", "summary"
]

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "study_planner.db")


def _init_db() -> None:
    """Initialize the SQLite database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            subject TEXT,
            difficulty TEXT NOT NULL,
            estimated_hours REAL NOT NULL,
            word_count INTEGER NOT NULL,
            page_range TEXT,
            priority_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("DELETE FROM topics")  # Fresh run each time
    conn.commit()
    conn.close()


def _clean_text(raw: str) -> str:
    """
    Remove PDF artifacts, page numbers, and excessive whitespace.

    Args:
        raw: Raw extracted text from a PDF page.

    Returns:
        Cleaned text string.
    """
    text = re.sub(r'\n{3,}', '\n\n', raw)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # page numbers
    text = re.sub(r'[^\x20-\x7E\n]', ' ', text)                  # non-ASCII
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _detect_topics(pages: list[str]) -> list[dict]:
    """
    Detect topic headings from cleaned page text using heading patterns.

    Patterns detected:
        - ALL CAPS lines (e.g. "NORMALIZATION")
        - Numbered headings (e.g. "1. Introduction", "3.2 SQL Joins")
        - Lines ending with a colon (e.g. "Key Concepts:")

    Args:
        pages: List of cleaned page text strings.

    Returns:
        List of dicts with keys: topic, start_page, end_page, text_content.
    """
    heading_pattern = re.compile(
        r'^(\d+[\.\d]*\s+[A-Z].{2,60}|[A-Z][A-Z\s]{4,50}|.{3,60}:)\s*$',
        re.MULTILINE
    )
    topics = []
    current_topic = None
    current_start = 1
    current_text = []

    for page_num, page_text in enumerate(pages, start=1):
        lines = page_text.split('\n')
        for line in lines:
            line = line.strip()
            if heading_pattern.match(line) and len(line) > 4:
                if current_topic:
                    topics.append({
                        "topic": current_topic,
                        "start_page": current_start,
                        "end_page": page_num,
                        "text_content": " ".join(current_text)
                    })
                current_topic = line.rstrip(':').strip()
                current_start = page_num
                current_text = []
            else:
                current_text.append(line)

    if current_topic:
        topics.append({
            "topic": current_topic,
            "start_page": current_start,
            "end_page": len(pages),
            "text_content": " ".join(current_text)
        })

    return topics if topics else [{
        "topic": "General Content",
        "start_page": 1,
        "end_page": len(pages),
        "text_content": " ".join([t for p in pages for t in p.split('\n')])
    }]


def _estimate_difficulty(text: str, word_count: int) -> str:
    """
    Estimate topic difficulty based on keyword presence and content size.

    Scoring:
        - Each HIGH keyword found: +2 points
        - Each LOW keyword found: -1 point
        - word_count > 800: +1 point
        - word_count < 200: -1 point
        - Score >= 3 → "high", Score <= 0 → "low", else "medium"

    Args:
        text: Full text content of the topic.
        word_count: Number of words in the topic.

    Returns:
        Difficulty string: "low", "medium", or "high".
    """
    lower = text.lower()
    score = 0
    for kw in HIGH_KEYWORDS:
        if kw in lower:
            score += 2
    for kw in LOW_KEYWORDS:
        if kw in lower:
            score -= 1
    if word_count > 800:
        score += 1
    elif word_count < 200:
        score -= 1

    if score >= 3:
        return "high"
    elif score < 0:
        return "low"
    return "medium"


def _estimate_hours(word_count: int, difficulty: str) -> float:
    """
    Estimate study hours based on word count and difficulty level.

    Formula: base_hours = word_count / 300
    Multipliers: high=1.5, medium=1.0, low=0.7
    Clamped between 0.5 and 8.0 hours.

    Args:
        word_count: Number of words in the topic.
        difficulty: Difficulty level string.

    Returns:
        Estimated study hours as a float.
    """
    multipliers = {"high": 1.5, "medium": 1.0, "low": 0.7}
    base = word_count / 300
    hours = base * multipliers.get(difficulty, 1.0)
    return round(max(0.5, min(8.0, hours)), 1)


def _save_topics_to_db(topics: list[dict], subject: str) -> None:
    """
    Persist extracted topics into the SQLite topics table.

    Args:
        topics: List of structured topic dicts.
        subject: Subject/course name inferred from the PDF filename.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for t in topics:
        cursor.execute("""
            INSERT INTO topics (topic, subject, difficulty, estimated_hours, word_count, page_range)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            t["topic"], subject, t["difficulty"],
            t["estimated_hours"], t["word_count"], t["page_range"]
        ))
    conn.commit()
    conn.close()


def extract_topics_from_pdf(file_path: str) -> list[dict]:
    """
    Main entry point: extract structured topic list from a PDF file.

    Reads the PDF, cleans text, detects headings, estimates difficulty
    and study hours, persists to DB, and returns a structured list.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        List of TopicDict-compatible dicts with keys:
            topic, subject, difficulty, estimated_hours, word_count, page_range.

    Raises:
        FileNotFoundError: If the PDF path does not exist.
        ValueError: If the PDF contains no extractable text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    _init_db()

    subject = os.path.splitext(os.path.basename(file_path))[0].replace("_", " ").title()

    reader = pypdf.PdfReader(file_path)
    if len(reader.pages) == 0:
        raise ValueError(f"PDF has no pages: {file_path}")

    pages = []
    for page in reader.pages:
        raw = page.extract_text() or ""
        pages.append(_clean_text(raw))

    raw_topics = _detect_topics(pages)

    structured = []
    for t in raw_topics:
        words = t["text_content"].split()
        word_count = len(words)
        difficulty = _estimate_difficulty(t["text_content"], word_count)
        hours = _estimate_hours(word_count, difficulty)
        page_range = f"{t['start_page']}-{t['end_page']}"

        structured.append({
            "topic": t["topic"],
            "subject": subject,
            "difficulty": difficulty,
            "estimated_hours": hours,
            "word_count": word_count,
            "page_range": page_range
        })

    _save_topics_to_db(structured, subject)
    return structured