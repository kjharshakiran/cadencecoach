# Spartan Coach - AI Accountability Engine

## Problem Statement
Most fitness applications fail because they lack **accountability** and **adaptability**. Users get a static plan, follow it for a week, and then quit when life gets in the way or motivation wanes. There is no "coach" to adjust the plan when you're sick, or to demand execution when you're lazy. The experience is passive and impersonal.

## Solution
**Spartan Coach** is an AI-powered accountability engine designed to forge users into warriors. It uses a **multi-agent system** led by "THE SPARTAN" — a persona-driven commander who doesn't just suggest workouts but demands them.

The system:
1.  **Interviews** the user to create a personalized "Master Plan".
2.  **Calculates** precise metabolic needs (BMR/TDEE) using custom tools.
3.  **Adapts** daily plans based on real-time constraints (e.g., "I'm traveling", "I'm sick").
4.  **Enforces** discipline through a tough, motivating persona.

## Architecture
The project uses a **Hub-and-Spoke** multi-agent architecture built with the **Google Agent Development Kit (ADK)** and **Gemini 2.0 Flash**.

-   **THE SPARTAN (Hub)**: The central orchestrator. Manages user interaction, maintains the persona, and routes tasks.
-   **PLANNER AGENT (Spoke)**: Strategist. Generates the long-term Master Plan and calculates metrics.
-   **FITNESS AGENT (Spoke)**: Drill Sergeant. Generates detailed workout splits and exercises.
-   **NUTRITION AGENT (Spoke)**: Chef. Generates meal plans and macro targets.
-   **MONITORING AGENT (Spoke)**: Scout. Tracks progress and logs.

### Key Concepts Implemented

1.  **Multi-Agent System**:
    -   We use a hierarchical team of 5 specialized agents.
    -   **Routing**: The main agent (`THE_SPARTAN`) intelligently routes user intents to sub-agents (`planner`, `fitness`, `nutrition`, `monitoring`) based on context.
    -   **Delegation**: The `planner_agent` delegates detailed planning to `fitness` and `nutrition` agents during Master Plan creation.

2.  **Tools**:
    -   **Custom Tool**: `calculate_bmr_tdee` (in `calculator_tools.py`).
    -   The `planner_agent` uses this Python tool to accurately calculate Basal Metabolic Rate and Total Daily Energy Expenditure using the Mifflin-St Jeor equation, ensuring the diet plan is scientifically grounded.

3.  **Observability**:
    -   **Structured Logging**: We implemented a custom logging system (`log_agent_interaction`) that captures every interaction between the user and the agents.
    -   Logs are written to `agent_logs.jsonl` with timestamps, session IDs, and agent names, allowing for detailed tracing of the conversation flow and agent performance.

4.  **Sessions & State Management**:
    -   **Database Persistence**: We use `DatabaseSessionService` with SQLite to persist user sessions.
    -   **State Locking**: The system tracks the user's "Warrior Profile" and "Master Plan" in the session state. Once a plan is accepted, it is "locked" (`profile_locked=True`), transitioning the user from the onboarding phase to the execution phase.

## Tech Stack
-   **AI**: Google Gemini 2.0 Flash, Google ADK
-   **Backend**: Python, FastAPI
-   **Frontend**: HTML/CSS/JS (Vanilla)
-   **Database**: SQLite
