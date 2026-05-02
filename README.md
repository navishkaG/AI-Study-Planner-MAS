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
