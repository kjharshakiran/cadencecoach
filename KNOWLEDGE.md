# Spartan Coach - Technical Knowledge Base

A comprehensive fitness accountability application built with Google Agent Development Kit (ADK), Claude AI, and FastAPI.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [External APIs & Services](#external-apis--services)
4. [Database Structure](#database-structure)
5. [Session State Schema](#session-state-schema)
6. [REST API Endpoints](#rest-api-endpoints)
7. [Multi-Agent System](#multi-agent-system)
8. [Agent Tools](#agent-tools)
9. [Scheduled Jobs](#scheduled-jobs)
10. [Environment Configuration](#environment-configuration)
11. [Data Flow](#data-flow)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/JS)                       │
│                     static/index.html                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Server (server.py)                   │
│  - REST API Endpoints                                           │
│  - Session Management                                           │
│  - APScheduler (Cron Jobs)                                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Google ADK Runner                             │
│  - Manages agent execution                                      │
│  - Routes messages to appropriate agents                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    THE_SPARTAN (Root Agent)                     │
│          spartan_phalanx/main.py                                │
├─────────────────────────────────────────────────────────────────┤
│                       Sub-Agents                                │
│  ┌───────────────┐    ┌──────────────────┐                     │
│  │ planner_agent │    │ monitoring_agent │                     │
│  └───────┬───────┘    └──────────────────┘                     │
│          │                                                      │
│  ┌───────┴────────────────┐                                    │
│  │    Sub-Sub-Agents      │                                    │
│  │  ┌─────────────────┐   │                                    │
│  │  │ nutrition_agent │   │                                    │
│  │  │ fitness_agent   │   │                                    │
│  │  └─────────────────┘   │                                    │
│  └────────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Claude API (via LiteLLM)                    │
│              Model: claude-sonnet-4-20250514                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SQLite Database                              │
│               spartan_phalanx.db                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend Framework | FastAPI | latest |
| Agent Framework | Google ADK | 0.3.0 |
| LLM Provider | Claude (Anthropic) | claude-sonnet-4-20250514 |
| LLM Wrapper | LiteLLM | 1.66.3 |
| Database | SQLite | - |
| Session Management | google.adk.sessions.DatabaseSessionService | - |
| Task Scheduler | APScheduler | latest |
| HTTP Server | Uvicorn | latest |
| Data Validation | Pydantic | latest |

### Python Dependencies (requirements.txt)

```
google-adk[database]==0.3.0
yfinance==0.2.56
psutil==5.9.5
litellm==1.66.3
google-generativeai==0.8.5
python-dotenv==1.1.0
fastapi
uvicorn
pydantic
deprecated
apscheduler
```

---

## External APIs & Services

### 1. Claude API (Anthropic)

**Purpose**: Powers all AI agent conversations and reasoning.

**Integration**: Via LiteLLM wrapper in Google ADK

**Configuration** (`spartan_phalanx/config.py`):
```python
from google.adk.models.lite_llm import LiteLlm

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-20250514")

def get_model():
    if MODEL_PROVIDER == "anthropic":
        return LiteLlm(model=CLAUDE_MODEL)
    return GEMINI_MODEL  # Fallback to Gemini
```

**Environment Variable**: `ANTHROPIC_API_KEY`

**Retry Configuration** (server.py):
```python
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)
```

### 2. Google Generative AI (Optional Fallback)

**Purpose**: Alternative LLM provider (Gemini)

**Model**: `gemini-2.0-flash`

**Environment Variable**: `GOOGLE_API_KEY`

---

## Database Structure

### Database File
- **Location**: `./spartan_phalanx.db`
- **Type**: SQLite
- **Connection String**: `sqlite:///./spartan_phalanx.db`

### Sessions Table

The database uses Google ADK's `DatabaseSessionService` which creates and manages a `sessions` table.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Unique session identifier (UUID) |
| app_name | TEXT | Application name ("SpartanCoach") |
| user_id | TEXT | User identifier (default: "Alex") |
| state | TEXT | JSON blob containing all session state |
| create_time | TIMESTAMP | Session creation time |
| update_time | TIMESTAMP | Last update time |

### Direct Database Access

For state updates that bypass the session service:

```python
def force_update_state(session_id: str, new_state: Dict[str, Any]):
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE sessions SET state = :state, update_time = CURRENT_TIMESTAMP WHERE id = :id"),
            {"state": json.dumps(new_state), "id": session_id}
        )
        conn.commit()
```

### Observability Logs

**File**: `agent_logs.jsonl`

Each interaction is logged in JSONL format:

```json
{
    "timestamp": "2024-01-15T10:30:00.000000",
    "session_id": "abc123-def456",
    "user_input": "What's my daily plan?",
    "agent_response": "Here's your daily battle plan...",
    "agent_name": "THE_SPARTAN"
}
```

---

## Session State Schema

The session state is a JSON object stored in the database. Here's the complete schema:

```python
{
    # User Profile
    "user_name": str,                    # User's display name
    "warrior_profile": {
        "name": str,                     # Full name
        "age": int,                      # Age in years
        "height": float,                 # Height in cm
        "weight": float,                 # Starting weight in kg
        "goal": str,                     # e.g., "Lose 5kg"
        "target_date": str               # YYYY-MM-DD format
    },
    "profile_locked": bool,              # True after onboarding complete

    # Master Plan (Long-term Strategy)
    "master_plan": {
        "plan_text": str,                # Full master plan content
        "created_at": str,               # Creation date
        "status": str                    # "pending_confirmation" | "accepted"
    },
    "plan_accepted": bool,               # User accepted the master plan

    # Daily Plan (Today's Schedule)
    "daily_plan": {
        "date": str,                     # YYYY-MM-DD
        "plan_text": str,                # Today's workout/meals
        "generated_at": str              # ISO timestamp
    },

    # Daily Goals System
    "daily_goals": [                     # Today's goals with status
        {
            "id": str,                   # Unique ID (e.g., "pushups")
            "name": str,                 # Display name
            "completed": bool            # Completion status
        }
    ],
    "daily_goals_template": [            # Default goals (reset source)
        {
            "id": str,
            "name": str
        }
    ],

    # Metrics & History
    "daily_metrics": {                   # Keyed by date
        "YYYY-MM-DD": {
            "weight": float,             # kg
            "sleep": float,              # hours
            "recovery": int              # percentage 0-100
        }
    },
    "daily_logs": [                      # Archived daily records
        {
            "date": str,
            "goals_completed": [str],    # List of goal IDs
            "completion_rate": str,      # "8/11" format
            "weight": float,
            "sleep": float,
            "recovery": int,
            "archived_at": str
        }
    ],

    # Goal Completion
    "goal_completed": bool,              # Final goal achieved
    "goal_completed_at": str,            # ISO timestamp
    "journey_summary": {                 # Generated on completion
        "start_weight": float,
        "final_weight": float,
        "weight_lost": float,
        "total_days": int,
        "perfect_days": int,
        "avg_sleep": float,
        "avg_recovery": int,
        "goal": str,
        "name": str
    }
}
```

### Default Daily Goals Template

```python
[
    {"id": "weight", "name": "Weight check-in"},
    {"id": "ice_wash", "name": "Ice face wash"},
    {"id": "medicine", "name": "Take medicine"},
    {"id": "abc_drink", "name": "ABC drink"},
    {"id": "vitamins", "name": "Take vitamins"},
    {"id": "nuts", "name": "Eat nuts"},
    {"id": "water", "name": "Water intake (8 glasses)"},
    {"id": "pushups", "name": "Push-ups"},
    {"id": "pullups", "name": "Pull-ups"},
    {"id": "standing", "name": "Standing breaks"},
    {"id": "walking", "name": "Walking/Steps"}
]
```

---

## REST API Endpoints

### Base URL: `http://localhost:8000`

---

### Chat & Conversation

#### `POST /api/chat`

Send a message to the AI coach and receive a response.

**Request Body:**
```json
{
    "message": "What's my daily plan?"
}
```

**Response:**
```json
{
    "response": "Here's your DAILY BATTLE PLAN for today..."
}
```

**Side Effects:**
- Logs interaction to `agent_logs.jsonl`
- Auto-saves daily plan if message contains daily plan keywords

**Daily Plan Keywords Detected:**
- "daily plan", "today's plan", "plan for today"
- "daily battle", "workout for today", "today's workout"
- "what should i do today"

---

### User Onboarding

#### `POST /api/onboard`

Submit user profile and trigger master plan generation.

**Request Body:**
```json
{
    "name": "Alex",
    "age": 30,
    "height": 175.0,
    "weight": 80.0,
    "goal": "Lose 5kg",
    "target_date": "2024-03-15"
}
```

**Response:**
```json
{
    "message": "Profile Submitted",
    "agent_response": "⚔️ MASTER PLAN: Alex's TRANSFORMATION..."
}
```

**Side Effects:**
- Sets `profile_locked: true`
- Generates and stores master plan
- Master plan status set to `pending_confirmation`

---

### Plan Management

#### `POST /api/accept-plan`

Accept the master plan and initialize daily tracking.

**Response:**
```json
{
    "message": "Plan accepted! Your transformation begins.",
    "plan_accepted": true
}
```

**Side Effects:**
- Sets `plan_accepted: true`
- Initializes `daily_goals` from template
- Triggers daily plan generation via agent

#### `GET /api/master-plan`

Retrieve the master transformation plan.

**Response:**
```json
{
    "created_at": "2024-01-15",
    "plan_text": "⚔️ MASTER PLAN: Alex's TRANSFORMATION..."
}
```

**Error (404):** `"No master plan available"`

#### `GET /api/daily-plan`

Get today's specific workout and meal plan.

**Response:**
```json
{
    "date": "2024-01-15",
    "plan_text": "🗓️ DAILY BATTLE PLAN - 2024-01-15..."
}
```

**Error (404):** `"No daily plan available. Ask the coach for today's plan!"`

---

### Daily Goals

#### `GET /api/daily-goals`

Get today's goals with completion status.

**Response:**
```json
{
    "date": "2024-01-15",
    "goals": [
        {"id": "weight", "name": "Weight check-in", "completed": true},
        {"id": "pushups", "name": "Push-ups", "completed": false}
    ],
    "completed_count": 5,
    "total_count": 11
}
```

#### `POST /api/goals/check`

Mark a goal as completed.

**Request Body:**
```json
{
    "goal_id": "pushups"
}
```

**Response:**
```json
{
    "message": "Goal 'pushups' checked off!",
    "completed_count": 6,
    "total_count": 11
}
```

**Error (404):** `"Goal 'invalid_id' not found"`

#### `POST /api/goals/uncheck`

Unmark a completed goal.

**Request Body:**
```json
{
    "goal_id": "pushups"
}
```

**Response:**
```json
{
    "message": "Goal 'pushups' unchecked."
}
```

---

### Metrics & History

#### `POST /api/metrics`

Save daily metrics (weight, sleep, recovery).

**Request Body:**
```json
{
    "weight": 79.5,
    "sleep": 7.5,
    "recovery": 85
}
```

All fields are optional - only provided fields are updated.

**Response:**
```json
{
    "message": "Metrics logged! Keep pushing, warrior!",
    "date": "2024-01-15"
}
```

#### `GET /api/metrics/today`

Get today's logged metrics.

**Response:**
```json
{
    "date": "2024-01-15",
    "weight": 79.5,
    "sleep": 7.5,
    "recovery": 85
}
```

#### `GET /api/history`

Get historical data for charts (last 30 days with data).

**Response:**
```json
[
    {
        "date": "2024-01-14",
        "weight": 80.0,
        "sleep": 7.0,
        "recovery": 75,
        "completion_rate": 82
    },
    {
        "date": "2024-01-15",
        "weight": 79.5,
        "sleep": 7.5,
        "recovery": 85,
        "completion_rate": 91
    }
]
```

---

### State & Session

#### `GET /api/state`

Get current session state summary.

**Response:**
```json
{
    "user_name": "Alex",
    "profile_locked": true,
    "plan_accepted": true,
    "master_plan": {...},
    "daily_plan": {...},
    "daily_goals": [...]
}
```

#### `POST /api/reset`

Reset all session data (start fresh).

**Response:**
```json
{
    "message": "Session reset. PREPARE FOR GLORY!"
}
```

**Side Effects:**
- Deletes all sessions from database
- Next request creates fresh session

---

### Journey & Simulation

#### `POST /api/simulate-journey`

Generate 77 days of simulated historical data for testing.

**Response:**
```json
{
    "message": "Journey simulated! 77 days of data generated.",
    "start_weight": 80.0,
    "current_weight": 75.0,
    "weight_lost": 5.0,
    "days_simulated": 78
}
```

**Data Generation Logic:**
- Weight: Progressive loss with daily variation (±0.3kg)
- Sleep: Random 6.5-8.5 hours
- Recovery: Improves from ~65% to ~85% over time
- Goal completion: Improves from ~50% to ~90% over time

#### `POST /api/complete-goal`

Mark the final goal as accomplished and generate summary.

**Response:**
```json
{
    "message": "GOAL ACCOMPLISHED! You are a true Spartan!",
    "summary": {
        "start_weight": 80.0,
        "final_weight": 75.0,
        "weight_lost": 5.0,
        "total_days": 77,
        "perfect_days": 15,
        "avg_sleep": 7.2,
        "avg_recovery": 78,
        "goal": "Lose 5kg",
        "name": "Alex"
    }
}
```

#### `GET /api/journey-status`

Get current journey progress.

**Response:**
```json
{
    "goal_completed": false,
    "journey_summary": null,
    "start_weight": 80.0,
    "current_weight": 77.5,
    "target_weight": 75.0,
    "weight_lost": 2.5,
    "target_loss": 5.0,
    "progress_percent": 50
}
```

---

### Static Files

#### `GET /`

Serves the main frontend (`static/index.html`)

#### `GET /static/{path}`

Serves static files from the `static/` directory

---

## Multi-Agent System

### Agent Hierarchy

```
THE_SPARTAN (Root Agent)
├── planner_agent
│   ├── nutrition_agent
│   └── fitness_agent
└── monitoring_agent
```

### Agent Details

#### THE_SPARTAN (Root Agent)

**File:** `spartan_phalanx/main.py`

**Role:** Commander - Routes conversations to appropriate sub-agents

**Responsibilities:**
- Onboarding flow management
- Plan acceptance handling
- Goal check-off acknowledgments
- Routing to planner_agent or monitoring_agent

**Routing Rules:**
| User Intent | Route To |
|-------------|----------|
| Profile/plan creation | planner_agent |
| Daily plan requests | planner_agent |
| Progress logs | monitoring_agent |
| Weight/step logs | monitoring_agent |
| Status checks | monitoring_agent |

---

#### planner_agent

**File:** `spartan_phalanx/sub_agents/planner_agent.py`

**Role:** Strategist - Creates master and daily plans

**Capabilities:**
1. **Master Plan Generation**
   - Feasibility analysis
   - BMR/TDEE calculations (using `calculate_bmr_tdee` tool)
   - Strategic phase planning
   - Delegates to nutrition_agent and fitness_agent

2. **Daily Plan Generation**
   - Specific workouts with sets/reps
   - Meal schedules with portions
   - Daily goals reminder

**Sub-Agents:**
- `nutrition_agent`
- `fitness_agent`

**Tools:**
- `calculate_bmr_tdee`

---

#### nutrition_agent

**File:** `spartan_phalanx/sub_agents/nutrition_agent.py`

**Role:** The Spartan Chef

**Capabilities:**
- Strategic diet planning (macro splits, meal timing)
- Daily meal plan generation with specific foods
- Constraint handling (traveling, illness)

**Input:**
- Daily calorie target
- Macro split percentages
- Diet type (vegetarian, etc.)
- User constraints

---

#### fitness_agent

**File:** `spartan_phalanx/sub_agents/fitness_agent.py`

**Role:** The Drill Sergeant

**Capabilities:**
- 7-day workout plan creation
- Exercise selection based on access (home/gym)
- Sets/reps programming

**Input:**
- Workout split (Upper/Lower, PPL, etc.)
- Frequency (days per week)
- Goal focus (Strength, Hypertrophy, Endurance)
- Equipment access

---

#### monitoring_agent

**File:** `spartan_phalanx/sub_agents/monitoring_agent.py`

**Role:** The Truth - Progress monitoring

**Capabilities:**
- Analyzes daily logs vs daily plan
- Processes screenshots (scale apps, fitness trackers)
- Extracts metrics from images (weight, body fat, sleep, recovery)
- Discrepancy detection

**Output Format:**
```json
{
  "metrics": {
    "weight": 79.5,
    "body_fat": 18.5,
    "sleep_hours": 7.5,
    "recovery": 85,
    "strain": 12.5
  }
}
```

---

## Agent Tools

### calculate_bmr_tdee

**File:** `spartan_phalanx/tools/calculator_tools.py`

**Purpose:** Calculate Basal Metabolic Rate and Total Daily Energy Expenditure

**Formula:** Mifflin-St Jeor Equation

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| weight_kg | float | Weight in kilograms |
| height_cm | float | Height in centimeters |
| age | int | Age in years |
| gender | str | "male" or "female" |
| activity_level | str | See activity levels below |

**Activity Levels:**
| Level | Factor | Description |
|-------|--------|-------------|
| sedentary | 1.2 | Little or no exercise |
| light | 1.375 | Light exercise 1-3 days/week |
| moderate | 1.55 | Moderate exercise 3-5 days/week |
| active | 1.725 | Hard exercise 6-7 days/week |
| very_active | 1.9 | Very hard exercise, physical job |

**Returns:**
```python
{
    "bmr": 1800,           # kcal
    "tdee": 2790,          # kcal
    "activity_factor": 1.55,
    "formula": "Mifflin-St Jeor"
}
```

---

### State Tools

**File:** `spartan_phalanx/tools/state_tools.py`

#### save_profile

Saves user profile to session state.

**Parameters:**
- name, age, height, weight, goal, target_date

#### save_master_plan

Saves master plan to session state.

**Parameters:**
- plan (dict): Complete master plan object

---

## Scheduled Jobs

Managed by APScheduler (`AsyncIOScheduler`)

### Check-In Jobs

**Schedule:** 9:00 AM, 12:00 PM, 3:00 PM, 9:00 PM daily

**Function:** `scheduled_checkin()`

**Action:** Triggers monitoring agent to check on user progress

```python
scheduler.add_job(scheduled_checkin, 'cron', hour=9, minute=0)
scheduler.add_job(scheduled_checkin, 'cron', hour=12, minute=0)
scheduler.add_job(scheduled_checkin, 'cron', hour=15, minute=0)
scheduler.add_job(scheduled_checkin, 'cron', hour=21, minute=0)
```

### Midnight Reset Job

**Schedule:** 12:00 AM daily

**Function:** `midnight_reset()`

**Actions:**
1. Archives previous day's goals and metrics to `daily_logs`
2. Resets `daily_goals` from template (all unchecked)
3. Clears old daily plan
4. Generates new daily plan for today

**Archive Record Format:**
```python
{
    "date": "2024-01-14",
    "goals_completed": ["weight", "pushups", ...],
    "completion_rate": "8/11",
    "weight": 79.5,
    "sleep": 7.5,
    "recovery": 85,
    "archived_at": "2024-01-15T00:00:00"
}
```

---

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root:

```env
# LLM Configuration
MODEL_PROVIDER=anthropic
CLAUDE_MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Optional: Google Gemini fallback
GOOGLE_API_KEY=xxxxxxxxxxxxx
```

### Configuration File

**File:** `spartan_phalanx/config.py`

```python
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-20250514")
GEMINI_MODEL = "gemini-2.0-flash"
```

---

## Data Flow

### 1. User Onboarding Flow

```
User submits profile form
         │
         ▼
POST /api/onboard
         │
         ▼
Save profile to session state
(profile_locked = true)
         │
         ▼
Send profile to THE_SPARTAN
         │
         ▼
Route to planner_agent
         │
         ├── Call calculate_bmr_tdee tool
         ├── Delegate to nutrition_agent
         └── Delegate to fitness_agent
         │
         ▼
Return combined Master Plan
         │
         ▼
Save master_plan to session state
(status = pending_confirmation)
         │
         ▼
Return response to frontend
```

### 2. Plan Acceptance Flow

```
User clicks "Accept Plan"
         │
         ▼
POST /api/accept-plan
         │
         ▼
Set plan_accepted = true
         │
         ▼
Initialize daily_goals from template
         │
         ▼
Request daily plan from agent
         │
         ▼
Save daily_plan to session state
         │
         ▼
Return success response
```

### 3. Daily Interaction Flow

```
User sends message (e.g., "daily plan")
         │
         ▼
POST /api/chat
         │
         ▼
THE_SPARTAN routes to planner_agent
         │
         ▼
planner_agent generates daily plan
         │
         ▼
Check for daily plan keywords
         │
         ▼
If match: Save to daily_plan in state
         │
         ▼
Log interaction to agent_logs.jsonl
         │
         ▼
Return response to frontend
```

### 4. Midnight Reset Flow

```
APScheduler triggers at 00:00
         │
         ▼
midnight_reset() function
         │
         ├── Archive yesterday's goals to daily_logs
         ├── Reset daily_goals from template
         ├── Clear old daily_plan
         │
         ▼
Generate new daily plan via agent
         │
         ▼
Save new daily_plan to state
         │
         ▼
Log completion
```

---

## File Structure

```
spartancoach/
├── server.py                    # FastAPI server, all endpoints
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables
├── spartan_phalanx.db          # SQLite database
├── agent_logs.jsonl            # Interaction logs
├── static/
│   └── index.html              # Frontend UI
└── spartan_phalanx/
    ├── main.py                 # THE_SPARTAN root agent
    ├── config.py               # Model configuration
    ├── sub_agents/
    │   ├── planner_agent.py    # Planning & strategy
    │   ├── monitoring_agent.py # Progress tracking
    │   ├── nutrition_agent.py  # Diet planning
    │   └── fitness_agent.py    # Workout planning
    └── tools/
        ├── state_tools.py      # Session state tools
        └── calculator_tools.py # BMR/TDEE calculator
```

---

## Quick Reference

### Starting the Server

```bash
cd spartancoach
source .venv/bin/activate
python server.py
```

Server runs at: `http://localhost:8000`

### Key Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send message to coach |
| `/api/onboard` | POST | Submit user profile |
| `/api/accept-plan` | POST | Accept master plan |
| `/api/daily-goals` | GET | Get today's goals |
| `/api/goals/check` | POST | Mark goal complete |
| `/api/metrics` | POST | Log weight/sleep/recovery |
| `/api/history` | GET | Get historical data |
| `/api/state` | GET | Get session state |
| `/api/reset` | POST | Reset all data |

---

*Last updated: December 2025*
