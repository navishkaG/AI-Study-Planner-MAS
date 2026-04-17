"""
state.py — Shared LangGraph state schema for the AI Study Planner MAS.
All agents read from and write to this single TypedDict.
"""

from typing import TypedDict, Optional
from datetime import date


class TopicDict(TypedDict):
    topic: str
    difficulty: str          # "low" | "medium" | "high"
    estimated_hours: float
    word_count: int
    page_range: str          # e.g. "3-7"
    subject: str


class DeadlineDict(TypedDict):
    topic: str
    due_date: str            # ISO format: "YYYY-MM-DD"
    days_remaining: int


class PriorityDict(TypedDict):
    topic: str
    priority_score: float
    urgency: float
    difficulty_score: float


class ConflictAlert(TypedDict):
    conflict_type: str       # "overload" | "deadline_clash" | "consecutive_hard"
    affected_topics: list[str]
    affected_day: Optional[str]
    description: str


class TaskBlock(TypedDict):
    topic: str
    duration_hours: float
    difficulty: str
    priority_score: float
    locked: bool             # True = cannot be moved by optimizer


class DayBlock(TypedDict):
    day: str                 # "Monday 2025-04-14"
    date: str                # ISO format
    tasks: list[TaskBlock]
    total_hours: float
    buffer_hours: float


class TraceEntry(TypedDict):
    agent: str
    tool_called: str
    input_summary: str
    output_summary: str
    timestamp: str


class StudyPlanState(TypedDict):
    # Input
    pdf_paths: list[str]
    deadlines: list[DeadlineDict]
    available_hours_per_day: float
    start_date: str

    # Agent 1 output
    topics: list[TopicDict]

    # Agent 2 output
    priority_scores: list[PriorityDict]
    conflicts: list[ConflictAlert]

    # Agent 3 output
    schedule: list[DayBlock]
    ics_path: str

    # Agent 4 output
    optimized_schedule: list[DayBlock]
    optimizer_log: list[str]
    resolved_conflicts: list[str]

    # Observability
    agent_trace: list[TraceEntry]