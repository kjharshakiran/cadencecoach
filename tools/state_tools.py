from google.adk.tools import FunctionTool, ToolContext
from typing import Dict, Any

def save_master_plan(plan: Dict[str, Any], context: ToolContext):
    """Saves the Master Plan to the user's session.
    
    Args:
        plan: The comprehensive Master Plan dictionary containing workout strategy, nutrition targets, and timeline.
        context: The tool execution context (automatically provided by the framework).
    """
    context.state["master_plan"] = plan
    context.state["plan_locked"] = True
    return "Master Plan saved and locked."

def save_profile(name: str, age: int, height: float, weight: float, goal: str, target_date: str, context: ToolContext):
    """Save the user's onboarding profile to the session and lock it.
    
    This tool saves the warrior's profile information including their name, age, 
    physical stats, fitness goal, and target date. Once saved, the profile is locked
    and the system is ready to proceed to master plan creation.
    
    Args:
        name: User's full name
        age: User's age in years
        height: User's height in centimeters
        weight: User's weight in kilograms
        goal: The fitness goal the user wants to achieve
        target_date: Target date for achieving the goal (YYYY-MM-DD format)
        context: The tool execution context (automatically provided by the framework).
    """
    context.state["warrior_profile"] = {
        "name": name,
        "age": age,
        "height": height,
        "weight": weight,
        "goal": goal,
        "target_date": target_date,
    }
    context.state["profile_locked"] = True
    context.state["plan_locked"] = False
    return "Profile saved successfully. The warrior profile is now locked. Proceed to create the Master Plan."

save_master_plan_tool = FunctionTool(save_master_plan)
save_profile_tool = FunctionTool(save_profile)



