import asyncio
import os
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Request, Response, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
import httpx

# Import the new architecture
from spartan_phalanx.main import THE_SPARTAN
from calendar_service import CalendarService, get_workout_suggestions

load_dotenv()

# --- Authentication Configuration ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "demo_user")
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "SpartanWarrior2024!")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

# OAuth Setup
oauth = OAuth()
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_CLIENT_ID != "your_google_client_id_here":
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

retry_config=types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1, # Initial delay before first retry (in seconds)
    http_status_codes=[429, 500, 503, 504] # Retry on these HTTP errors
)

# --- Observability Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SpartanCoach")

def log_agent_interaction(session_id: str, user_input: str, agent_response: str):
    """Logs agent interactions to a JSONL file for observability."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "user_input": user_input,
        "agent_response": agent_response,
        "agent_name": THE_SPARTAN.name
    }
    with open("agent_logs.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    logger.info(f"Interaction logged for session {session_id}")

app = FastAPI(title="Spartan Coach API")

# Add session middleware (must be added before CORS)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Authentication Helpers ---
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from session."""
    return request.session.get("user")

def require_auth(request: Request) -> Dict[str, Any]:
    """Dependency that requires authentication."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# --- Login Page ---
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spartan Coach - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #09090b 0%, #18181b 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fafafa;
        }
        .login-container {
            background: rgba(24, 24, 27, 0.95);
            border: 1px solid rgba(63, 63, 70, 0.5);
            border-radius: 16px;
            padding: 48px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .logo {
            text-align: center;
            margin-bottom: 32px;
        }
        .logo-icon {
            font-size: 64px;
            margin-bottom: 16px;
        }
        .logo h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .logo p {
            color: #a1a1aa;
            margin-top: 8px;
        }
        .error-message {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 24px;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #a1a1aa;
            font-size: 14px;
            margin-bottom: 8px;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 14px 16px;
            background: rgba(39, 39, 42, 0.5);
            border: 1px solid rgba(63, 63, 70, 0.5);
            border-radius: 8px;
            color: #fafafa;
            font-size: 16px;
            transition: all 0.2s;
        }
        input:focus {
            outline: none;
            border-color: #ef4444;
            box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
        }
        .btn {
            width: 100%;
            padding: 14px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 12px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(239, 68, 68, 0.3);
        }
        .btn-google {
            background: white;
            color: #333;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        .btn-google:hover {
            background: #f5f5f5;
        }
        .btn-google svg {
            width: 20px;
            height: 20px;
        }
        .divider {
            display: flex;
            align-items: center;
            margin: 24px 0;
            color: #71717a;
        }
        .divider::before, .divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: rgba(63, 63, 70, 0.5);
        }
        .divider span {
            padding: 0 16px;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            margin-top: 24px;
            color: #71717a;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">⚔️</div>
            <h1>SPARTAN COACH</h1>
            <p>Your AI Fitness Commander</p>
        </div>

        __ERROR_HTML__

        <form method="POST" action="/auth/login">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="Enter your username" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter your password" required>
            </div>
            <button type="submit" class="btn btn-primary">Enter the Arena</button>
        </form>

        __GOOGLE_BTN__

        <div class="footer">
            <p>Prepare for transformation. No excuses.</p>
        </div>
    </div>
</body>
</html>
"""

@app.get("/login")
async def login_page(request: Request, error: str = None):
    """Render the login page."""
    # Check if already logged in
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)

    error_html = ""
    if error:
        error_html = f'<div class="error-message">{error}</div>'

    # Show Google button only if configured
    google_btn = ""
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID != "your_google_client_id_here":
        google_btn = '''
        <div class="divider"><span>or</span></div>
        <a href="/auth/google" class="btn btn-google">
            <svg viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Continue with Google
        </a>
        '''

    html = LOGIN_PAGE_HTML.replace("__ERROR_HTML__", error_html).replace("__GOOGLE_BTN__", google_btn)
    return HTMLResponse(content=html)

@app.get("/")
async def read_root(request: Request):
    """Serve main app or redirect to login."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse('static/index.html')

# --- Authentication Endpoints ---
@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle username/password login."""
    if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
        request.session["user"] = {
            "username": username,
            "name": "Alex",
            "email": f"{username}@spartancoach.local",
            "auth_method": "password"
        }
        logger.info(f"User {username} logged in via password")
        return RedirectResponse(url="/", status_code=302)

    return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=302)

@app.get("/auth/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID == "your_google_client_id_here":
        return RedirectResponse(url="/login?error=Google+OAuth+not+configured", status_code=302)

    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            return RedirectResponse(url="/login?error=Failed+to+get+user+info", status_code=302)

        request.session["user"] = {
            "username": user_info.get("email", "").split("@")[0],
            "name": user_info.get("name", "Warrior"),
            "email": user_info.get("email", ""),
            "picture": user_info.get("picture", ""),
            "auth_method": "google"
        }
        logger.info(f"User {user_info.get('email')} logged in via Google")
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        return RedirectResponse(url="/login?error=OAuth+failed", status_code=302)

@app.get("/auth/logout")
async def logout(request: Request):
    """Log out the current user."""
    user = get_current_user(request)
    if user:
        logger.info(f"User {user.get('username')} logged out")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/api/auth/me")
async def get_current_user_info(request: Request):
    """Get current authenticated user info."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check authentication status."""
    user = get_current_user(request)
    return {
        "authenticated": user is not None,
        "user": user
    }

# Initialize Session Service (Shared DB with CLI)
db_url = "sqlite:///./spartan_phalanx.db"
session_service = DatabaseSessionService(db_url=db_url)

APP_NAME = "SpartanCoach"
USER_ID = "Alex"  # Default user for this demo

# Default daily goals template (used for new sessions and before plan acceptance)
DEFAULT_GOALS_TEMPLATE = [
    {"id": "weight", "name": "Weight check-in", "category": "health"},
    {"id": "ice_wash", "name": "Ice face wash", "category": "health"},
    {"id": "medicine", "name": "Take medicine", "category": "health"},
    {"id": "abc_drink", "name": "ABC drink", "category": "nutrition"},
    {"id": "vitamins", "name": "Take vitamins", "category": "nutrition"},
    {"id": "nuts", "name": "Eat nuts", "category": "nutrition"},
    {"id": "water", "name": "Water (8 glasses)", "category": "hydration", "target": 8, "current": 0},
    {"id": "workout", "name": "Completed workout", "category": "exercise"},
    {"id": "diet", "name": "Completed diet plan", "category": "nutrition"},
    {"id": "standing", "name": "Standing breaks", "category": "movement"},
    {"id": "walking", "name": "10k Steps", "category": "movement", "target": 10000, "current": 0}
]

# Initialize Runner
runner = Runner(
    agent=THE_SPARTAN,
    app_name=APP_NAME,
    session_service=session_service,
)

# Data Models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    plan_accepted: bool = False

class OnboardRequest(BaseModel):
    name: str
    age: int
    height: float
    weight: float
    goal: str
    target_date: str

class StateResponse(BaseModel):
    user_name: str
    profile_locked: bool
    plan_accepted: bool
    master_plan: Dict[str, Any]
    daily_plan: Dict[str, Any]
    daily_goals: List[Dict[str, Any]]

class GoalCheckRequest(BaseModel):
    goal_id: str

class DailyGoalsResponse(BaseModel):
    date: str
    goals: List[Dict[str, Any]]
    completed_count: int
    total_count: int

class MetricsRequest(BaseModel):
    weight: Optional[float] = None
    sleep: Optional[float] = None
    recovery: Optional[int] = None

class MetricsResponse(BaseModel):
    date: str
    weight: Optional[float] = None
    sleep: Optional[float] = None
    recovery: Optional[int] = None

class HistoryEntry(BaseModel):
    date: str
    weight: Optional[float] = None
    sleep: Optional[float] = None
    recovery: Optional[int] = None
    completion_rate: int = 0

def get_or_create_session_id():
    existing_sessions = session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    if existing_sessions and len(existing_sessions.sessions) > 0:
        return existing_sessions.sessions[0].id
    
    # Initial state with enhanced schema for proactive coaching
    initial_state = {
        "user_name": "",
        "warrior_profile": {},
        "profile_locked": False,
        "master_plan": {},
        "plan_accepted": False,
        "daily_plan": {},
        "daily_goals": [],
        "daily_goals_template": DEFAULT_GOALS_TEMPLATE,
        "daily_logs": [],
        "daily_metrics": {},

        # Calendar Integration
        "google_calendar_token": None,
        "today_calendar_events": [],
        "calendar_gaps": [],
        "calendar_last_sync": None,

        # Water Tracking
        "water_intake": {
            "date": "",
            "glasses": 0,
            "last_logged": None
        },

        # Proactive Coaching
        "urgency_level": 0,
        "pending_reminders": [],
        "push_subscription": None,

        # Notification Settings
        "notification_settings": {
            "wake_time": "07:00",
            "sleep_time": "22:00",
            "enable_push": True
        }
    }
    new_session = session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state=initial_state,
    )
    return new_session.id

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = get_or_create_session_id()
    try:
        content = types.Content(role="user", parts=[types.Part(text=request.message)])
        final_response_text = ""

        # Run the agent asynchronously
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=content
        ):
            if event.is_final_response():
                if (
                    event.content
                    and event.content.parts
                    and hasattr(event.content.parts[0], "text")
                    and event.content.parts[0].text
                ):
                    final_response_text = event.content.parts[0].text.strip()

        # Log the interaction
        log_agent_interaction(session_id, request.message, final_response_text)

        # Check if this is a daily plan request and save the response
        daily_plan_keywords = ["daily plan", "today's plan", "plan for today", "daily battle", "workout for today", "today's workout", "what should i do today"]
        message_lower = request.message.lower()

        if any(keyword in message_lower for keyword in daily_plan_keywords):
            # Check if response looks like a plan (has workout/meal content)
            response_lower = final_response_text.lower()
            if any(word in response_lower for word in ["workout", "exercise", "meal", "breakfast", "lunch", "dinner", "sets", "reps"]):
                # Save as daily plan
                session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
                state = session.state
                today = datetime.now().strftime("%Y-%m-%d")
                if "daily_plan" not in state:
                    state["daily_plan"] = {}
                state["daily_plan"]["date"] = today
                state["daily_plan"]["plan_text"] = final_response_text
                state["daily_plan"]["generated_at"] = datetime.now().isoformat()
                force_update_state(session_id, state)
                logger.info(f"Daily plan saved from chat for {today}")

        # Get plan_accepted status to return to frontend
        session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        state = session.state
        plan_accepted = state.get("plan_accepted", False)

        return ChatResponse(response=final_response_text, plan_accepted=plan_accepted)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import json
import sqlalchemy
from sqlalchemy import text

# ...

def force_update_state(session_id: str, new_state: Dict[str, Any]):
    """Directly updates the session state in the database."""
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE sessions SET state = :state, update_time = CURRENT_TIMESTAMP WHERE id = :id"),
            {"state": json.dumps(new_state), "id": session_id}
        )
        conn.commit()

@app.post("/api/onboard")
async def onboard(request: OnboardRequest):
    session_id = get_or_create_session_id()
    

    # Directly update session state with profile and lock it
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    current_state = session.state
    current_state["warrior_profile"] = {
        "name": request.name,
        "age": request.age,
        "height": request.height,
        "weight": request.weight,
        "goal": request.goal,
        "target_date": request.target_date
    }
    current_state["profile_locked"] = True
    # Force update the database
    force_update_state(session_id, current_state)

    # Now ask the agent to create the Master Plan
    profile_text = (
        f"I have completed my profile setup. Here are my details:\n"
        f"Name: {request.name}, Age: {request.age}, Height: {request.height}cm, "
        f"Weight: {request.weight}kg, Goal: {request.goal}, Target Date: {request.target_date}\n\n"
        f"Please create my Master Plan."
    )
    
    content = types.Content(role="user", parts=[types.Part(text=profile_text)])
    final_response_text = ""
    
    async for event in runner.run_async(
        user_id=USER_ID, 
        session_id=session_id, 
        new_message=content
    ):
        if event.is_final_response():
             if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text.strip()

    # Save the master plan to session state
    # Extract the plan from the response and store it
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    current_state = session.state
    current_state["master_plan"] = {
        "plan_text": final_response_text,
        "created_at": request.target_date,
        "status": "pending_confirmation"
    }
    force_update_state(session_id, current_state)

    # Log the interaction
    log_agent_interaction(session_id, profile_text, final_response_text)

    return {"message": "Profile Submitted", "agent_response": final_response_text}

# ... (extract_metrics_from_response and upload_image remain same)

@app.post("/api/reset")
def reset_session():
    # Delete via session service
    existing_sessions = session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    for s in existing_sessions.sessions:
        session_service.delete_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=s.id
        )

    # Also directly delete from database to ensure clean slate
    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sessions WHERE app_name = :app AND user_id = :user"),
                     {"app": APP_NAME, "user": USER_ID})
        conn.commit()

    return {"message": "Session reset. PREPARE FOR GLORY!"}

@app.get("/api/state", response_model=StateResponse)
async def get_state():
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state
    return StateResponse(
        user_name=state.get("user_name", ""),
        profile_locked=state.get("profile_locked", False),
        plan_accepted=state.get("plan_accepted", False),
        master_plan=state.get("master_plan", {}),
        daily_plan=state.get("daily_plan", {}),
        daily_goals=state.get("daily_goals", [])
    )

@app.post("/api/accept-plan")
async def accept_plan():
    """Accept the master plan, generate daily plan, and initialize daily goals."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    if not state.get("master_plan"):
        raise HTTPException(status_code=400, detail="No master plan to accept")

    # Set plan as accepted
    state["plan_accepted"] = True

    # Initialize daily goals from template
    today = datetime.now().strftime("%Y-%m-%d")
    state["daily_goals"] = [
        {**goal, "completed": False}
        for goal in state.get("daily_goals_template", [])
    ]
    state["daily_plan"] = {"date": today, "generated_at": datetime.now().isoformat()}
    force_update_state(session_id, state)

    # Generate actual daily plan by asking the agent
    try:
        daily_plan_prompt = (
            f"I have accepted my Master Plan. Today is {today}. "
            f"Please generate my DAILY BATTLE PLAN for today with:\n"
            f"1. Specific workout exercises with sets and reps\n"
            f"2. Specific meals with foods and portions\n"
            f"3. Timing recommendations\n"
            f"Format it as a clear, actionable daily schedule."
        )

        content = types.Content(role="user", parts=[types.Part(text=daily_plan_prompt)])
        daily_plan_text = ""

        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=content
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    daily_plan_text = event.content.parts[0].text.strip()

        # Save the daily plan
        session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        state = session.state
        state["daily_plan"]["plan_text"] = daily_plan_text
        force_update_state(session_id, state)

        log_agent_interaction(session_id, daily_plan_prompt, daily_plan_text)

    except Exception as e:
        logger.error(f"Error generating daily plan: {e}")

    return {"message": "Plan accepted! Your transformation begins.", "plan_accepted": True}

@app.get("/api/daily-goals", response_model=DailyGoalsResponse)
async def get_daily_goals():
    """Get today's daily goals with completion status."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    goals = state.get("daily_goals", [])

    # If no goals yet, use the template to show placeholder goals
    if not goals:
        template = state.get("daily_goals_template", DEFAULT_GOALS_TEMPLATE)
        today = datetime.now().strftime("%Y-%m-%d")
        goals = [
            {**goal, "completed": False, "date": today}
            for goal in template
        ]

    # Migrate old goal IDs to new ones (pushups/pullups -> workout/diet)
    goal_ids = [g.get("id") for g in goals]
    needs_migration = "pushups" in goal_ids or "pullups" in goal_ids

    if needs_migration:
        new_goals = []
        for goal in goals:
            if goal.get("id") == "pushups":
                new_goals.append({
                    "id": "workout",
                    "name": "Completed workout",
                    "category": "exercise",
                    "completed": goal.get("completed", False)
                })
            elif goal.get("id") == "pullups":
                new_goals.append({
                    "id": "diet",
                    "name": "Completed diet plan",
                    "category": "nutrition",
                    "completed": goal.get("completed", False)
                })
            else:
                new_goals.append(goal)
        goals = new_goals
        state["daily_goals"] = goals
        force_update_state(session_id, state)

    completed = sum(1 for g in goals if g.get("completed", False))

    return DailyGoalsResponse(
        date=datetime.now().strftime("%Y-%m-%d"),
        goals=goals,
        completed_count=completed,
        total_count=len(goals)
    )

@app.post("/api/goals/check")
async def check_goal(request: GoalCheckRequest):
    """Mark a daily goal as completed."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    goals = state.get("daily_goals", [])

    # If no goals yet, initialize from template
    if not goals:
        template = state.get("daily_goals_template", DEFAULT_GOALS_TEMPLATE)
        today = datetime.now().strftime("%Y-%m-%d")
        goals = [
            {**goal, "completed": False, "date": today}
            for goal in template
        ]

    goal_found = False

    for goal in goals:
        if goal["id"] == request.goal_id:
            goal["completed"] = True
            goal_found = True
            break

    if not goal_found:
        raise HTTPException(status_code=404, detail=f"Goal '{request.goal_id}' not found")

    state["daily_goals"] = goals
    force_update_state(session_id, state)

    completed = sum(1 for g in goals if g.get("completed", False))
    return {
        "message": f"Goal '{request.goal_id}' checked off!",
        "completed_count": completed,
        "total_count": len(goals)
    }

@app.post("/api/goals/uncheck")
async def uncheck_goal(request: GoalCheckRequest):
    """Unmark a daily goal."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    goals = state.get("daily_goals", [])

    # If no goals yet, initialize from template
    if not goals:
        template = state.get("daily_goals_template", DEFAULT_GOALS_TEMPLATE)
        today = datetime.now().strftime("%Y-%m-%d")
        goals = [
            {**goal, "completed": False, "date": today}
            for goal in template
        ]

    for goal in goals:
        if goal["id"] == request.goal_id:
            goal["completed"] = False
            break

    state["daily_goals"] = goals
    force_update_state(session_id, state)

    return {"message": f"Goal '{request.goal_id}' unchecked."}

@app.post("/api/metrics")
async def save_metrics(request: MetricsRequest):
    """Save daily metrics (weight, sleep, recovery)."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")

    # Get or create today's metrics
    daily_metrics = state.get("daily_metrics", {})
    if today not in daily_metrics:
        daily_metrics[today] = {}

    # Update metrics
    if request.weight is not None:
        daily_metrics[today]["weight"] = request.weight
    if request.sleep is not None:
        daily_metrics[today]["sleep"] = request.sleep
    if request.recovery is not None:
        daily_metrics[today]["recovery"] = request.recovery

    state["daily_metrics"] = daily_metrics
    force_update_state(session_id, state)

    return {"message": "Metrics logged! Keep pushing, warrior!", "date": today}

@app.get("/api/metrics/today", response_model=MetricsResponse)
async def get_today_metrics():
    """Get today's metrics."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")
    daily_metrics = state.get("daily_metrics", {})
    today_metrics = daily_metrics.get(today, {})

    return MetricsResponse(
        date=today,
        weight=today_metrics.get("weight"),
        sleep=today_metrics.get("sleep"),
        recovery=today_metrics.get("recovery")
    )

@app.get("/api/history", response_model=List[HistoryEntry])
async def get_history():
    """Get historical data for charts (last 30 days)."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    daily_metrics = state.get("daily_metrics", {})
    daily_logs = state.get("daily_logs", [])

    # Create a map of completion rates from daily_logs
    completion_map = {}
    for log in daily_logs:
        date = log.get("date")
        rate_str = log.get("completion_rate", "0/0")
        try:
            completed, total = map(int, rate_str.split("/"))
            completion_map[date] = int((completed / total) * 100) if total > 0 else 0
        except:
            completion_map[date] = 0

    # Generate last 30 days
    history = []
    from datetime import timedelta
    today = datetime.now()

    for i in range(29, -1, -1):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        metrics = daily_metrics.get(date, {})
        completion = completion_map.get(date, 0)

        # Only include days that have some data
        if metrics or date in completion_map:
            history.append(HistoryEntry(
                date=date,
                weight=metrics.get("weight"),
                sleep=metrics.get("sleep"),
                recovery=metrics.get("recovery"),
                completion_rate=completion
            ))

    return history

@app.get("/api/daily-plan")
async def get_daily_plan():
    """Get the current daily plan (specific workout/meals for today)."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    daily_plan = state.get("daily_plan", {})

    # Only return if we have an actual daily plan
    if daily_plan.get("plan_text"):
        return {
            "date": daily_plan.get("date"),
            "plan_text": daily_plan.get("plan_text")
        }

    raise HTTPException(status_code=404, detail="No daily plan available. Ask the coach for today's plan!")

@app.get("/api/master-plan")
async def get_master_plan():
    """Get the master transformation plan."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    master_plan = state.get("master_plan", {})

    if master_plan.get("plan_text"):
        return {
            "created_at": master_plan.get("created_at"),
            "plan_text": master_plan.get("plan_text")
        }

    raise HTTPException(status_code=404, detail="No master plan available")

@app.post("/api/simulate-journey")
async def simulate_journey():
    """Simulate historical data for testing the goal journey."""
    import random
    from datetime import timedelta

    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    # Get goal details
    profile = state.get("warrior_profile", {})
    start_weight = profile.get("weight", 80)
    goal_text = profile.get("goal", "Lose 5kg")

    # Parse weight loss goal
    target_loss = 5  # Default
    if "lose" in goal_text.lower():
        try:
            target_loss = float(''.join(filter(lambda x: x.isdigit() or x == '.', goal_text)))
        except:
            target_loss = 5

    target_weight = start_weight - target_loss

    # Generate 77 days of historical data (simulating the journey)
    today = datetime.now()
    daily_logs = []
    daily_metrics = {}

    for i in range(77, -1, -1):
        date = (today - timedelta(days=i))
        date_str = date.strftime("%Y-%m-%d")

        # Calculate progressive weight loss (with some variation)
        progress = (77 - i) / 77  # 0 to 1
        weight_loss = target_loss * progress
        daily_weight = round(start_weight - weight_loss + random.uniform(-0.3, 0.3), 1)

        # Ensure final weight hits target
        if i == 0:
            daily_weight = target_weight

        # Random sleep (6.5-8.5 hours)
        sleep = round(random.uniform(6.5, 8.5), 1)

        # Recovery (improves over time, 60-95%)
        base_recovery = 65 + (progress * 20)  # Improves from 65% to 85%
        recovery = min(100, int(base_recovery + random.randint(-10, 10)))

        # Goal completion (improves over time)
        base_completion = 50 + (progress * 40)  # Improves from 50% to 90%
        num_goals = 11
        completed_goals = min(num_goals, int((base_completion / 100) * num_goals) + random.randint(-2, 2))
        completed_goals = max(0, completed_goals)

        # Store metrics
        daily_metrics[date_str] = {
            "weight": daily_weight,
            "sleep": sleep,
            "recovery": recovery
        }

        # Store logs
        goal_ids = ["weight", "ice_wash", "medicine", "abc_drink", "vitamins", "nuts", "water", "pushups", "pullups", "standing", "walking"]
        completed_goal_ids = random.sample(goal_ids, completed_goals)

        daily_logs.append({
            "date": date_str,
            "goals_completed": completed_goal_ids,
            "completion_rate": f"{completed_goals}/{num_goals}",
            "weight": daily_weight,
            "sleep": sleep,
            "recovery": recovery,
            "archived_at": date.isoformat()
        })

    state["daily_metrics"] = daily_metrics
    state["daily_logs"] = daily_logs[-30:]  # Keep last 30 for display

    force_update_state(session_id, state)

    return {
        "message": "Journey simulated! 77 days of data generated.",
        "start_weight": start_weight,
        "current_weight": target_weight,
        "weight_lost": target_loss,
        "days_simulated": 78
    }

@app.post("/api/complete-goal")
async def complete_goal():
    """Mark the goal as accomplished and generate summary."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    profile = state.get("warrior_profile", {})
    daily_metrics = state.get("daily_metrics", {})
    daily_logs = state.get("daily_logs", [])

    # Calculate journey stats
    start_weight = profile.get("weight", 80)
    weights = [m.get("weight") for m in daily_metrics.values() if m.get("weight")]
    current_weight = weights[-1] if weights else start_weight
    weight_lost = round(start_weight - current_weight, 1)

    # Average stats
    sleeps = [m.get("sleep") for m in daily_metrics.values() if m.get("sleep")]
    recoveries = [m.get("recovery") for m in daily_metrics.values() if m.get("recovery")]
    avg_sleep = round(sum(sleeps) / len(sleeps), 1) if sleeps else 0
    avg_recovery = round(sum(recoveries) / len(recoveries)) if recoveries else 0

    # Completion stats
    total_days = len(daily_logs)
    perfect_days = sum(1 for log in daily_logs if log.get("completion_rate", "").startswith(f"{11}/"))

    # Mark goal as complete
    state["goal_completed"] = True
    state["goal_completed_at"] = datetime.now().isoformat()
    state["journey_summary"] = {
        "start_weight": start_weight,
        "final_weight": current_weight,
        "weight_lost": weight_lost,
        "total_days": total_days,
        "perfect_days": perfect_days,
        "avg_sleep": avg_sleep,
        "avg_recovery": avg_recovery,
        "goal": profile.get("goal", ""),
        "name": profile.get("name", "Warrior")
    }

    force_update_state(session_id, state)

    return {
        "message": "GOAL ACCOMPLISHED! You are a true Spartan!",
        "summary": state["journey_summary"]
    }

@app.get("/api/journey-status")
async def get_journey_status():
    """Get current journey status including completion."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    profile = state.get("warrior_profile", {})
    daily_metrics = state.get("daily_metrics", {})

    # Calculate current progress
    start_weight = profile.get("weight", 80)
    weights = [m.get("weight") for m in daily_metrics.values() if m.get("weight")]
    current_weight = weights[-1] if weights else start_weight

    goal_text = profile.get("goal", "Lose 5kg")
    target_loss = 5
    if "lose" in goal_text.lower():
        try:
            target_loss = float(''.join(filter(lambda x: x.isdigit() or x == '.', goal_text)))
        except:
            target_loss = 5

    weight_lost = round(start_weight - current_weight, 1)
    progress_percent = min(100, round((weight_lost / target_loss) * 100))

    return {
        "goal_completed": state.get("goal_completed", False),
        "journey_summary": state.get("journey_summary"),
        "start_weight": start_weight,
        "current_weight": current_weight,
        "target_weight": start_weight - target_loss,
        "weight_lost": weight_lost,
        "target_loss": target_loss,
        "progress_percent": progress_percent
    }


# ═══════════════════════════════════════════════════════════════
# WATER TRACKING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/water/log")
async def log_water():
    """Log a glass of water (+1)."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")
    water_intake = state.get("water_intake", {"date": "", "glasses": 0, "last_logged": None})

    # Reset if new day
    if water_intake.get("date") != today:
        water_intake = {"date": today, "glasses": 0, "last_logged": None}

    water_intake["glasses"] = min(water_intake["glasses"] + 1, 12)  # Cap at 12
    water_intake["last_logged"] = datetime.now().isoformat()

    state["water_intake"] = water_intake

    # Also update the water goal in daily_goals
    goals = state.get("daily_goals", [])
    for goal in goals:
        if goal.get("id") == "water":
            goal["current"] = water_intake["glasses"]
            if water_intake["glasses"] >= goal.get("target", 8):
                goal["completed"] = True
            break
    state["daily_goals"] = goals

    force_update_state(session_id, state)

    remaining = max(0, 8 - water_intake["glasses"])
    message = "HYDRATION LOGGED!" if remaining > 0 else "HYDRATION GOAL COMPLETE! OUTSTANDING!"

    return {
        "message": message,
        "glasses": water_intake["glasses"],
        "remaining": remaining,
        "target": 8
    }


@app.get("/api/water/status")
async def get_water_status():
    """Get current water intake status."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")
    water_intake = state.get("water_intake", {"date": "", "glasses": 0, "last_logged": None})

    # Reset if new day
    if water_intake.get("date") != today:
        water_intake = {"date": today, "glasses": 0, "last_logged": None}

    glasses = water_intake.get("glasses", 0)
    last_logged = water_intake.get("last_logged")

    # Calculate hours since last water
    hours_since_last = None
    needs_reminder = False
    if last_logged:
        last_time = datetime.fromisoformat(last_logged)
        hours_since_last = round((datetime.now() - last_time).total_seconds() / 3600, 1)
        needs_reminder = hours_since_last >= 2
    else:
        needs_reminder = True  # Never logged today

    return {
        "date": today,
        "glasses": glasses,
        "target": 8,
        "remaining": max(0, 8 - glasses),
        "last_logged": last_logged,
        "hours_since_last": hours_since_last,
        "needs_reminder": needs_reminder,
        "completed": glasses >= 8
    }


# ═══════════════════════════════════════════════════════════════
# STEP TRACKING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class StepLogRequest(BaseModel):
    steps: int


@app.post("/api/steps/log")
async def log_steps(request: StepLogRequest):
    """Log step count (manual entry)."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")
    daily_metrics = state.get("daily_metrics", {})

    if today not in daily_metrics:
        daily_metrics[today] = {}

    daily_metrics[today]["steps"] = request.steps
    daily_metrics[today]["steps_logged_at"] = datetime.now().isoformat()
    state["daily_metrics"] = daily_metrics

    # Update walking goal in daily_goals
    goals = state.get("daily_goals", [])
    for goal in goals:
        if goal.get("id") == "walking":
            goal["current"] = request.steps
            if request.steps >= goal.get("target", 10000):
                goal["completed"] = True
            break
    state["daily_goals"] = goals

    force_update_state(session_id, state)

    target = 10000
    remaining = max(0, target - request.steps)
    progress_percent = min(100, round((request.steps / target) * 100))

    if request.steps >= target:
        message = "10K STEPS CONQUERED! OUTSTANDING WORK, WARRIOR!"
    elif request.steps >= 7500:
        message = f"SOLID PROGRESS! {remaining:,} steps to go. FINISH STRONG!"
    elif request.steps >= 5000:
        message = f"HALFWAY THERE! {remaining:,} steps remaining. KEEP MOVING!"
    else:
        message = f"TIME TO MOVE! {remaining:,} steps to hit your target."

    return {
        "message": message,
        "steps": request.steps,
        "target": target,
        "remaining": remaining,
        "progress_percent": progress_percent,
        "completed": request.steps >= target
    }


@app.get("/api/steps/status")
async def get_steps_status():
    """Get current step count status."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    today = datetime.now().strftime("%Y-%m-%d")
    daily_metrics = state.get("daily_metrics", {})
    today_metrics = daily_metrics.get(today, {})

    steps = today_metrics.get("steps", 0)
    target = 10000
    remaining = max(0, target - steps)

    # Calculate time-based urgency
    current_hour = datetime.now().hour
    is_evening = current_hour >= 17

    # Determine urgency level for steps
    if steps >= target:
        urgency = "completed"
        urgency_message = "MISSION ACCOMPLISHED!"
    elif is_evening and steps < 5000:
        urgency = "critical"
        urgency_message = f"CRITICAL: {remaining:,} steps needed before day ends!"
    elif is_evening and steps < 7500:
        urgency = "high"
        urgency_message = f"Evening crunch! {remaining:,} steps to go. MOVE NOW!"
    elif steps < 3000 and current_hour >= 12:
        urgency = "medium"
        urgency_message = f"Behind schedule. {remaining:,} steps remaining."
    else:
        urgency = "normal"
        urgency_message = f"{remaining:,} steps to target."

    # Activity suggestions based on remaining steps
    suggestions = []
    if remaining > 0:
        if remaining >= 5000:
            suggestions = [
                {"activity": "45-min walk", "steps": "~4,500"},
                {"activity": "30-min jog", "steps": "~4,000"},
                {"activity": "Basketball/Tennis (1hr)", "steps": "~5,000+"}
            ]
        elif remaining >= 2500:
            suggestions = [
                {"activity": "25-min walk", "steps": "~2,500"},
                {"activity": "15-min jog", "steps": "~2,000"},
                {"activity": "Take stairs + walk breaks", "steps": "~2,000"}
            ]
        else:
            suggestions = [
                {"activity": "15-min walk", "steps": "~1,500"},
                {"activity": "Walk while on calls", "steps": "~1,000"},
                {"activity": "Evening stroll", "steps": "~1,500"}
            ]

    return {
        "date": today,
        "steps": steps,
        "target": target,
        "remaining": remaining,
        "progress_percent": min(100, round((steps / target) * 100)),
        "completed": steps >= target,
        "urgency": urgency,
        "urgency_message": urgency_message,
        "suggestions": suggestions,
        "logged_at": today_metrics.get("steps_logged_at")
    }


# ═══════════════════════════════════════════════════════════════
# CALENDAR INTEGRATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/calendar/sync")
async def sync_calendar():
    """Sync calendar and find available gaps for workouts."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    calendar_token = state.get("google_calendar_token")
    notification_settings = state.get("notification_settings", {})
    wake_time = notification_settings.get("wake_time", "07:00")
    sleep_time = notification_settings.get("sleep_time", "22:00")

    if not calendar_token:
        # Return mock data if no calendar connected
        now = datetime.now()
        mock_gaps = []

        # Generate realistic gaps based on time of day
        current_hour = now.hour
        if current_hour < 12:
            mock_gaps.append({
                "start": now.replace(minute=0, second=0).isoformat(),
                "end": (now + timedelta(hours=1)).replace(minute=0, second=0).isoformat(),
                "duration_minutes": 60,
                "time_of_day": "morning",
                "next_event": "Work block"
            })
        elif current_hour < 17:
            mock_gaps.append({
                "start": now.replace(minute=0, second=0).isoformat(),
                "end": (now + timedelta(minutes=30)).isoformat(),
                "duration_minutes": 30,
                "time_of_day": "afternoon",
                "next_event": "Meeting"
            })
        else:
            mock_gaps.append({
                "start": now.replace(minute=0, second=0).isoformat(),
                "end": (now + timedelta(hours=2)).isoformat(),
                "duration_minutes": 120,
                "time_of_day": "evening",
                "next_event": "End of day"
            })

        state["calendar_gaps"] = mock_gaps
        state["calendar_last_sync"] = now.isoformat()
        force_update_state(session_id, state)

        return {
            "message": "Calendar not connected. Using estimated gaps.",
            "connected": False,
            "gaps": mock_gaps,
            "total_free_time": sum(g["duration_minutes"] for g in mock_gaps)
        }

    try:
        # Use actual calendar service
        calendar_service = CalendarService(credentials=calendar_token)
        events = calendar_service.get_today_events()
        gaps = calendar_service.find_gaps(events, wake_time, sleep_time)

        state["today_calendar_events"] = events
        state["calendar_gaps"] = gaps
        state["calendar_last_sync"] = datetime.now().isoformat()
        force_update_state(session_id, state)

        return {
            "message": "Calendar synced successfully!",
            "connected": True,
            "events_count": len(events),
            "gaps": gaps,
            "total_free_time": sum(g["duration_minutes"] for g in gaps)
        }

    except Exception as e:
        logger.error(f"Calendar sync error: {e}")
        raise HTTPException(status_code=500, detail=f"Calendar sync failed: {str(e)}")


@app.get("/api/calendar/gaps")
async def get_calendar_gaps():
    """Get today's available time gaps with workout suggestions."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    gaps = state.get("calendar_gaps", [])
    last_sync = state.get("calendar_last_sync")

    # Find current gap (if any)
    now = datetime.now()
    current_gap = None
    next_gap = None

    for gap in gaps:
        gap_start = datetime.fromisoformat(gap["start"])
        gap_end = datetime.fromisoformat(gap["end"])

        if gap_start <= now <= gap_end:
            remaining = int((gap_end - now).total_seconds() / 60)
            current_gap = {
                **gap,
                "remaining_minutes": remaining,
                "suggestions": get_workout_suggestions(remaining, gap["time_of_day"])
            }
        elif gap_start > now and not next_gap:
            minutes_until = int((gap_start - now).total_seconds() / 60)
            next_gap = {
                **gap,
                "minutes_until": minutes_until,
                "suggestions": get_workout_suggestions(gap["duration_minutes"], gap["time_of_day"])
            }

    return {
        "last_sync": last_sync,
        "total_gaps": len(gaps),
        "gaps": gaps,
        "current_gap": current_gap,
        "next_gap": next_gap,
        "total_free_time": sum(g["duration_minutes"] for g in gaps)
    }


# ═══════════════════════════════════════════════════════════════
# NOTIFICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]


@app.post("/api/push/subscribe")
async def subscribe_push(subscription: PushSubscription):
    """Store push notification subscription."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    state["push_subscription"] = subscription.dict()
    force_update_state(session_id, state)

    return {"message": "Push notifications enabled! Prepare for orders."}


@app.get("/api/notifications")
async def get_notifications():
    """Get pending notifications/reminders."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    reminders = state.get("pending_reminders", [])

    return {
        "count": len(reminders),
        "reminders": reminders
    }


@app.post("/api/notifications/clear")
async def clear_notifications():
    """Clear all pending notifications."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    state["pending_reminders"] = []
    force_update_state(session_id, state)

    return {"message": "Notifications cleared."}


class NotificationSettings(BaseModel):
    wake_time: Optional[str] = None
    sleep_time: Optional[str] = None
    enable_push: Optional[bool] = None


@app.post("/api/notifications/settings")
async def update_notification_settings(settings: NotificationSettings):
    """Update notification settings."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    current_settings = state.get("notification_settings", {
        "wake_time": "07:00",
        "sleep_time": "22:00",
        "enable_push": True
    })

    if settings.wake_time:
        current_settings["wake_time"] = settings.wake_time
    if settings.sleep_time:
        current_settings["sleep_time"] = settings.sleep_time
    if settings.enable_push is not None:
        current_settings["enable_push"] = settings.enable_push

    state["notification_settings"] = current_settings
    force_update_state(session_id, state)

    return {"message": "Settings updated.", "settings": current_settings}


@app.get("/api/notifications/settings")
async def get_notification_settings():
    """Get current notification settings."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    return state.get("notification_settings", {
        "wake_time": "07:00",
        "sleep_time": "22:00",
        "enable_push": True
    })


# ═══════════════════════════════════════════════════════════════
# URGENCY STATUS ENDPOINT
# ═══════════════════════════════════════════════════════════════

@app.get("/api/urgency")
async def get_urgency_status():
    """Get current urgency level and factors."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    # Calculate urgency based on multiple factors
    now = datetime.now()
    current_hour = now.hour
    notification_settings = state.get("notification_settings", {})
    sleep_time = notification_settings.get("sleep_time", "22:00")
    sleep_hour = int(sleep_time.split(":")[0])

    # Hours remaining in day
    hours_remaining = max(0, sleep_hour - current_hour)

    # Goal progress
    goals = state.get("daily_goals", [])
    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.get("completed", False))
    completion_percent = (completed_goals / total_goals * 100) if total_goals > 0 else 0

    # Water status
    water_intake = state.get("water_intake", {})
    water_glasses = water_intake.get("glasses", 0)

    # Step status
    today = now.strftime("%Y-%m-%d")
    daily_metrics = state.get("daily_metrics", {})
    steps = daily_metrics.get(today, {}).get("steps", 0)

    # Calculate urgency level (0-3)
    urgency_factors = []
    urgency_level = 0

    # Time-based urgency
    if hours_remaining <= 2:
        urgency_level += 1
        urgency_factors.append(f"Only {hours_remaining}h remaining")

    # Goal completion urgency
    if completion_percent < 50 and current_hour >= 15:
        urgency_level += 1
        urgency_factors.append(f"Goals only {completion_percent:.0f}% complete")

    # Water urgency
    if water_glasses < 4 and current_hour >= 14:
        urgency_level += 1
        urgency_factors.append(f"Only {water_glasses}/8 glasses water")

    # Step urgency (evening)
    if steps < 5000 and current_hour >= 17:
        urgency_level += 1
        urgency_factors.append(f"Only {steps:,}/10,000 steps")

    urgency_level = min(3, urgency_level)

    labels = ["GREEN", "YELLOW", "ORANGE", "RED"]
    messages = [
        "ON TRACK. Maintain discipline.",
        "ATTENTION NEEDED. Pick up the pace.",
        "FALLING BEHIND. Immediate action required.",
        "CRITICAL. Execute NOW or fail the day."
    ]

    return {
        "level": urgency_level,
        "label": labels[urgency_level],
        "message": messages[urgency_level],
        "factors": urgency_factors,
        "hours_remaining": hours_remaining,
        "goals_completed": completed_goals,
        "goals_total": total_goals,
        "completion_percent": round(completion_percent),
        "water_glasses": water_glasses,
        "steps": steps
    }


@app.post("/api/trigger-checkin")
async def trigger_checkin():
    """Manually trigger a proactive check-in for testing."""
    try:
        await proactive_checkin()
        return {"message": "Check-in triggered successfully!"}
    except Exception as e:
        logger.error(f"Error triggering check-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Scheduling ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def proactive_checkin():
    """
    AGGRESSIVE proactive check-in triggered every 2 hours.
    Syncs calendar, evaluates goals, and generates commanding reminders.
    """
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    if not state.get("plan_accepted"):
        logger.info("Plan not accepted yet, skipping proactive check-in.")
        return

    now = datetime.now()
    current_hour = now.hour
    logger.info(f"Executing proactive check-in at {now.strftime('%H:%M')} for session {session_id}")

    # Gather current status for context
    goals = state.get("daily_goals", [])
    completed = sum(1 for g in goals if g.get("completed", False))
    total = len(goals)
    incomplete_goals = [g["name"] for g in goals if not g.get("completed", False)]
    completion_percent = (completed / total * 100) if total > 0 else 0

    water_intake = state.get("water_intake", {})
    water_glasses = water_intake.get("glasses", 0)
    water_last_logged = water_intake.get("last_logged")
    hours_since_water = None
    if water_last_logged:
        try:
            last_time = datetime.fromisoformat(water_last_logged)
            hours_since_water = round((now - last_time).total_seconds() / 3600, 1)
        except:
            pass

    today = now.strftime("%Y-%m-%d")
    daily_metrics = state.get("daily_metrics", {})
    steps = daily_metrics.get(today, {}).get("steps", 0)

    # Calculate urgency level
    hours_remaining = max(0, 22 - current_hour)
    urgency_level = 0
    urgency_factors = []

    if hours_remaining <= 2:
        urgency_level += 1
        urgency_factors.append(f"Only {hours_remaining}h remaining")
    if completion_percent < 50 and current_hour >= 15:
        urgency_level += 1
        urgency_factors.append(f"Goals only {completion_percent:.0f}% complete")
    if water_glasses < 4 and current_hour >= 14:
        urgency_level += 1
        urgency_factors.append(f"Only {water_glasses}/8 glasses water")
    if steps < 5000 and current_hour >= 17:
        urgency_level += 1
        urgency_factors.append(f"Only {steps:,}/10,000 steps")

    urgency_level = min(3, urgency_level)
    urgency_labels = ["GREEN", "YELLOW", "ORANGE", "RED"]
    urgency_tones = ["encouraging but firm", "firm and urgent", "aggressive and demanding", "MAXIMUM INTENSITY"]

    # Get calendar gaps
    calendar_gaps = state.get("calendar_gaps", [])
    current_gap = None
    for gap in calendar_gaps:
        try:
            gap_start = datetime.fromisoformat(gap["start"])
            gap_end = datetime.fromisoformat(gap["end"])
            if gap_start <= now <= gap_end:
                remaining = int((gap_end - now).total_seconds() / 60)
                current_gap = {"duration": remaining, "time_of_day": gap.get("time_of_day", "afternoon")}
                break
        except:
            continue

    # Build time of day context
    time_of_day = "morning" if current_hour < 12 else "afternoon" if current_hour < 17 else "evening"

    # Build comprehensive check-in prompt with ALL data
    checkin_prompt = f"""SYSTEM TRIGGER: PROACTIVE CHECK-IN - {time_of_day.upper()} ({now.strftime('%I:%M %p')})

══════════════════════════════════════════════════════════════
📊 WARRIOR STATUS REPORT
══════════════════════════════════════════════════════════════

GOALS: {completed}/{total} completed ({completion_percent:.0f}%)
INCOMPLETE: {', '.join(incomplete_goals[:6]) if incomplete_goals else 'NONE - ALL COMPLETE!'}

💧 WATER: {water_glasses}/8 glasses
   Last logged: {f'{hours_since_water:.1f} hours ago' if hours_since_water else 'NEVER TODAY'}
   {"⚠️ NEEDS HYDRATION REMINDER!" if (hours_since_water is None or hours_since_water >= 2) and water_glasses < 8 else ""}

👟 STEPS: {steps:,}/10,000 ({round(steps/10000*100)}%)
   Remaining: {max(0, 10000-steps):,} steps
   {"⚠️ EVENING STEP CRUNCH!" if time_of_day == "evening" and steps < 7000 else ""}

⏰ TIME: {hours_remaining} hours until end of day (10 PM)

══════════════════════════════════════════════════════════════
🚨 URGENCY LEVEL: {urgency_level} ({urgency_labels[urgency_level]})
══════════════════════════════════════════════════════════════
Factors: {', '.join(urgency_factors) if urgency_factors else 'None - on track'}
Recommended tone: {urgency_tones[urgency_level]}

{f'''
📅 CURRENT TIME GAP AVAILABLE: {current_gap["duration"]} minutes
Suggested activity: {"Push-ups, burpees, energizing exercises" if current_gap["time_of_day"] == "morning" else "Standing break, stretches, quick walk" if current_gap["time_of_day"] == "afternoon" else "Walking, jogging, sports to hit step goal"}
''' if current_gap else ''}
══════════════════════════════════════════════════════════════
YOUR ORDERS: Based on the status above, issue COMMANDING orders to this warrior.
- DO NOT use any tools - all data is provided above
- Be {urgency_tones[urgency_level]}
- Address the most critical gaps first
- End with a specific action they should take RIGHT NOW
══════════════════════════════════════════════════════════════"""

    content = types.Content(role="user", parts=[types.Part(text=checkin_prompt)])
    final_response_text = ""

    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                final_response_text = event.content.parts[0].text.strip()

        # Store as pending reminder
        session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        state = session.state
        reminders = state.get("pending_reminders", [])
        reminders.append({
            "id": f"checkin_{now.strftime('%H%M')}",
            "type": "proactive_checkin",
            "time": now.isoformat(),
            "message": final_response_text[:500],  # Truncate for storage
            "read": False
        })
        state["pending_reminders"] = reminders[-10:]  # Keep last 10
        force_update_state(session_id, state)

        log_agent_interaction(session_id, f"PROACTIVE_CHECKIN_{time_of_day.upper()}", final_response_text)
        logger.info(f"Proactive check-in complete. Response stored as reminder.")

    except Exception as e:
        logger.error(f"Error during proactive check-in: {e}")


async def water_reminder():
    """Check water intake and send reminder if needed."""
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state

    if not state.get("plan_accepted"):
        return

    water_intake = state.get("water_intake", {})
    glasses = water_intake.get("glasses", 0)
    last_logged = water_intake.get("last_logged")

    # Check if reminder needed
    needs_reminder = False
    if glasses < 8:
        if last_logged:
            last_time = datetime.fromisoformat(last_logged)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            needs_reminder = hours_since >= 2
        else:
            needs_reminder = True

    if needs_reminder:
        now = datetime.now()
        reminders = state.get("pending_reminders", [])
        reminders.append({
            "id": f"water_{now.strftime('%H%M')}",
            "type": "water_reminder",
            "time": now.isoformat(),
            "message": f"💧 HYDRATION CHECK! You have {glasses}/8 glasses. DRINK WATER NOW, WARRIOR!",
            "read": False
        })
        state["pending_reminders"] = reminders[-10:]
        force_update_state(session_id, state)
        logger.info(f"Water reminder sent: {glasses}/8 glasses logged")


async def scheduled_checkin():
    """Legacy check-in function - redirects to proactive_checkin."""
    await proactive_checkin()

async def midnight_reset():
    """Reset daily goals at midnight and archive previous day's progress."""
    try:
        session_id = get_or_create_session_id()
        session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        state = session.state

        if not state.get("plan_accepted"):
            logger.info("Plan not accepted yet, skipping midnight reset.")
            return

        # Archive previous day's goals and metrics
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        previous_goals = state.get("daily_goals", [])
        completed_count = sum(1 for g in previous_goals if g.get("completed", False))

        # Get yesterday's metrics
        daily_metrics = state.get("daily_metrics", {})
        yesterday_metrics = daily_metrics.get(yesterday, {})

        # Add to daily logs
        daily_logs = state.get("daily_logs", [])
        daily_logs.append({
            "date": yesterday,
            "goals_completed": [g["id"] for g in previous_goals if g.get("completed", False)],
            "completion_rate": f"{completed_count}/{len(previous_goals)}",
            "weight": yesterday_metrics.get("weight"),
            "sleep": yesterday_metrics.get("sleep"),
            "recovery": yesterday_metrics.get("recovery"),
            "archived_at": datetime.now().isoformat()
        })
        state["daily_logs"] = daily_logs[-30:]  # Keep last 30 days

        # Reset daily goals from template
        state["daily_goals"] = [
            {**goal, "completed": False}
            for goal in state.get("daily_goals_template", [])
        ]

        # Update daily plan date
        today = datetime.now().strftime("%Y-%m-%d")
        state["daily_plan"]["date"] = today
        state["daily_plan"]["generated_at"] = datetime.now().isoformat()
        state["daily_plan"]["plan_text"] = ""  # Clear old plan

        force_update_state(session_id, state)
        logger.info(f"Midnight reset complete. Archived {completed_count}/{len(previous_goals)} goals from {yesterday}.")

        # Generate new daily plan for today
        try:
            daily_plan_prompt = (
                f"Good morning! Today is {today}. "
                f"Please generate my DAILY BATTLE PLAN for today with:\n"
                f"1. Specific workout exercises with sets and reps\n"
                f"2. Specific meals with foods and portions\n"
                f"3. Timing recommendations\n"
                f"Format it as a clear, actionable daily schedule."
            )

            content = types.Content(role="user", parts=[types.Part(text=daily_plan_prompt)])
            daily_plan_text = ""

            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=content
            ):
                if event.is_final_response():
                    if event.content and event.content.parts:
                        daily_plan_text = event.content.parts[0].text.strip()

            # Save the new daily plan
            session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
            state = session.state
            state["daily_plan"]["plan_text"] = daily_plan_text
            force_update_state(session_id, state)

            logger.info(f"New daily plan generated for {today}.")

        except Exception as e:
            logger.error(f"Error generating daily plan during midnight reset: {e}")

    except Exception as e:
        logger.error(f"Error during midnight reset: {e}")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    # ═══════════════════════════════════════════════════════════════
    # AGGRESSIVE 2-HOUR PROACTIVE CHECK-INS
    # Check-ins at: 7AM, 9AM, 11AM, 1PM, 3PM, 5PM, 7PM, 9PM
    # ═══════════════════════════════════════════════════════════════
    for hour in [7, 9, 11, 13, 15, 17, 19, 21]:
        scheduler.add_job(
            proactive_checkin,
            'cron',
            hour=hour,
            minute=0,
            id=f'checkin_{hour:02d}00'
        )

    # ═══════════════════════════════════════════════════════════════
    # WATER REMINDERS (offset by 1 hour from check-ins)
    # Reminders at: 8AM, 10AM, 12PM, 2PM, 4PM, 6PM, 8PM
    # ═══════════════════════════════════════════════════════════════
    for hour in [8, 10, 12, 14, 16, 18, 20]:
        scheduler.add_job(
            water_reminder,
            'cron',
            hour=hour,
            minute=0,
            id=f'water_{hour:02d}00'
        )

    # ═══════════════════════════════════════════════════════════════
    # MIDNIGHT RESET - Archive goals and generate new daily plan
    # ═══════════════════════════════════════════════════════════════
    scheduler.add_job(midnight_reset, 'cron', hour=0, minute=0, id='midnight_reset')

    # ═══════════════════════════════════════════════════════════════
    # MORNING CALENDAR SYNC (7:05 AM)
    # ═══════════════════════════════════════════════════════════════
    async def morning_calendar_sync():
        """Sync calendar at start of day."""
        try:
            session_id = get_or_create_session_id()
            session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
            state = session.state

            if state.get("plan_accepted"):
                # Trigger calendar sync
                now = datetime.now()
                notification_settings = state.get("notification_settings", {})
                wake_time = notification_settings.get("wake_time", "07:00")
                sleep_time = notification_settings.get("sleep_time", "22:00")

                # Generate estimated gaps if no calendar connected
                mock_gaps = [
                    {
                        "start": now.replace(hour=7, minute=0, second=0).isoformat(),
                        "end": now.replace(hour=9, minute=0, second=0).isoformat(),
                        "duration_minutes": 120,
                        "time_of_day": "morning",
                        "next_event": "Work"
                    },
                    {
                        "start": now.replace(hour=12, minute=0, second=0).isoformat(),
                        "end": now.replace(hour=13, minute=0, second=0).isoformat(),
                        "duration_minutes": 60,
                        "time_of_day": "afternoon",
                        "next_event": "Afternoon work"
                    },
                    {
                        "start": now.replace(hour=18, minute=0, second=0).isoformat(),
                        "end": now.replace(hour=22, minute=0, second=0).isoformat(),
                        "duration_minutes": 240,
                        "time_of_day": "evening",
                        "next_event": "End of day"
                    }
                ]
                state["calendar_gaps"] = mock_gaps
                state["calendar_last_sync"] = now.isoformat()
                force_update_state(session_id, state)
                logger.info("Morning calendar sync complete.")
        except Exception as e:
            logger.error(f"Error during morning calendar sync: {e}")

    scheduler.add_job(morning_calendar_sync, 'cron', hour=7, minute=5, id='morning_sync')

    scheduler.start()
    logger.info("=" * 60)
    logger.info("DRILL INSTRUCTOR SCHEDULER ACTIVATED")
    logger.info("=" * 60)
    logger.info("Proactive check-ins: 7AM, 9AM, 11AM, 1PM, 3PM, 5PM, 7PM, 9PM")
    logger.info("Water reminders: 8AM, 10AM, 12PM, 2PM, 4PM, 6PM, 8PM")
    logger.info("Midnight reset: 12:00 AM")
    logger.info("Morning calendar sync: 7:05 AM")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn

    # Get port from environment variable (Cloud Run sets PORT)
    port = int(os.environ.get("PORT", 8000))
    environment = os.environ.get("ENVIRONMENT", "development")

    logger.info(f"Starting Spartan Coach in {environment} mode on port {port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info" if environment == "production" else "debug"
    )
