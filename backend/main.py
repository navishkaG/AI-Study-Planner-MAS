"""
main.py — LangGraph orchestrator for the AI Study Planner MAS.

Imports each agent from its own dedicated file and wires them into a
sequential LangGraph StateGraph pipeline.

Pipeline:
    Agent 1 (Document Analyzer)
        ↓
    Agent 2 (Priority Planner)
        ↓
    Agent 3 (Schedule Generator)
        ↓
    Agent 4 (Workload Optimizer)
        ↓
    END → outputs saved to /output

Usage:
    python main.py --pdf notes.pdf --hours 4
    python main.py --pdf notes.pdf --deadlines data/deadlines_example.json --hours 5 --start 2025-04-14
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from langgraph.graph import StateGraph, END
from state import StudyPlanState

# Each agent lives in its own file
from agents.agent1_document_analyzer import run as agent1_run
from agents.agent2_priority_planner import run as agent2_run
from agents.agent3_schedule_generator import run as agent3_run
from agents.agent4_workload_optimizer import run as agent4_run

os.makedirs("output", exist_ok=True)
os.makedirs("data", exist_ok=True)


def build_graph():
    """
    Build and compile the LangGraph StateGraph pipeline.

    Each agent node is a function imported from its own module.
    State flows sequentially: Agent1 → Agent2 → Agent3 → Agent4 → END.

    Returns:
        Compiled LangGraph runnable.
    """
    graph = StateGraph(StudyPlanState)

    graph.add_node("agent1_document_analyzer", agent1_run)
    graph.add_node("agent2_priority_planner",  agent2_run)
    graph.add_node("agent3_schedule_generator", agent3_run)
    graph.add_node("agent4_workload_optimizer", agent4_run)

    graph.set_entry_point("agent1_document_analyzer")
    graph.add_edge("agent1_document_analyzer", "agent2_priority_planner")
    graph.add_edge("agent2_priority_planner",  "agent3_schedule_generator")
    graph.add_edge("agent3_schedule_generator", "agent4_workload_optimizer")
    graph.add_edge("agent4_workload_optimizer", END)

    return graph.compile()


def load_deadlines(path: str) -> list[dict]:
    """
    Load deadlines from a JSON file and compute days_remaining for each.

    Expected JSON format:
        [{"topic": "SQL Joins", "due_date": "2025-04-20"}, ...]

    Args:
        path: Path to the deadlines JSON file.

    Returns:
        List of deadline dicts with days_remaining added.
        Returns empty list if file not found.
    """
    if not path or not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    today = datetime.now().date()
    for d in data:
        due = datetime.strptime(d["due_date"], "%Y-%m-%d").date()
        d["days_remaining"] = max((due - today).days, 1)
    return data


def save_outputs(state: StudyPlanState) -> None:
    """
    Save final schedule, observability trace, and summary to output files.

    Writes:
        output/final_schedule.json   — optimized day-by-day schedule
        output/agent_trace.json      — full structured trace (all 4 agents)
        output/run_summary.txt       — human-readable run summary

    Args:
        state: Final StudyPlanState after all agents have completed.
    """
    with open("output/final_schedule.json", "w") as f:
        json.dump(state.get("optimized_schedule") or state.get("schedule", []), f, indent=2)

    with open("output/agent_trace.json", "w") as f:
        json.dump(state.get("agent_trace", []), f, indent=2)

    with open("output/run_summary.txt", "w") as f:
        f.write("=" * 50 + "\n")
        f.write("  AI Study Planner — Run Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Topics extracted   : {len(state.get('topics', []))}\n")
        f.write(f"Topics prioritized : {len(state.get('priority_scores', []))}\n")
        f.write(f"Schedule days      : {len(state.get('schedule', []))}\n")
        f.write(f"ICS calendar       : {state.get('ics_path', 'N/A')}\n")
        f.write(f"Conflicts resolved : {len(state.get('resolved_conflicts', []))}\n\n")
        f.write("--- Optimizer Log ---\n")
        for line in state.get("optimizer_log", []):
            f.write(f"  {line}\n")
        f.write("\n--- Agent Trace ---\n")
        for entry in state.get("agent_trace", []):
            f.write(
                f"  [{entry['timestamp']}] {entry['agent']}\n"
                f"    Tool : {entry['tool_called']}\n"
                f"    In   : {entry['input_summary']}\n"
                f"    Out  : {entry['output_summary']}\n\n"
            )

    print("\n✓ Output files saved:")
    print(f"  output/final_schedule.json")
    print(f"  output/agent_trace.json")
    print(f"  output/run_summary.txt")
    print(f"  {state.get('ics_path', 'N/A')}")


def run(
    pdf_paths: list[str],
    deadlines_path: str = "",
    available_hours: float = 4.0,
    start_date: str = ""
) -> StudyPlanState:
    """
    Run the full 4-agent pipeline from start to finish.

    Args:
        pdf_paths: List of PDF file paths to analyze.
        deadlines_path: Optional path to a JSON deadlines file.
        available_hours: Student's daily study capacity in hours.
        start_date: ISO date string for schedule start (default: today).

    Returns:
        Final StudyPlanState after all 4 agents complete.
    """
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    # Clear previous trace log
    open("output/agent_trace.log", "w").close()

    initial_state: StudyPlanState = {
        "pdf_paths": pdf_paths,
        "deadlines": load_deadlines(deadlines_path),
        "available_hours_per_day": available_hours,
        "start_date": start_date,
        "topics": [],
        "priority_scores": [],
        "conflicts": [],
        "schedule": [],
        "ics_path": "",
        "optimized_schedule": [],
        "optimizer_log": [],
        "resolved_conflicts": [],
        "agent_trace": []
    }

    print("=" * 50)
    print("  AI Study Planner — Multi-Agent System")
    print("=" * 50)
    print(f"  PDFs        : {len(pdf_paths)} file(s)")
    print(f"  Deadlines   : {len(initial_state['deadlines'])} loaded")
    print(f"  Daily hours : {available_hours}h")
    print(f"  Start date  : {start_date}")
    print("=" * 50)

    app = build_graph()
    final_state = app.invoke(initial_state)

    save_outputs(final_state)

    print("\n" + "=" * 50)
    print("  Pipeline complete!")
    print("=" * 50)
    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Study Planner MAS")
    parser.add_argument("--pdf", nargs="+", required=True, help="PDF file path(s)")
    parser.add_argument("--deadlines", default="", help="Path to deadlines JSON file")
    parser.add_argument("--hours", type=float, default=4.0, help="Daily study hours available")
    parser.add_argument("--start", default="", help="Schedule start date YYYY-MM-DD")
    args = parser.parse_args()

    run(
        pdf_paths=args.pdf,
        deadlines_path=args.deadlines,
        available_hours=args.hours,
        start_date=args.start
    )