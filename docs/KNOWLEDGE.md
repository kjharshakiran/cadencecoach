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
12. [Deployment](#deployment)

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
│                    Gemini API (Primary)                         │
│              Model: gemini-2.5-flash-lite                       │
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
| LLM Provider | Gemini (Google) | gemini-2.5-flash-lite |
| LLM Wrapper | Google GenAI SDK | - |
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

### 1. Google Generative AI (Primary)

**Purpose**: Powers all AI agent conversations and reasoning.

**Model**: `gemini-2.5-flash-lite`

**Environment Variable**: `GOOGLE_API_KEY`

### 2. Claude API (Anthropic - Optional)

**Purpose**: Alternative LLM provider.

**Integration**: Via LiteLLM wrapper in Google ADK

**Configuration** (`spartan_phalanx/config.py`):
```python
from google.adk.models.lite_llm import LiteLlm

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-20250514")

def get_model():
    if MODEL_PROVIDER == "anthropic":
        return LiteLlm(model=CLAUDE_MODEL)
    return GEMINI_MODEL
```

**Environment Variable**: `ANTHROPIC_API_KEY`

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

*Last updated: December 22, 2025*

---

## Notification System

### Overview

The notification system sends proactive coaching reminders to users based on their timezone and daily schedule. Notifications are stored in `pending_reminders` in each user's session state.

### Notification Types

| Type | Trigger | Description |
|------|---------|-------------|
| `proactive_checkin` | Hourly (7am-10pm user time) | Progress status with goals/water/steps |
| `water_reminder` | Every 30 min | Hydration reminder if behind target |
| `schedule_reminder` | 15-30 min before events | Upcoming meal/workout reminder |
| `overdue_reminder` | After missed time | Alert for missed scheduled items |

### Template-Based Notifications (Simplified)

Notifications use simple templates instead of AI calls for speed and reliability:

```python
# Urgency levels determine message tone
if urgency_level >= 3:  # RED - Critical
    message = f"🚨 {user_name}, CRITICAL STATUS!\n\n{status_line}..."
elif urgency_level >= 2:  # ORANGE - Urgent
    message = f"⚠️ {user_name}, STATUS CHECK!\n\n{status_line}..."
elif urgency_level >= 1:  # YELLOW - Attention
    message = f"📋 {user_name}, PROGRESS UPDATE\n\n{status_line}..."
else:  # GREEN - On track
    message = f"✅ {user_name}, GREAT PROGRESS!\n\n{status_line}..."
```

### Scheduler Jobs

```python
scheduler.add_job(proactive_checkin, 'cron', minute=0)      # Every hour on the hour
scheduler.add_job(water_reminder, 'cron', minute=30)        # Every hour at :30
scheduler.add_job(schedule_reminder, 'cron', minute='*/15') # Every 15 minutes
scheduler.add_job(midnight_reset, 'cron', minute=5)         # Every hour at :05
```

### User-Specific Notifications

Each user has their own `pending_reminders` list in their session state. The scheduler:
1. Gets all users from `registered_users` table
2. Checks each user's timezone to determine local time
3. Only sends notifications during user's wake/sleep hours
4. Stores notifications in that user's session

### Notification Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/notifications` | GET | Get pending notifications |
| `/api/notifications/clear` | POST | Clear all notifications |
| `/api/notifications/settings` | GET/POST | Get/update notification settings |
| `/api/trigger-checkin` | POST | Manually trigger check-in |
| `/api/trigger-checkin?force=true` | POST | Force check-in for current user |

### Testing Notifications

Use `test_notifications.py` to test:

```bash
python test_notifications.py                    # List all users
python test_notifications.py <username>         # Trigger check-in for user
python test_notifications.py <username> --add   # Add simple test notification
python test_notifications.py <username> --view  # View user's notifications
python test_notifications.py <username> --clear # Clear user's notifications
```

---

## WhatsApp Integration

### Twilio WhatsApp API

WhatsApp notifications are sent via Twilio's API when enabled.

**Configuration:**
```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### Notification Settings

Users must enable WhatsApp in their notification settings:

```python
notification_settings = {
    "wake_time": "07:00",
    "sleep_time": "22:00",
    "enable_push": True,
    "enable_whatsapp": True,        # Must be True
    "whatsapp_number": "+1234567890", # User's WhatsApp number
    "timezone": "America/New_York"
}
```

### WhatsApp Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/whatsapp/status` | GET | Check connection status |
| `/api/whatsapp/connect` | POST | Connect WhatsApp number |
| `/api/whatsapp/disconnect` | POST | Disconnect WhatsApp |
| `/api/whatsapp/test` | POST | Send test message |
| `/api/whatsapp/toggle` | POST | Enable/disable notifications |

---

## Multi-User Support

### User Registration

Users are tracked in the `registered_users` table for scheduled tasks:

```sql
CREATE TABLE registered_users (
    username TEXT PRIMARY KEY
)
```

Users are automatically registered during onboarding.

### User Identification

```python
def get_user_id(request: Request) -> str:
    """Get user ID from logged-in user session."""
    user = get_current_user(request)
    if user:
        return user.get("username", "anonymous")
    return "anonymous"
```

### Session Isolation

Each user has their own session with isolated:
- `warrior_profile` - User's profile data
- `master_plan` - Their transformation plan
- `daily_goals` - Today's goals
- `pending_reminders` - Their notifications
- `notification_settings` - Their preferences

---

## Key Improvements (December 2025)

### 1. Simplified Notifications

**Before:** AI-generated messages for every check-in (slow, could fail)

**After:** Template-based messages (instant, reliable)

- Removed AI calls from `proactive_checkin` and `_force_proactive_checkin_for_user`
- Messages use urgency-based templates with user data
- Same message sent to both app and WhatsApp

### 2. JSON Serialization Fixes

Fixed serialization errors when saving session state:

```python
def make_json_serializable(obj):
    """Recursively convert objects to JSON-serializable types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()
                if not k.startswith('_')}
    # ... handles lists, datetimes, objects
```

### 3. Multi-Part Response Handling

Fixed agent responses that span multiple parts:

```python
if event.is_final_response() and event.content and event.content.parts:
    # Concatenate ALL text parts
    response_parts = [p.text for p in event.content.parts
                      if hasattr(p, 'text') and p.text]
    final_response_text = "".join(response_parts).strip()
```

### 4. Template Placeholder Fix

Fixed Gemini API errors by replacing `{X}` placeholders with `[X]` in agent prompts:

```python
# Before (caused "Context variable not found" errors)
"You're {X} steps behind. MOVE NOW."

# After
"You're [steps_behind] steps behind. MOVE NOW."
```

### 5. Gemini as Primary Model

Switched from Claude to Gemini as the default model provider:

```python
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
GEMINI_MODEL = "gemini-2.5-flash-lite"
```

---

## Deployment

The Spartan Coach is designed to be deployed on Google Cloud Platform (GCP) using Cloud Run.

### Quick Start

The repository includes a helper script `deploy.sh` that automates the deployment process.

```bash
./deploy.sh
```

For detailed deployment instructions, including prerequisites, manual deployment steps, and environment configuration, please refer to the [Deployment Guide](DEPLOYMENT.md).

### Infrastructure

- **Compute**: Google Cloud Run (Serverless container)
- **Database**: SQLite (Development) / Cloud SQL (Production)
- **Build**: Google Cloud Build
- **Registry**: Google Container Registry (GCR)

---

## Future Coaching Improvements (Roadmap)

### Phase 1: Gamification (In Progress)

#### Streak System
- Track consecutive days of 100% goal completion
- "Streak at risk" warnings when time running out
- Streak recovery mechanics (e.g., "wellness days" don't break streak)

#### Personal Records
- Track all-time bests: highest steps, longest streak, fastest completion
- Celebrate new PRs with special messages
- Reference PRs in motivation: "You're 500 steps from beating your record!"

### Phase 2: Adaptive Coaching

#### Coaching Personality Modes
- `drill_sergeant` (default): Aggressive, commanding
- `supportive_mentor`: Encouraging, celebrates small wins
- `data_analyst`: Facts-focused, minimal emotion
- `auto`: Adapts based on user response patterns

#### Burnout Detection
- Detect: 3+ days low completion, Whoop RED recovery, sleep < 6h
- Auto-switch to "Recovery Mode" with reduced goals
- Softer messaging: "Rest is part of the journey"

### Phase 3: Behavioral Science

#### Implementation Intentions
- Add "IF X, THEN Y" plans to daily schedule
- Example: "IF I wake up, THEN first thing is ice face wash"

#### Identity Reinforcement
- Use identity language: "Spartans stay hydrated" vs "You should drink"
- Reinforce identity after streaks: "You ARE a Spartan. This is WHO YOU ARE."

#### Reframe Failures
- Ask "What happened?" instead of just criticizing
- Offer options: too many goals? Low energy? Something came up?

### Phase 4: Advanced Features

#### Weekly Retrospective
- Sunday summary: wins, improvement areas, patterns
- Set focus for next week based on data

#### Warrior Rank System
- Recruit (0-7 days) → Soldier (8-21) → Warrior (22-50) → Spartan (51-100) → Elite (101-200) → Legend (201+)
- Rank-up celebrations

#### Context-Aware Nudges
- Weather integration: "Rainy? Perfect for indoor HIIT"
- Time-pattern: "You're usually done by now. Everything okay?"
- Energy-pattern: Send reminders at user's high-energy times

### Phase 5: Integrations

#### Outlook Calendar
- Sync work calendar
- Identify breaks for walks/stretches
- Suggest movement during back-to-back meetings

#### Apple Health (via Terra/Vital)
- Third-party API for Apple Health data
- Steps, workouts, sleep from Apple Watch

---

## Implementation Notes

### Minimal Change Philosophy
- Small, surgical changes
- One feature at a time
- Test thoroughly before adding more
- Don't break working features
