"""
api.py — FastAPI REST server for the AI Study Planner MAS.

Exposes endpoints for the frontend to:
  - Upload PDF files
  - Submit deadlines and run the full pipeline
  - Stream real-time agent logs via SSE
  - Retrieve schedule, priorities, trace, and ICS file

Run:
    cd backend
    uvicorn api:app --reload --port 8000
"""

import os
import sys
import json
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))

from state import StudyPlanState
from langgraph.graph import StateGraph, END

from agents.agent1_document_analyzer import run as agent1_run
from agents.agent2_priority_planner    import run as agent2_run
from agents.agent3_schedule_generator  import run as agent3_run
from agents.agent4_workload_optimizer  import run as agent4_run

# ── Directory setup ───────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
PDFS_DIR   = BASE_DIR / "pdfs"
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR   = BASE_DIR / "data"

for d in [PDFS_DIR, OUTPUT_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── In-memory log buffer (for SSE streaming) ─────────────────────────────────
log_buffer: list[str] = []
pipeline_status: dict = {"running": False, "done": False, "error": None}
latest_state: Optional[StudyPlanState] = None

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="AI Study Planner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper: captured print → log buffer ──────────────────────────────────────
import builtins
_original_print = builtins.print

def _capturing_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    log_buffer.append(msg)
    _original_print(*args, **kwargs)


def _load_deadlines(data: list[dict]) -> list[dict]:
    today = datetime.now().date()
    for d in data:
        due = datetime.strptime(d["due_date"], "%Y-%m-%d").date()
        d["days_remaining"] = max((due - today).days, 1)
    return data


def _build_graph():
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


def _run_pipeline(pdf_paths: list[str], deadlines: list[dict],
                  available_hours: float, start_date: str):
    """Run the full 4-agent pipeline in background thread."""
    global pipeline_status, latest_state, log_buffer
    builtins.print = _capturing_print

    pipeline_status = {"running": True, "done": False, "error": None}
    log_buffer.clear()

    try:
        initial_state: StudyPlanState = {
            "pdf_paths": pdf_paths,
            "deadlines": _load_deadlines(deadlines),
            "available_hours_per_day": available_hours,
            "start_date": start_date or datetime.now().strftime("%Y-%m-%d"),
            "topics": [], "priority_scores": [], "conflicts": [],
            "schedule": [], "ics_path": "", "optimized_schedule": [],
            "optimizer_log": [], "resolved_conflicts": [], "agent_trace": []
        }

        app_graph = _build_graph()
        final_state = app_graph.invoke(initial_state)

        # Save outputs
        with open(OUTPUT_DIR / "final_schedule.json", "w") as f:
            json.dump(final_state.get("optimized_schedule") or
                      final_state.get("schedule", []), f, indent=2)
        with open(OUTPUT_DIR / "agent_trace.json", "w") as f:
            json.dump(final_state.get("agent_trace", []), f, indent=2)

        latest_state = final_state
        pipeline_status = {"running": False, "done": True, "error": None}
        log_buffer.append("✅ Pipeline complete!")

    except Exception as e:
        pipeline_status = {"running": False, "done": False, "error": str(e)}
        log_buffer.append(f"❌ Error: {e}")
    finally:
        builtins.print = _original_print


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "AI Study Planner API is running"}


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file to backend/pdfs/.
    Creates the pdfs/ directory automatically if it doesn't exist.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDFS_DIR / file.filename

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "message": "PDF uploaded successfully",
        "filename": file.filename,
        "path": str(dest),
        "size_kb": round(dest.stat().st_size / 1024, 1)
    }


@app.get("/uploaded-pdfs")
def get_uploaded_pdfs():
    """List all PDFs currently in the pdfs/ directory."""
    if not PDFS_DIR.exists():
        return {"pdfs": []}
    files = []
    for f in PDFS_DIR.glob("*.pdf"):
        files.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })
    return {"pdfs": sorted(files, key=lambda x: x["uploaded_at"], reverse=True)}


@app.delete("/uploaded-pdfs/{filename}")
def delete_pdf(filename: str):
    """Delete a specific uploaded PDF."""
    target = PDFS_DIR / filename
    if not target.exists():
        raise HTTPException(404, "File not found")
    target.unlink()
    return {"message": f"{filename} deleted"}


@app.post("/run-pipeline")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    deadlines: str = Form(default="[]"),
    available_hours: float = Form(default=4.0),
    start_date: str = Form(default=""),
    selected_pdfs: str = Form(default="[]")
):
    """
    Trigger the 4-agent pipeline.
    Uses PDFs already uploaded to pdfs/ directory.
    Runs in background so frontend can stream logs via /logs.
    """
    global pipeline_status
    if pipeline_status.get("running"):
        raise HTTPException(409, "Pipeline is already running.")

    # Parse selected PDFs
    try:
        pdf_names = json.loads(selected_pdfs)
        pdf_paths = [str(PDFS_DIR / name) for name in pdf_names]
        missing = [p for p in pdf_paths if not Path(p).exists()]
        if missing:
            raise HTTPException(400, f"PDFs not found: {missing}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid selected_pdfs JSON")

    # Parse deadlines
    try:
        deadline_list = json.loads(deadlines)
    except json.JSONDecodeError:
        deadline_list = []

    background_tasks.add_task(
        _run_pipeline, pdf_paths, deadline_list, available_hours, start_date
    )
    return {"message": "Pipeline started", "status": "running"}


@app.get("/pipeline-status")
def get_pipeline_status():
    """Return current pipeline execution status."""
    return pipeline_status


@app.get("/logs")
async def stream_logs():
    """
    Server-Sent Events endpoint — streams live agent log messages to frontend.
    """
    async def event_generator():
        sent = 0
        while True:
            while sent < len(log_buffer):
                msg = log_buffer[sent]
                yield f"data: {json.dumps({'message': msg, 'index': sent})}\n\n"
                sent += 1
            if pipeline_status.get("done") or pipeline_status.get("error"):
                yield f"data: {json.dumps({'message': '__DONE__', 'index': sent})}\n\n"
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/results/schedule")
def get_schedule():
    """Return the optimized schedule JSON."""
    path = OUTPUT_DIR / "final_schedule.json"
    if not path.exists():
        raise HTTPException(404, "No schedule yet. Run the pipeline first.")
    with open(path) as f:
        return {"schedule": json.load(f)}


@app.get("/results/priorities")
def get_priorities():
    """Return topic priority scores."""
    if not latest_state:
        raise HTTPException(404, "No results yet.")
    return {"priorities": latest_state.get("priority_scores", [])}


@app.get("/results/topics")
def get_topics():
    """Return extracted topics from Agent 1."""
    if not latest_state:
        raise HTTPException(404, "No results yet.")
    return {"topics": latest_state.get("topics", [])}


@app.get("/results/conflicts")
def get_conflicts():
    """Return detected scheduling conflicts."""
    if not latest_state:
        raise HTTPException(404, "No results yet.")
    return {
        "conflicts": latest_state.get("conflicts", []),
        "resolved": latest_state.get("resolved_conflicts", [])
    }


@app.get("/results/trace")
def get_trace():
    """Return the full agent execution trace."""
    path = OUTPUT_DIR / "agent_trace.json"
    if not path.exists():
        raise HTTPException(404, "No trace yet.")
    with open(path) as f:
        return {"trace": json.load(f)}


@app.get("/results/optimizer-log")
def get_optimizer_log():
    """Return the workload optimizer change log."""
    if not latest_state:
        raise HTTPException(404, "No results yet.")
    return {"log": latest_state.get("optimizer_log", [])}


@app.get("/results/download-ics")
def download_ics():
    """Download the generated .ics calendar file."""
    ics_path = OUTPUT_DIR / "study_plan.ics"
    if not ics_path.exists():
        raise HTTPException(404, "No ICS file yet. Run the pipeline first.")
    return FileResponse(
        path=str(ics_path),
        media_type="text/calendar",
        filename="study_plan.ics"
    )


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)