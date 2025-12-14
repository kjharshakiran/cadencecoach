# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spartan Coach is an AI-powered fitness accountability application built on a multi-agent architecture using the Google Agent Development Kit (ADK). It uses a "Spartan" persona to create personalized fitness plans and enforce discipline.

## Commands

### Run the Server
```bash
python server.py
```
The server runs on http://localhost:8000 with uvicorn.

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Google Cloud Authentication
```bash
gcloud auth application-default login
```
Required for Vertex AI API access (Gemini 2.0 Flash model).

## Architecture

### Multi-Agent System (The Phalanx)

The system uses hierarchical agents in `spartan_phalanx/`:

- **THE_SPARTAN** (`main.py`): Root orchestrator agent that routes requests to sub-agents based on user intent
- **planner_agent**: Creates Master Plan with BMR/TDEE calculations, coordinates nutrition and fitness agents
- **fitness_agent**: Generates 7-day workout plans based on workout split and user equipment access
- **nutrition_agent**: Creates strategic diet principles and daily meal plans
- **monitoring_agent**: Analyzes progress logs and fitness tracker screenshots (Whoop, scale data), outputs metrics as JSON

### Agent Hierarchy
```
THE_SPARTAN (Commander)
├── planner_agent (Strategist)
│   ├── nutrition_agent
│   └── fitness_agent
└── monitoring_agent (Scout)
```

### Session State Schema
The session state stored in SQLite includes:
- `warrior_profile`: User profile data (name, age, height, weight, goal, target_date)
- `master_plan`: Generated fitness plan with status
- `daily_logs`: Progress entries
- `plan_locked`: Boolean indicating if plan is confirmed

### Key Files
- `server.py`: FastAPI application with endpoints `/api/chat`, `/api/onboard`, `/api/reset`, `/api/state`
- `spartan_phalanx/tools/calculator_tools.py`: BMR/TDEE calculation using Mifflin-St Jeor equation
- `utils.py`: CLI utilities for terminal-based interaction (colored output, state display)

### Scheduled Check-ins
APScheduler triggers automated check-ins at 9AM, 12PM, 3PM, and 9PM via the monitoring agent.

## Tech Stack
- Backend: Python, FastAPI, Google ADK, Google GenAI SDK (Gemini 2.0 Flash)
- Frontend: Vanilla HTML/CSS/JS in `static/`
- Database: SQLite via SQLAlchemy (`spartan_phalanx.db`)
- Scheduling: APScheduler
