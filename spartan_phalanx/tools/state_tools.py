from google.adk.tools import FunctionTool, ToolContext
from typing import Dict, Any
from datetime import datetime

def save_master_plan(plan: Dict[str, Any], tool_context: ToolContext):
    """Saves the Master Plan to the user's session.

    Args:
        plan: The comprehensive Master Plan dictionary containing workout strategy, nutrition targets, and timeline.
        tool_context: The tool execution context (automatically provided by the framework).
    """
    tool_context.state["master_plan"] = plan
    tool_context.state["plan_locked"] = True
    return "Master Plan saved and locked."

def accept_plan(tool_context: ToolContext):
    """Accepts the Master Plan and transitions to daily execution phase.

    Call this tool when the user confirms they want to accept and start their Master Plan.
    This sets plan_accepted to True and initializes daily goals tracking.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).
    """
    if not tool_context.state.get("master_plan"):
        return "Error: No master plan exists to accept."

    tool_context.state["plan_accepted"] = True
    tool_context.state["master_plan"]["status"] = "accepted"

    # Initialize daily goals from template if not already set
    today = datetime.now().strftime("%Y-%m-%d")

    template = tool_context.state.get("daily_goals_template", [])
    if not tool_context.state.get("daily_goals") or len(tool_context.state.get("daily_goals", [])) == 0:
        tool_context.state["daily_goals"] = [
            {**goal, "completed": False, "date": today}
            for goal in template
        ]

    return "PLAN ACCEPTED! Your transformation begins NOW. Daily goals have been initialized. The warrior's journey starts today!"

def save_profile(name: str, age: int, height: float, weight: float, goal: str, target_date: str, reason: str, tool_context: ToolContext):
    """Save the user's onboarding profile to the session and lock it.

    This tool saves the warrior's profile information including their name, age,
    physical stats, fitness goal, target date, and personal motivation/reason.
    Once saved, the profile is locked and the system is ready to proceed to master plan creation.

    Args:
        name: User's full name
        age: User's age in years
        height: User's height in centimeters
        weight: User's weight in pounds (lbs)
        goal: The fitness goal the user wants to achieve
        target_date: Target date for achieving the goal (YYYY-MM-DD format)
        reason: The personal reason/motivation for achieving this goal (WHY this matters to the user)
        tool_context: The tool execution context (automatically provided by the framework).
    """
    tool_context.state["warrior_profile"] = {
        "name": name,
        "age": age,
        "height": height,
        "weight": weight,
        "goal": goal,
        "target_date": target_date,
        "reason": reason,
    }
    tool_context.state["profile_locked"] = True
    tool_context.state["plan_locked"] = False
    return "Profile saved successfully. The warrior profile is now locked. Proceed to create the Master Plan."


def get_daily_plan(tool_context: ToolContext) -> str:
    """Retrieves the stored comprehensive daily plan for today.

    Use this tool when the user asks about their daily plan, today's plan,
    what to do today, etc. This retrieves the pre-generated comprehensive
    schedule without regenerating it.

    The daily plan includes:
    - Complete time-based schedule from wake-up to bedtime
    - Workout details with exercises, sets, reps
    - All meals with portions and macros
    - Water/hydration checkpoints
    - Step targets and movement breaks
    - Daily goals checklist

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

    Returns:
        The stored daily plan text, or a message if no plan exists.
    """
    daily_plan = tool_context.state.get("daily_plan", {})
    plan_text = daily_plan.get("plan_text", "")
    plan_date = daily_plan.get("date", "")

    if not plan_text:
        return "NO_DAILY_PLAN: No daily plan has been generated yet. The user needs to accept their Master Plan first, which will automatically generate the daily plan."

    today = datetime.now().strftime("%Y-%m-%d")
    if plan_date != today:
        return f"OUTDATED_PLAN: The stored daily plan is from {plan_date}, not today ({today}). A new plan should be generated via midnight reset."

    return f"DAILY_PLAN_RETRIEVED:\n\n{plan_text}"


# Create FunctionTool wrappers - these automatically inject tool_context
save_master_plan_tool = FunctionTool(save_master_plan)
save_profile_tool = FunctionTool(save_profile)
accept_plan_tool = FunctionTool(accept_plan)
get_daily_plan_tool = FunctionTool(get_daily_plan)
