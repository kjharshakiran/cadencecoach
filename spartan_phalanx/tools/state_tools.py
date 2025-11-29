from google.adk.tools import FunctionTool
from google.genai import types
from typing import Dict, Any

def save_master_plan(plan: Dict[str, Any], **kwargs):
    """Saves the Master Plan to the user's session.
    
    Args:
        plan: The comprehensive Master Plan dictionary containing workout strategy, nutrition targets, and timeline.
    """
    context = kwargs.get("context")
    if not context:
        return "Error: Context not available."
    context.state["master_plan"] = plan
    context.state["plan_locked"] = True
    return "Master Plan saved and locked."

def save_profile(name: str, age: int, height: float, weight: float, goal: str, target_date: str, **kwargs):
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
    """
    context = kwargs.get("context")
    if not context:
        return "Error: Context not available."
    
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

# Manual function declarations that exclude the context parameter
save_master_plan_declaration = types.FunctionDeclaration(
    name="save_master_plan",
    description="Saves the Master Plan to the user's session.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "plan": types.Schema(
                type=types.Type.OBJECT,
                description="The comprehensive Master Plan dictionary containing workout strategy, nutrition targets, and timeline."
            ),
        },
        required=["plan"],
    ),
)

save_profile_declaration = types.FunctionDeclaration(
    name="save_profile",
    description="Save the user's onboarding profile to the session and lock it. This tool saves the warrior's profile information including their name, age, physical stats, fitness goal, and target date. Once saved, the profile is locked and the system is ready to proceed to master plan creation.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name": types.Schema(type=types.Type.STRING, description="User's full name"),
            "age": types.Schema(type=types.Type.INTEGER, description="User's age in years"),
            "height": types.Schema(type=types.Type.NUMBER, description="User's height in centimeters"),
            "weight": types.Schema(type=types.Type.NUMBER, description="User's weight in kilograms"),
            "goal": types.Schema(type=types.Type.STRING, description="The fitness goal the user wants to achieve"),
            "target_date": types.Schema(type=types.Type.STRING, description="Target date for achieving the goal (YYYY-MM-DD format)"),
        },
        required=["name", "age", "height", "weight", "goal", "target_date"],
    ),
)

# Create tools with manual declarations
save_master_plan_tool = types.Tool(function_declarations=[save_master_plan_declaration])
save_profile_tool = types.Tool(function_declarations=[save_profile_declaration])
