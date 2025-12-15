"""
Proactive Monitoring Tools for Spartan Coach.
These tools enable the monitoring agent to check calendar gaps, goal progress,
water intake, step counts, and calculate urgency levels.
"""

from datetime import datetime
from typing import Dict, Any, List


def get_calendar_gaps(**kwargs) -> Dict[str, Any]:
    """
    Retrieves available time gaps from the user's calendar for today.
    Use this to identify opportunities for micro-workouts.

    Returns:
        Dictionary containing:
        - total_gaps: Number of available gaps
        - gaps: List of gap objects with start, end, duration, time_of_day
        - current_gap: Current gap if user is in one (with remaining_minutes)
        - next_event: Next scheduled event with minutes_until
        - current_time: Current time
        - time_of_day: morning/afternoon/evening
    """
    context = kwargs.get("context")
    if not context:
        return {"error": "Context not available", "total_gaps": 0, "gaps": []}

    state = context.state
    gaps = state.get("calendar_gaps", [])
    events = state.get("today_calendar_events", [])
    now = datetime.now()

    # Find current gap
    current_gap = None
    for gap in gaps:
        try:
            gap_start = datetime.fromisoformat(gap["start"])
            gap_end = datetime.fromisoformat(gap["end"])
            if gap_start <= now <= gap_end:
                remaining = int((gap_end - now).total_seconds() / 60)
                current_gap = {
                    **gap,
                    "remaining_minutes": remaining
                }
                break
        except (ValueError, KeyError):
            continue

    # Find next event
    next_event = None
    for event in events:
        try:
            event_start_str = event.get("start", "")
            if not event_start_str:
                continue
            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).replace(tzinfo=None)
            if event_start > now:
                next_event = {
                    "summary": event.get("summary", "Unknown"),
                    "start": event_start_str,
                    "minutes_until": int((event_start - now).total_seconds() / 60)
                }
                break
        except (ValueError, KeyError):
            continue

    # Classify time of day
    hour = now.hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    return {
        "total_gaps": len(gaps),
        "gaps": gaps,
        "current_gap": current_gap,
        "next_event": next_event,
        "current_time": now.strftime("%H:%M"),
        "time_of_day": time_of_day,
        "calendar_synced": state.get("calendar_last_sync") is not None
    }


def check_goal_progress(**kwargs) -> Dict[str, Any]:
    """
    Checks the completion status of all daily goals.
    Use this to assess the user's progress and determine urgency.

    Returns:
        Dictionary containing:
        - completed: Number of completed goals
        - total: Total number of goals
        - percentage: Completion percentage
        - incomplete_goals: List of incomplete goal objects
        - category_status: Status breakdown by category
        - hours_remaining: Hours until end of day (10 PM)
        - expected_progress: Expected % based on time of day
        - on_track: Boolean if user is on track
    """
    context = kwargs.get("context")
    if not context:
        return {"error": "Context not available", "completed": 0, "total": 0}

    state = context.state
    goals = state.get("daily_goals", [])

    completed = [g for g in goals if g.get("completed", False)]
    incomplete = [g for g in goals if not g.get("completed", False)]

    # Group by category
    category_status = {}
    for goal in goals:
        category = goal.get("category", "other")
        if category not in category_status:
            category_status[category] = {"completed": 0, "total": 0, "goals": []}
        category_status[category]["total"] += 1
        category_status[category]["goals"].append(goal.get("name", goal.get("id")))
        if goal.get("completed"):
            category_status[category]["completed"] += 1

    percentage = (len(completed) / len(goals) * 100) if goals else 0

    # Calculate time-based expectations
    now = datetime.now()
    hour = now.hour
    hours_left = max(0, 22 - hour)  # 10 PM end

    # Expected progress: linear from 7 AM (0%) to 10 PM (100%)
    # 7 AM = 0%, 10 PM = 100%, 15 hours span
    if hour < 7:
        expected_progress = 0
    elif hour >= 22:
        expected_progress = 100
    else:
        expected_progress = min(100, ((hour - 7) / 15) * 100)

    return {
        "completed": len(completed),
        "total": len(goals),
        "percentage": round(percentage),
        "incomplete_goals": [
            {"id": g["id"], "name": g["name"], "category": g.get("category", "other")}
            for g in incomplete
        ],
        "category_status": category_status,
        "hours_remaining": hours_left,
        "expected_progress": round(expected_progress),
        "on_track": percentage >= expected_progress - 10,  # 10% buffer
        "behind_by": max(0, round(expected_progress - percentage))
    }


def calculate_urgency_level(**kwargs) -> Dict[str, Any]:
    """
    Calculates the urgency level based on time of day and goal progress.
    Use this to determine how aggressive your response should be.

    Returns:
        Dictionary containing:
        - level: 0-3 urgency level
        - label: GREEN/YELLOW/ORANGE/RED
        - message: Urgency description for the coach
        - factors: List of factors contributing to urgency
        - current_progress: Current completion %
        - expected_progress: Expected completion %
        - recommended_tone: Tone to use in response
    """
    context = kwargs.get("context")
    if not context:
        return {"error": "Context not available", "level": 0, "label": "GREEN"}

    state = context.state
    goals = state.get("daily_goals", [])
    water_data = state.get("water_intake", {"glasses": 0})

    now = datetime.now()
    hour = now.hour

    completed = sum(1 for g in goals if g.get("completed", False))
    total = len(goals)
    percentage = (completed / total * 100) if total else 100

    # Calculate expected progress
    if hour < 7:
        expected = 0
    elif hour >= 22:
        expected = 100
    else:
        expected = min(100, ((hour - 7) / 15) * 100)

    # Calculate urgency factors
    factors = []
    urgency = 0

    # Time factor
    if hour >= 20:  # After 8 PM
        urgency += 1
        factors.append("Late in the day - limited time remaining")
    if hour >= 21:  # After 9 PM
        urgency += 1
        factors.append("Day almost over - CRITICAL TIME")

    # Progress factor
    behind = expected - percentage
    if behind > 30:
        urgency += 2
        factors.append(f"SIGNIFICANTLY behind schedule ({round(percentage)}% vs {round(expected)}% expected)")
    elif behind > 15:
        urgency += 1
        factors.append(f"Behind schedule ({round(percentage)}% vs {round(expected)}% expected)")

    # Water factor
    water_glasses = water_data.get("glasses", 0)
    water_expected = min(8, max(1, int((hour - 7) / 2)))  # Roughly 1 glass every 2 hours
    if hour >= 12 and water_glasses < water_expected - 2:
        urgency += 1
        factors.append(f"Water intake critically low ({water_glasses}/8 glasses)")

    # Steps factor
    walking_goal = next((g for g in goals if g["id"] == "walking"), None)
    if walking_goal and not walking_goal.get("completed"):
        current_steps = walking_goal.get("current", 0)
        if hour >= 17 and current_steps < 5000:
            urgency += 1
            factors.append(f"Steps dangerously low ({current_steps}/10,000) - evening crunch!")
        elif hour >= 19 and current_steps < 7000:
            urgency += 1
            factors.append(f"Steps need URGENT attention ({current_steps}/10,000)")

    # Exercise goals factor
    exercise_goals = [g for g in goals if g.get("category") == "exercise" and not g.get("completed")]
    if hour >= 18 and exercise_goals:
        urgency += 1
        factors.append(f"Exercise goals incomplete: {', '.join(g['name'] for g in exercise_goals)}")

    urgency = min(3, urgency)  # Cap at 3

    labels = ["GREEN", "YELLOW", "ORANGE", "RED"]
    messages = [
        "On track - maintain discipline and keep pushing",
        "Slightly behind - increase pace, no room for complacency",
        "SIGNIFICANTLY behind - aggressive action required NOW",
        "CRITICAL - MAXIMUM EFFORT NEEDED. No excuses. Execute immediately."
    ]
    tones = [
        "encouraging but firm",
        "firm and urgent",
        "aggressive and demanding",
        "MAXIMUM INTENSITY - drill sergeant mode"
    ]

    return {
        "level": urgency,
        "label": labels[urgency],
        "message": messages[urgency],
        "factors": factors,
        "current_progress": round(percentage),
        "expected_progress": round(expected),
        "recommended_tone": tones[urgency],
        "hours_remaining": max(0, 22 - hour)
    }


def get_water_status(**kwargs) -> Dict[str, Any]:
    """
    Gets current water intake status and calculates required pace.
    Use this to remind users about hydration.

    Returns:
        Dictionary containing:
        - glasses_logged: Current glasses logged today
        - target: Target glasses (8)
        - remaining: Glasses still needed
        - last_logged: Time of last water log
        - hours_since_last: Hours since last log
        - required_pace: Glasses per hour needed to hit target
        - needs_reminder: Boolean if reminder needed (2+ hours since last)
        - on_track: Boolean if on track for 8 glasses
        - urgency_message: Message about water urgency
    """
    context = kwargs.get("context")
    if not context:
        return {"error": "Context not available", "glasses_logged": 0}

    state = context.state
    water_data = state.get("water_intake", {"glasses": 0, "last_logged": None})

    glasses = water_data.get("glasses", 0)
    last_logged = water_data.get("last_logged")

    now = datetime.now()
    sleep_time = 22  # 10 PM
    hours_left = max(1, sleep_time - now.hour)

    remaining = max(0, 8 - glasses)
    required_pace = remaining / hours_left if hours_left > 0 else remaining

    # Calculate hours since last log
    hours_since_last = None
    if last_logged:
        try:
            last_time = datetime.fromisoformat(last_logged)
            hours_since_last = (now - last_time).total_seconds() / 3600
        except ValueError:
            pass

    needs_reminder = hours_since_last is None or hours_since_last >= 2

    # Expected glasses based on time
    hour = now.hour
    expected_glasses = min(8, max(0, int((hour - 7) / 2) + 1))
    on_track = glasses >= expected_glasses - 1

    # Generate urgency message
    if glasses >= 8:
        urgency_message = "Hydration goal COMPLETE. Outstanding!"
    elif remaining <= 2 and hours_left >= 2:
        urgency_message = f"Almost there! {remaining} glasses to go."
    elif remaining > 4 and hours_left < 4:
        urgency_message = f"CRITICAL: {remaining} glasses needed in {hours_left} hours. DRINK NOW!"
    elif needs_reminder:
        urgency_message = f"HYDRATION CHECK: {hours_since_last:.1f if hours_since_last else 'Unknown'} hours since last water. DRINK NOW!"
    else:
        urgency_message = f"On track. Next glass in ~{max(0, 2 - (hours_since_last or 0)):.0f} hours."

    return {
        "glasses_logged": glasses,
        "target": 8,
        "remaining": remaining,
        "percentage": round(glasses / 8 * 100),
        "last_logged": last_logged,
        "hours_since_last": round(hours_since_last, 1) if hours_since_last else None,
        "required_pace": round(required_pace, 1),
        "hours_remaining": hours_left,
        "needs_reminder": needs_reminder,
        "on_track": on_track,
        "urgency_message": urgency_message
    }


def get_step_count(**kwargs) -> Dict[str, Any]:
    """
    Gets current step count and calculates required pace for 10k goal.
    Use this to push users toward their step goal, especially in evening.

    Returns:
        Dictionary containing:
        - current_steps: Steps logged today
        - target: Target steps (10,000)
        - remaining: Steps still needed
        - percentage: Completion percentage
        - required_pace: Steps per hour needed
        - activity_suggestions: List of activities to reach goal
        - on_track: Boolean if on track
        - evening_crunch: Boolean if it's evening and behind
        - urgency_message: Message about step urgency
    """
    context = kwargs.get("context")
    if not context:
        return {"error": "Context not available", "current_steps": 0}

    state = context.state
    walking_goal = next(
        (g for g in state.get("daily_goals", []) if g["id"] == "walking"),
        {"current": 0, "completed": False}
    )

    current_steps = walking_goal.get("current", 0)
    target = 10000
    remaining = max(0, target - current_steps)
    percentage = round(current_steps / target * 100)

    now = datetime.now()
    hour = now.hour
    sleep_time = 22
    hours_left = max(1, sleep_time - hour)

    required_pace = remaining / hours_left if hours_left > 0 else remaining

    # Is it evening crunch time?
    evening_crunch = hour >= 17 and remaining > 5000

    # Expected steps based on time (linear progression)
    if hour < 7:
        expected_steps = 0
    elif hour >= 22:
        expected_steps = 10000
    else:
        expected_steps = int(((hour - 7) / 15) * 10000)

    on_track = current_steps >= expected_steps - 1000  # 1000 step buffer

    # Generate activity suggestions based on remaining steps and time
    suggestions = []
    if remaining > 0:
        if remaining <= 2000:
            suggestions.append({
                "activity": "15-minute brisk walk",
                "estimated_steps": 1500,
                "time_minutes": 15
            })
        if remaining <= 4000:
            suggestions.append({
                "activity": "30-minute walk",
                "estimated_steps": 3500,
                "time_minutes": 30
            })
        if remaining <= 6000:
            suggestions.append({
                "activity": "45-minute walk or light jog",
                "estimated_steps": 5000,
                "time_minutes": 45
            })
        if remaining > 3000:
            suggestions.append({
                "activity": "Basketball (1 hour)",
                "estimated_steps": 6000,
                "time_minutes": 60
            })
            suggestions.append({
                "activity": "Tennis (1 hour)",
                "estimated_steps": 5500,
                "time_minutes": 60
            })
        if remaining > 4000:
            suggestions.append({
                "activity": "30-minute jog",
                "estimated_steps": 4000,
                "time_minutes": 30
            })

    # Generate urgency message
    if current_steps >= target:
        urgency_message = "10K STEPS COMPLETE! OUTSTANDING WARRIOR!"
    elif evening_crunch:
        urgency_message = f"EVENING CRUNCH: {remaining:,} steps needed in {hours_left} hours. GET MOVING NOW!"
    elif hour >= 19 and remaining > 3000:
        urgency_message = f"CRITICAL: {remaining:,} steps remaining. Time is running out. CHOOSE AN ACTIVITY NOW!"
    elif not on_track:
        urgency_message = f"Behind on steps. {remaining:,} to go. Pick up the pace!"
    else:
        urgency_message = f"On track. {remaining:,} steps remaining. Keep moving!"

    return {
        "current_steps": current_steps,
        "target": target,
        "remaining": remaining,
        "percentage": percentage,
        "required_pace": round(required_pace),
        "hours_remaining": hours_left,
        "activity_suggestions": suggestions[:4],  # Top 4 suggestions
        "on_track": on_track,
        "evening_crunch": evening_crunch,
        "urgency_message": urgency_message,
        "expected_steps": expected_steps,
        "behind_by": max(0, expected_steps - current_steps)
    }


# Tool declarations for Google ADK
from google.genai import types

get_calendar_gaps_declaration = types.FunctionDeclaration(
    name="get_calendar_gaps",
    description="Retrieves available time gaps from the user's calendar for today. Use this to identify opportunities for micro-workouts and exercise sessions.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)

check_goal_progress_declaration = types.FunctionDeclaration(
    name="check_goal_progress",
    description="Checks the completion status of all daily goals. Use this to assess progress and determine how aggressively to push the user.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)

calculate_urgency_level_declaration = types.FunctionDeclaration(
    name="calculate_urgency_level",
    description="Calculates urgency level (0-3: GREEN/YELLOW/ORANGE/RED) based on time and progress. Use this to set your response intensity.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)

get_water_status_declaration = types.FunctionDeclaration(
    name="get_water_status",
    description="Gets current water intake status. Use this to remind users about hydration if they haven't logged water in 2+ hours.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)

get_step_count_declaration = types.FunctionDeclaration(
    name="get_step_count",
    description="Gets current step count and progress toward 10k goal. Use this especially in the evening to push users who are behind.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)

# Create tool objects
proactive_tools = types.Tool(
    function_declarations=[
        get_calendar_gaps_declaration,
        check_goal_progress_declaration,
        calculate_urgency_level_declaration,
        get_water_status_declaration,
        get_step_count_declaration
    ]
)
