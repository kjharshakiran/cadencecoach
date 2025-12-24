# Spartan Coach - Architectural Retrospective & Improvement Plan

## Executive Summary

This document provides a comprehensive architectural review of the Spartan Coach codebase, identifying critical issues in code organization, security, state management, and database design. It proposes a restructured architecture that addresses these concerns while preparing the codebase for mobile app development.

**Current State:**
- **server.py**: 4,448 lines - monolithic file containing all business logic
- **Endpoints**: 63 API endpoints with no modularization
- **Security**: Multiple critical vulnerabilities
- **Database**: Primitive schema with all data as JSON blobs
- **State**: Spread across multiple untyped dictionaries

**Recommendation**: Major refactoring required before mobile launch.

---

## Table of Contents

1. [Monolith Analysis](#1-monolith-analysis)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [State Management Issues](#3-state-management-issues)
4. [Database Schema Problems](#4-database-schema-problems)
5. [Agent Architecture Review](#5-agent-architecture-review)
6. [Proposed Architecture](#6-proposed-architecture)
7. [Migration Strategy](#7-migration-strategy)
8. [Implementation Priorities](#8-implementation-priorities)

---

## 1. Monolith Analysis

### Current server.py Structure (4,448 lines)

```
Lines 1-100:      Imports, configuration, logging
Lines 100-540:    LOGIN_PAGE_HTML (440 lines of embedded HTML/CSS/JS!)
Lines 540-670:    Authentication endpoints (login, signup, Google OAuth)
Lines 670-960:    Whoop OAuth + data endpoints
Lines 960-1220:   WhatsApp endpoints
Lines 1220-1440:  Session management, user registration
Lines 1440-1770:  Onboarding, master plan generation
Lines 1770-2000:  Reset, daily goals management
Lines 2000-2200:  Metrics logging
Lines 2200-2500:  History, daily plan, journey status
Lines 2500-2700:  Water tracking endpoints
Lines 2700-2900:  Step tracking endpoints
Lines 2900-3150:  Calendar integration
Lines 3150-3400:  Notification endpoints
Lines 3400-3500:  Urgency, check-in triggers
Lines 3500-4000:  Scheduler functions (proactive_checkin, water_reminder, etc.)
Lines 4000-4200:  Parsing utilities
Lines 4200-4448:  App startup, scheduler configuration
```

### Critical Issues

| Issue | Severity | Impact |
|-------|----------|--------|
| **Embedded HTML** (440 lines) | High | Login page is a Python string with inline CSS/JS |
| **No modularization** | High | All 63 endpoints in one file |
| **Mixed concerns** | High | Auth, business logic, scheduling, utilities all together |
| **No dependency injection** | Medium | Services instantiated globally |
| **Inline Pydantic models** | Medium | 15+ models scattered through file |
| **Duplicate code** | Medium | Session/state retrieval repeated 50+ times |
| **No error handling abstraction** | Medium | try/except scattered everywhere |

### Code Smell Examples

**1. Session retrieval duplicated everywhere:**
```python
# This pattern appears 50+ times:
user_id = get_user_id(request)
session_id = get_or_create_session_id(user_id)
session = session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
state = session.state
```

**2. HTML embedded in Python:**
```python
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <!-- ... 440 lines of HTML/CSS/JS ... -->
</html>
"""
```

**3. Direct database access in endpoints:**
```python
engine = sqlalchemy.create_engine(db_url)
with engine.connect() as conn:
    conn.execute(text("DELETE FROM sessions WHERE app_name = :app AND user_id = :user"), ...)
```

---

## 2. Security Vulnerabilities

### Critical (Must Fix Before Production)

| Vulnerability | Location | Risk | Fix |
|--------------|----------|------|-----|
| **SHA256 password hashing** | `server.py:97-98` | Critical | Migrate to bcrypt/argon2 |
| **CORS allows all origins** | `server.py:86-92` | Critical | Whitelist specific origins |
| **Hardcoded default credentials** | `server.py:41-42` | Critical | Remove entirely |
| **Session secret fallback** | `server.py:43` | High | Required env var, no fallback |
| **OAuth tokens in session state** | `server.py:714-719` | High | Encrypt at rest |
| **No rate limiting** | Entire API | High | Add per-user/IP limits |

### Current Vulnerable Code

```python
# server.py:97-98 - WEAK PASSWORD HASHING
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()  # INSECURE!

# server.py:41-42 - HARDCODED CREDENTIALS
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "demo_user")
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "SpartanWarrior2024!")  # EXPOSED!

# server.py:86-92 - OPEN CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DANGEROUS!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# server.py:43 - WEAK SESSION SECRET
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))  # Changes on restart!
```

### Medium Severity

| Vulnerability | Location | Risk |
|--------------|----------|------|
| No CSRF protection | Form endpoints | Medium |
| No input validation | Most endpoints | Medium |
| SQL via text() | Multiple locations | Medium |
| WhatsApp webhook unverified | `server.py:1116` | Medium |
| No API key authentication | All endpoints | Medium |
| Tokens not encrypted | Session state | Medium |

### Recommended Security Stack

```python
# Proper password hashing
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Restricted CORS
origins = [
    "https://spartancoach.app",
    "https://app.spartancoach.com",
    "capacitor://localhost",  # Mobile app
    "http://localhost:3000",  # Dev only
]

# Required environment variables (no fallbacks)
SESSION_SECRET = os.environ["SESSION_SECRET"]  # Will fail if not set

# JWT for API authentication
from jose import JWTError, jwt
```

---

## 3. State Management Issues

### Current State Structure

The session state is a giant untyped dictionary with 25+ top-level keys:

```python
{
    "user_name": str,
    "warrior_profile": {...},
    "coaching_style": str,
    "profile_locked": bool,
    "master_plan": {...},
    "plan_accepted": bool,
    "daily_plan": {...},
    "daily_goals": [...],
    "daily_goals_template": [...],
    "daily_logs": [...],
    "daily_metrics": {...},
    "google_calendar_token": str,
    "today_calendar_events": [...],
    "calendar_gaps": [...],
    "calendar_last_sync": str,
    "water_intake": {...},
    "urgency_level": int,
    "pending_reminders": [...],
    "push_subscription": {...},
    "notification_settings": {...},
    "streak": {...},
    "personal_records": {...},
    "whoop_connected": bool,
    "whoop_tokens": {...},
    "whoop_profile": {...},
    "whoop_data": {...},
    "fitness_targets": {...},
    "daily_schedule": [...],
    "last_daily_reset": str,
    "goal_completed": bool,
    "journey_summary": {...}
}
```

### Problems

| Issue | Impact | Example |
|-------|--------|---------|
| **No type validation** | Runtime errors | `state["daily_goals"]` could be None, list, or dict |
| **Redundant data** | Sync bugs | Water tracked in both `water_intake` AND `daily_goals[].current` |
| **Deep nesting** | Hard to query | `state["whoop_tokens"]["access_token"]` |
| **No schema versioning** | Migration hell | Adding new fields breaks old sessions |
| **Serialization issues** | Data loss | `force_update_state` uses `make_json_serializable` hack |
| **No TTL/cleanup** | Storage bloat | Old sessions never deleted |

### Redundant State Examples

```python
# Water is tracked in TWO places:
state["water_intake"] = {"date": "2024-01-15", "glasses": 5, "last_logged": "..."}
state["daily_goals"][6] = {"id": "water", "current": 5, "target": 8, "completed": False}

# Steps tracked in TWO places:
state["daily_metrics"]["2024-01-15"]["steps"] = 8500
state["daily_goals"][10] = {"id": "walking", "current": 8500, "target": 10000}
```

### State Synchronization Code (Symptom of Bad Design)

```python
# server.py:2027-2043 - Manual sync between redundant state
if goal["id"] == "water" and goal.get("target"):
    water_intake = state.get("water_intake", {...})
    water_intake["glasses"] = goal.get("current", goal.get("target", 8))
    state["water_intake"] = water_intake

if goal["id"] == "walking" and goal.get("target"):
    daily_metrics = state.get("daily_metrics", {})
    daily_metrics[today]["steps"] = goal.get("current", goal.get("target", 10000))
```

---

## 4. Database Schema Problems

### Current Schema

```sql
-- Only 2 tables exist:

-- 1. ADK's sessions table (stores everything as JSON)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    app_name TEXT,
    user_id TEXT,
    state TEXT,  -- JSON blob containing ALL user data
    create_time TIMESTAMP,
    update_time TIMESTAMP
);

-- 2. Custom registered_users (just usernames)
CREATE TABLE registered_users (
    username TEXT PRIMARY KEY
);

-- Users also stored in users.json file (separate from DB!)
```

### Problems

| Issue | Impact |
|-------|--------|
| **All data in JSON blob** | Cannot query, no indexing, no constraints |
| **No relational modeling** | Duplicate data, no referential integrity |
| **No proper user table** | Users in file + table, passwords in JSON |
| **No audit trail** | No created_at, updated_at on operations |
| **No data normalization** | Goals, metrics, plans all nested in one blob |
| **Dual storage** | `users.json` file AND `registered_users` table |

### Data Access Patterns (Workarounds)

```python
# server.py:1136-1147 - Scanning ALL sessions to find user by phone
result = conn.execute(text("SELECT user_id, state FROM sessions WHERE app_name = :app"), {"app": APP_NAME})
for row in result.fetchall():
    uid, state_data = row
    state = json.loads(state_data) if isinstance(state_data, str) else state_data
    if state.get("notification_settings", {}).get("whatsapp_number") == phone_number:
        user_id = uid
        break
# O(n) scan of ALL users just to find one by phone number!
```

---

## 5. Agent Architecture Review

### Current Agent Hierarchy

```
THE_SPARTAN (Commander)
├── Tools: calculate_bmr_tdee, accept_plan, get_daily_plan
└── monitoring_agent (Drill Instructor)
    └── Tools: check_goal_progress, calculate_urgency_level,
               get_water_status, get_step_count, get_whoop_status,
               verify_workout_claim, verify_sleep_claim, get_training_readiness
```

### Issues

| Issue | Location | Impact |
|-------|----------|--------|
| **Duplicate functionality** | `accept_plan` in both tools AND server.py | Inconsistent behavior |
| **State access inconsistency** | Tools use `tool_context.state`, server uses `session.state` | Race conditions |
| **Tools reach into DB** | `proactive_tools.py` imports DB logic | Layer violation |
| **No tool result caching** | Each tool call hits DB | Performance |

### Tool/Server Duplication Example

```python
# spartan_phalanx/tools/state_tools.py:16-41
def accept_plan(tool_context: ToolContext):
    tool_context.state["plan_accepted"] = True
    tool_context.state["master_plan"]["status"] = "accepted"
    # Initialize daily goals...

# server.py:1860-1941
@app.post("/api/accept-plan")
async def accept_plan(request: Request):
    state["plan_accepted"] = True
    # DIFFERENT implementation - also generates daily plan
    # These two can get out of sync!
```

---

## 6. Proposed Architecture

### Target Directory Structure

```
spartancoach/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Settings, environment validation
│   ├── dependencies.py         # Dependency injection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # API v1 router aggregation
│   │   │   ├── auth.py         # Auth endpoints
│   │   │   ├── users.py        # User profile endpoints
│   │   │   ├── plans.py        # Master/daily plan endpoints
│   │   │   ├── goals.py        # Daily goals endpoints
│   │   │   ├── metrics.py      # Weight, steps, water endpoints
│   │   │   ├── integrations.py # Whoop, calendar, WhatsApp
│   │   │   └── notifications.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── auth.py         # Auth request/response models
│   │       ├── users.py
│   │       ├── plans.py
│   │       ├── goals.py
│   │       └── metrics.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py         # Password hashing, JWT, CORS
│   │   ├── exceptions.py       # Custom exceptions
│   │   └── middleware.py       # Rate limiting, auth middleware
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py             # SQLAlchemy base
│   │   ├── user.py             # User model
│   │   ├── plan.py             # MasterPlan, DailyPlan models
│   │   ├── goal.py             # Goal, GoalCompletion models
│   │   ├── metric.py           # DailyMetric model
│   │   ├── integration.py      # WhoopToken, CalendarToken models
│   │   └── notification.py     # Notification, PushSubscription models
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py     # User business logic
│   │   ├── plan_service.py     # Plan generation, acceptance
│   │   ├── goal_service.py     # Goal tracking logic
│   │   ├── metric_service.py   # Metrics aggregation
│   │   ├── notification_service.py
│   │   ├── whoop_service.py    # Whoop integration
│   │   ├── calendar_service.py
│   │   └── whatsapp_service.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── spartan.py          # THE_SPARTAN agent
│   │   ├── monitor.py          # Monitoring agent
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── calculator.py
│   │       ├── plan_tools.py
│   │       └── progress_tools.py
│   │
│   └── scheduler/
│       ├── __init__.py
│       ├── jobs.py             # Scheduled job definitions
│       └── tasks.py            # Task implementations
│
├── migrations/                  # Alembic migrations
│   ├── versions/
│   └── env.py
│
├── static/                      # Frontend (unchanged)
├── templates/                   # Jinja2 templates (extracted HTML)
│   └── login.html
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

### Proposed Database Schema

```sql
-- Users table (proper authentication)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- User profiles (separated from auth)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100),
    age INTEGER,
    height_cm FLOAT,
    weight_lbs FLOAT,
    goal TEXT,
    target_date DATE,
    reason TEXT,
    coaching_style VARCHAR(20) DEFAULT 'drill_sergeant',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Master plans
CREATE TABLE master_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_text TEXT NOT NULL,
    bmr FLOAT,
    tdee FLOAT,
    target_calories FLOAT,
    protein_grams FLOAT,
    water_glasses INTEGER DEFAULT 8,
    daily_steps INTEGER DEFAULT 10000,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, completed
    created_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP
);

-- Daily plans
CREATE TABLE daily_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    master_plan_id UUID REFERENCES master_plans(id),
    plan_date DATE NOT NULL,
    plan_text TEXT,
    schedule JSONB,  -- Parsed time-based schedule
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, plan_date)
);

-- Goal templates (what goals exist)
CREATE TABLE goal_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),  -- health, nutrition, exercise, movement
    has_target BOOLEAN DEFAULT FALSE,
    default_target INTEGER,
    display_order INTEGER
);

-- Daily goal completions
CREATE TABLE daily_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    goal_template_id UUID REFERENCES goal_templates(id),
    goal_date DATE NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    current_value INTEGER,  -- For trackable goals like water, steps
    target_value INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, goal_template_id, goal_date)
);

-- Daily metrics (weight, sleep, recovery)
CREATE TABLE daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    weight_lbs FLOAT,
    sleep_hours FLOAT,
    recovery_score INTEGER,
    steps INTEGER,
    water_glasses INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, metric_date)
);

-- Notification settings
CREATE TABLE notification_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    wake_time TIME DEFAULT '07:00',
    sleep_time TIME DEFAULT '22:00',
    enable_push BOOLEAN DEFAULT TRUE,
    enable_whatsapp BOOLEAN DEFAULT FALSE,
    whatsapp_number VARCHAR(20),
    push_subscription JSONB
);

-- Integration tokens (encrypted!)
CREATE TABLE integration_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- whoop, google_calendar, google_oauth
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMP,
    connected_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Notifications/reminders
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50),  -- proactive_checkin, water_reminder, schedule_reminder
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Streaks and records
CREATE TABLE user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_complete_date DATE,
    perfect_days_total INTEGER DEFAULT 0
);

-- Indexes for common queries
CREATE INDEX idx_daily_goals_user_date ON daily_goals(user_id, goal_date);
CREATE INDEX idx_daily_metrics_user_date ON daily_metrics(user_id, metric_date);
CREATE INDEX idx_daily_plans_user_date ON daily_plans(user_id, plan_date);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX idx_notification_settings_whatsapp ON notification_settings(whatsapp_number) WHERE whatsapp_number IS NOT NULL;
```

### Service Layer Example

```python
# app/services/goal_service.py
from sqlalchemy.orm import Session
from app.models.goal import DailyGoal, GoalTemplate
from app.models.metric import DailyMetric
from datetime import date

class GoalService:
    def __init__(self, db: Session):
        self.db = db

    def get_daily_goals(self, user_id: str, goal_date: date = None) -> list[DailyGoal]:
        goal_date = goal_date or date.today()
        return self.db.query(DailyGoal).filter(
            DailyGoal.user_id == user_id,
            DailyGoal.goal_date == goal_date
        ).all()

    def complete_goal(self, user_id: str, goal_id: str, value: int = None) -> DailyGoal:
        goal = self.db.query(DailyGoal).filter(
            DailyGoal.id == goal_id,
            DailyGoal.user_id == user_id
        ).first()

        if not goal:
            raise NotFoundException("Goal not found")

        goal.completed = True
        goal.completed_at = datetime.utcnow()

        if value and goal.target_value:
            goal.current_value = value

            # Sync to daily metrics if applicable
            if goal.goal_template.name == "water":
                self._sync_water_metric(user_id, goal.goal_date, value)
            elif goal.goal_template.name == "walking":
                self._sync_steps_metric(user_id, goal.goal_date, value)

        self.db.commit()
        return goal

    def _sync_water_metric(self, user_id: str, goal_date: date, glasses: int):
        metric = self._get_or_create_metric(user_id, goal_date)
        metric.water_glasses = glasses
        self.db.commit()

    def _get_or_create_metric(self, user_id: str, goal_date: date) -> DailyMetric:
        metric = self.db.query(DailyMetric).filter(
            DailyMetric.user_id == user_id,
            DailyMetric.metric_date == goal_date
        ).first()

        if not metric:
            metric = DailyMetric(user_id=user_id, metric_date=goal_date)
            self.db.add(metric)

        return metric
```

### API Router Example

```python
# app/api/v1/goals.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.services.goal_service import GoalService
from app.api.schemas.goals import GoalResponse, GoalCompleteRequest

router = APIRouter(prefix="/goals", tags=["goals"])

@router.get("/daily", response_model=list[GoalResponse])
async def get_daily_goals(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = GoalService(db)
    return service.get_daily_goals(current_user.id)

@router.post("/{goal_id}/complete", response_model=GoalResponse)
async def complete_goal(
    goal_id: str,
    request: GoalCompleteRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    service = GoalService(db)
    return service.complete_goal(current_user.id, goal_id, request.value)
```

---

## 7. Migration Strategy

### Phase 1: Security Fixes (Week 1)

**Priority: CRITICAL - Do before any public launch**

1. **Replace password hashing**
   ```python
   # Before
   hashlib.sha256(password.encode()).hexdigest()

   # After
   from passlib.context import CryptContext
   pwd_context = CryptContext(schemes=["bcrypt"])
   pwd_context.hash(password)
   ```

2. **Fix CORS configuration**
   ```python
   # Before
   allow_origins=["*"]

   # After
   allow_origins=[
       "https://spartancoach.app",
       "https://app.spartancoach.com",
       "capacitor://localhost",
   ]
   ```

3. **Remove hardcoded credentials**
   - Delete `DEFAULT_USERNAME` and `DEFAULT_PASSWORD`
   - Require all users to register

4. **Require SESSION_SECRET**
   ```python
   SESSION_SECRET = os.environ["SESSION_SECRET"]  # No fallback
   ```

5. **Add rate limiting**
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)

   @app.post("/auth/login")
   @limiter.limit("5/minute")
   async def login(...):
   ```

### Phase 2: Extract Modules (Week 2-3)

1. **Extract HTML templates**
   - Move `LOGIN_PAGE_HTML` to `templates/login.html`
   - Use Jinja2 for rendering

2. **Create API routers**
   - `app/api/v1/auth.py` - Authentication endpoints
   - `app/api/v1/goals.py` - Goal management
   - `app/api/v1/metrics.py` - Metrics tracking
   - etc.

3. **Extract Pydantic schemas**
   - Move all `BaseModel` classes to `app/api/schemas/`

4. **Create service layer**
   - Move business logic from endpoints to services
   - Services take `db: Session` parameter

### Phase 3: Database Migration (Week 4-5)

1. **Set up Alembic**
   ```bash
   alembic init migrations
   ```

2. **Create new schema**
   - Generate migrations for new tables
   - Add indexes

3. **Data migration script**
   ```python
   # migrate_sessions.py
   def migrate_session_to_tables(session_state, user_id):
       # Extract user profile
       profile = session_state.get("warrior_profile", {})
       db.execute("""
           INSERT INTO user_profiles (user_id, name, age, ...)
           VALUES (:user_id, :name, :age, ...)
       """, {...})

       # Extract master plan
       master_plan = session_state.get("master_plan", {})
       db.execute("""
           INSERT INTO master_plans (user_id, plan_text, ...)
           VALUES (:user_id, :plan_text, ...)
       """, {...})

       # Extract daily metrics
       for date_str, metrics in session_state.get("daily_metrics", {}).items():
           db.execute("""
               INSERT INTO daily_metrics (user_id, metric_date, weight_lbs, ...)
               VALUES (:user_id, :date, :weight, ...)
           """, {...})
   ```

4. **Run migration**
   - Backup current database
   - Run migration script
   - Validate data integrity

### Phase 4: Agent Integration (Week 6)

1. **Simplify agent tools**
   - Tools call services, not DB directly
   - Remove duplicate `accept_plan` implementations

2. **Consistent state access**
   - All state through service layer
   - No direct `tool_context.state` manipulation

### Phase 5: Testing & Validation (Week 7-8)

1. **Unit tests for services**
2. **Integration tests for API**
3. **Load testing**
4. **Security audit**

---

## 8. Implementation Priorities

### Must Have (Before Mobile Launch)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Fix password hashing | Low | Critical | P0 |
| Fix CORS | Low | Critical | P0 |
| Remove hardcoded creds | Low | Critical | P0 |
| Add rate limiting | Medium | High | P0 |
| JWT authentication | Medium | High | P1 |
| Encrypt OAuth tokens | Medium | High | P1 |

### Should Have (For Maintainability)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Extract API routers | Medium | High | P1 |
| Create service layer | High | High | P1 |
| Database schema migration | High | High | P2 |
| Extract HTML to templates | Low | Medium | P2 |
| Add Alembic migrations | Medium | Medium | P2 |

### Nice to Have (Future)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Add OpenAPI docs | Low | Medium | P3 |
| Add comprehensive tests | High | High | P3 |
| Implement caching | Medium | Medium | P3 |
| Add observability (metrics) | Medium | Medium | P3 |

---

## Conclusion

The Spartan Coach codebase has grown organically and now exhibits significant technical debt. The monolithic `server.py` with embedded HTML, weak security practices, and primitive database schema are major concerns.

**Key Recommendations:**

1. **Immediate (Before Any Launch):** Fix security vulnerabilities - password hashing, CORS, rate limiting
2. **Short-term (2-4 weeks):** Extract modules, create service layer, proper database schema
3. **Medium-term (1-2 months):** Full refactor to proposed architecture

The proposed architecture provides:
- Clear separation of concerns
- Proper security practices
- Scalable database design
- Testable code structure
- Mobile-ready API

**Estimated Total Effort:** 6-8 weeks for complete refactor

---

*Document Version: 1.0*
*Date: December 2024*
*Author: Principal Architect Review*
