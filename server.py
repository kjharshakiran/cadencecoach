import asyncio
import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

# Import the new architecture
from spartan_phalanx.main import THE_SPARTAN

load_dotenv()

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

@app.get("/")
async def read_root():
    return FileResponse('static/index.html')

# Initialize Session Service (Shared DB with CLI)
db_url = "sqlite:///./spartan_phalanx.db"
session_service = DatabaseSessionService(db_url=db_url)

APP_NAME = "SpartanCoach"
USER_ID = "Alex"  # Default user for this demo

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
    
    # Initial state with enhanced schema
    default_goals_template = [
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
    initial_state = {
        "user_name": "",
        "warrior_profile": {},
        "profile_locked": False,
        "master_plan": {},
        "plan_accepted": False,
        "daily_plan": {},
        "daily_goals": [],
        "daily_goals_template": default_goals_template,
        "daily_logs": [],
        "daily_metrics": {}
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

        return ChatResponse(response=final_response_text)
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

# --- Scheduling ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def scheduled_checkin():
    """Triggers the monitoring agent to check in on the user."""
    session_id = get_or_create_session_id()
    logger.info(f"Executing scheduled check-in for session {session_id}")

    checkin_prompt = "SYSTEM TRIGGER: It is time for a scheduled check-in. Review the user's status and ask for a report if nothing has been logged recently."

    content = types.Content(role="user", parts=[types.Part(text=checkin_prompt)])
    final_response_text = ""

    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                final_response_text = event.content.parts[0].text.strip()

        log_agent_interaction(session_id, "SCHEDULED_CHECKIN", final_response_text)
    except Exception as e:
        logger.error(f"Error during scheduled check-in: {e}")

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
    # Schedule check-ins at 9 AM, 12 PM, 3 PM, and 9 PM
    scheduler.add_job(scheduled_checkin, 'cron', hour=9, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=12, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=15, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=21, minute=0)
    # Midnight reset for daily goals
    scheduler.add_job(midnight_reset, 'cron', hour=0, minute=0)
    scheduler.start()
    logger.info("Scheduler started with check-ins at 9AM, 12PM, 3PM, 9PM and midnight reset.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
