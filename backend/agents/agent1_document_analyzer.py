"""
agents/agent1_document_analyzer.py — Agent 1: Document Analyzer

Persona:
    Academic document analyst that converts raw PDF lecture notes
    into a clean structured topic list stored in SQLite.

Responsibilities:
    - Read uploaded PDF files using the pdf_extractor tool
    - Validate and summarize extracted topics via LLM
    - Write structured topics into shared state

LLM Role:
    Validates difficulty assignments and summarizes what was extracted.
    Does NOT invent or modify topics — tool output is authoritative.

Tool Used:
    tools/pdf_extractor.py → extract_topics_from_pdf()

Student: Student 1
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import StudyPlanState
from tools.pdf_extractor import extract_topics_from_pdf
from utils import call_ollama, log_trace


SYSTEM_PROMPT = """
You are an academic document analyst. Your ONLY job is to summarize 
the topics extracted from a PDF and confirm difficulty assignments.

CONSTRAINTS:
- Never invent topics. Only summarize what the tool extracted.
- If difficulty seems wrong for a topic, briefly explain why.
- Do NOT add new topics or remove existing ones.
- Be concise — 2 to 3 sentences maximum.
- Do not repeat the full topic list verbatim.
"""


def run(state: StudyPlanState) -> StudyPlanState:
    """
    Execute Agent 1 — Document Analyzer.

    Reads all PDF paths from state, extracts structured topics using the
    pdf_extractor tool, validates results with the LLM, and updates state.

    Args:
        state: Shared StudyPlanState. Reads: pdf_paths.

    Returns:
        Updated state with 'topics' populated.
    """
    print("\n[Agent 1] Document Analyzer — starting...")

    all_topics = []
    for pdf_path in state["pdf_paths"]:
        print(f"  → Extracting: {pdf_path}")
        topics = extract_topics_from_pdf(pdf_path)
        all_topics.extend(topics)

    # LLM validation — summarize and flag any concerns
    sample = json.dumps(all_topics[:5], indent=2)
    llm_response = call_ollama(
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"I extracted {len(all_topics)} topics from "
            f"{len(state['pdf_paths'])} PDF(s). "
            f"First few topics: {sample}. "
            f"Please confirm this looks reasonable and flag any difficulty concerns."
        )
    )
    print(f"  → LLM: {llm_response[:100]}...")

    state["topics"] = all_topics

    log_trace(
        state=state,
        agent="Document Analyzer",
        tool="pdf_extractor.extract_topics_from_pdf",
        input_summary=f"{len(state['pdf_paths'])} PDF file(s)",
        output_summary=f"Extracted {len(all_topics)} topics into SQLite"
    )

    print(f"  ✓ {len(all_topics)} topics extracted and stored.")
    return state