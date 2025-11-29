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
USER_ID = "Harsha"  # Default user for this demo

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
    master_plan: Dict[str, Any]

def get_or_create_session_id():
    existing_sessions = session_service.list_sessions(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    if existing_sessions and len(existing_sessions.sessions) > 0:
        return existing_sessions.sessions[0].id
    
    # Initial state matching run_phalanx.py
    initial_state = {
        "user_name": "Harsha",
        "warrior_profile": {},
        "master_plan": {},
        "daily_logs": [],
        "plan_locked": False
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
    return {"message": "Session reset. PREPARE FOR GLORY!"}

@app.get("/api/state", response_model=StateResponse)
async def get_state():
    session_id = get_or_create_session_id()
    session = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    state = session.state
    return StateResponse(
        user_name=state.get("user_name", ""),
        profile_locked=state.get("profile_locked", False),
        master_plan=state.get("master_plan", {})
    )

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

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    # Schedule check-ins at 9 AM, 12 PM, 3 PM, and 9 PM
    scheduler.add_job(scheduled_checkin, 'cron', hour=9, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=12, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=15, minute=0)
    scheduler.add_job(scheduled_checkin, 'cron', hour=21, minute=0)
    scheduler.start()
    logger.info("Scheduler started with check-ins at 9AM, 12PM, 3PM, 9PM.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
