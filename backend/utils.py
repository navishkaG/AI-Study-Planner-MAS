"""
utils.py — Shared utilities for all agents.

Provides:
    - call_ollama(): sends a prompt to the local Ollama LLM
    - log_trace(): appends an observability entry to state + log file

Used by all 4 agents. Centralizing here avoids code duplication
and ensures consistent logging format across the pipeline.
"""

import json
import os
import requests
from datetime import datetime

from state import StudyPlanState, TraceEntry

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"   # swap to "phi3" or "qwen2" if preferred
TRACE_LOG_PATH = os.path.join("output", "agent_trace.log")


def call_ollama(system_prompt: str, user_message: str) -> str:
    """
    Send a prompt to the local Ollama LLM and return the response text.

    Args:
        system_prompt: The agent's persona and constraint instructions.
        user_message: The specific task content for this invocation.

    Returns:
        LLM response string. Returns a fallback message if Ollama is
        not reachable so the pipeline continues without crashing.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"SYSTEM: {system_prompt}\n\nUSER: {user_message}",
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "[Ollama not running — start with: ollama serve]"
    except Exception as e:
        return f"[LLM error: {e}]"


def log_trace(
    state: StudyPlanState,
    agent: str,
    tool: str,
    input_summary: str,
    output_summary: str
) -> None:
    """
    Append a structured trace entry to state and to the log file.

    Each entry records which agent ran, which tool it called,
    a summary of inputs and outputs, and a timestamp.
    This satisfies the LLMOps/AgentOps observability requirement.

    Args:
        state: The shared state object to append the trace entry to.
        agent: Name of the agent (e.g. "Document Analyzer").
        tool: Name of the tool called (e.g. "pdf_extractor.extract_topics_from_pdf").
        input_summary: Short description of what was passed to the tool.
        output_summary: Short description of what the tool returned.
    """
    entry: TraceEntry = {
        "agent": agent,
        "tool_called": tool,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "timestamp": datetime.now().isoformat()
    }
    state["agent_trace"].append(entry)

    os.makedirs("output", exist_ok=True)
    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")