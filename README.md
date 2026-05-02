# AI Study Planner — Multi-Agent System
**SE4010 CTSE Assignment 2 | Group Project**

---

## Folder Structure

```
.
├── backend/                          # Python LangGraph backend
│   ├── api.py                        # FastAPI entrypoint for the dashboard
│   ├── main.py                       # LangGraph orchestrator
│   ├── requirements.txt              # Python dependencies
│   ├── state.py                      # Shared `StudyPlanState` TypedDict
│   ├── utils.py                      # Shared Ollama caller + trace logger
│   ├── agents/                       # One file per agent (one per student)
│   │   ├── __init__.py
│   │   ├── agent1_document_analyzer.py
│   │   ├── agent2_priority_planner.py
│   │   ├── agent3_schedule_generator.py
│   │   └── agent4_workload_optimizer.py
│   ├── tools/                        # Agent tools plus backend schedule editor
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py
│   │   ├── sqlite_tool.py
│   │   ├── ics_generator.py
│   │   ├── workload_analyzer.py
│   │   └── schedule_editor.py
│   ├── tests/                        # One test file per agent
│   │   ├── __init__.py
│   │   ├── test_agent1_document_analyzer.py
│   │   ├── test_agent2_priority_planner.py
│   │   ├── test_agent3_schedule_generator.py
│   │   └── test_agent4_workload_optimizer.py
│   ├── data/                         # Input data and deadlines
│   │   ├── study_planner.db
│   │   └── deadlines_example.json
│   └── output/                       # Generated output files
│       ├── study_plan.ics
│       ├── final_schedule.json
│       ├── agent_trace.json
│       ├── agent_trace.log
│       └── run_summary.txt
├── frontend/                         # React + Vite dashboard
│   ├── package.json
│   ├── public/
│   ├── src/
│   ├── index.html
│   └── vite.config.js
└── README.md
```

---
## Student Ownership

| Student | Agent File | Tool File | Test File |
|---------|-----------|-----------|-----------|
| Student 1 | agents/agent1_document_analyzer.py | tools/pdf_extractor.py | tests/test_agent1_document_analyzer.py |
| Student 2 | agents/agent2_priority_planner.py | tools/sqlite_tool.py | tests/test_agent2_priority_planner.py |
| Student 3 | agents/agent3_schedule_generator.py | tools/ics_generator.py | tests/test_agent3_schedule_generator.py |
| Student 4 | agents/agent4_workload_optimizer.py | tools/workload_analyzer.py | tests/test_agent4_workload_optimizer.py |

---

## Setup

### 1. Install Ollama
bash
# Download from https://ollama.com
ollama pull llama3.2:3b
ollama serve


### 2. Install Python dependencies
bash
cd backend
pip install -r requirements.txt


### 3. Install frontend dependencies
bash
cd frontend
npm install


---

## Running the System

### Start the backend API
bash
cd backend
uvicorn api:app --reload --port 8000


### Start the frontend dashboard
bash
cd frontend
npm run dev


### Full backend run with deadlines
bash
cd backend
python main.py \
  --pdf pdfs/databases.pdf pdfs/os.pdf \
  --deadlines data/deadlines_example.json \
  --hours 5 \
  --start 2025-04-14


### Deadlines JSON format
json
[
  {"topic": "SQL Joins", "due_date": "2025-04-20"},
  {"topic": "Normalization", "due_date": "2025-04-18"}
]


---

## Running Tests

bash
# All tests
python -m pytest tests/ -v

# Individual student tests
python -m pytest tests/test_agent1_document_analyzer.py -v
python -m pytest tests/test_agent2_priority_planner.py -v
python -m pytest tests/test_agent3_schedule_generator.py -v
python -m pytest tests/test_agent4_workload_optimizer.py -v


---

## System Flow


PDF files + deadlines
        ↓
[Agent 1] Document Analyzer
  Tool: pdf_extractor.py
  → Extracts topics, difficulty, hours from PDF
  → Writes to SQLite database
        ↓  (state: topics)
[Agent 2] Priority Planner
  Tool: sqlite_tool.py
  → Computes priority scores (with/without deadlines)
  → Detects scheduling conflicts
        ↓  (state: priority_scores, conflicts)
[Agent 3] Schedule Generator
  Tool: ics_generator.py
  → Builds time-blocked day-by-day schedule
  → Exports importable .ics calendar file
        ↓  (state: schedule, ics_path)
[Agent 4] Workload Optimizer
  Tool: workload_analyzer.py (pure Python — no LLM)
  → Detects overloads, hard-day streaks
  → Applies minimum-cost fixes to future tasks
  → LLM writes friendly notification only
        ↓
output/final_schedule.json
output/study_plan.ics
output/agent_trace.json


---

## Technical Constraints Met
- ✅ Local LLM via Ollama (llama3:8b) — zero cloud cost, no paid APIs
- ✅ LangGraph StateGraph orchestration
- ✅ 4 distinct agents, each in its own file
- ✅ 5 custom Python tools with strict type hints and docstrings
- ✅ Shared StudyPlanState TypedDict passed through all agents
- ✅ Structured JSON trace logging (AgentOps-style observability)
- ✅ 4 separate test files — each student owns their own tests
- ✅ Property-based + LLM-as-Judge testing per agent