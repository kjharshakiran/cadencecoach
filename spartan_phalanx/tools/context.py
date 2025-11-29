import datetime
from google.adk.tools import FunctionTool

def get_user_context() -> dict:
    """
    Retrieves the current context for the user.
    In a real app, this would fetch from a database, health API, or device sensors.
    """
    now = datetime.datetime.now()
    
    # Mock context data
    return {
        "timestamp": now.isoformat(),
        "day_of_week": now.strftime("%A"),
        "time_of_day": now.strftime("%H:%M"),
        "location": "Home Base",
        "energy_level": "Unknown (Assume 100% until reported otherwise)",
        "last_workout": "Yesterday - 5k Run",
        "current_focus": "Building the Phalanx",
        "notifications_pending": 0
    }
from google.adk.tools import FunctionTool

def get_user_context(user_id: str, session) -> str:
    profile = session.load(user_id).get("warrior_profile", {})
    plan = session.load(user_id).get("master_plan", "None")
    return f"Profile: {profile}\nMaster Plan: {plan[:200]}..."

