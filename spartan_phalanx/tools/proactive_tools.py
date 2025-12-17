"""
Proactive Monitoring Tools for Spartan Coach.
These tools enable the monitoring agent to check calendar gaps, goal progress,
water intake, step counts, and calculate urgency levels.
"""

from datetime import datetime
from typing import Dict, Any, List
from google.adk.tools import FunctionTool, ToolContext


def get_calendar_gaps(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieves available time gaps from the user's calendar for today.
    Use this to identify opportunities for micro-workouts.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

    Returns:
        Dictionary containing:
        - total_gaps: Number of available gaps
        - gaps: List of gap objects with start, end, duration, time_of_day
        - current_gap: Current gap if user is in one (with remaining_minutes)
        - next_event: Next scheduled event with minutes_until
        - current_time: Current time
        - time_of_day: morning/afternoon/evening
    """

    state = tool_context.state
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


def check_goal_progress(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Checks the completion status of all daily goals.
    Use this to assess the user's progress and determine urgency.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

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
    state = tool_context.state
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


def calculate_urgency_level(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Calculates the urgency level based on time of day and goal progress.
    Use this to determine how aggressive your response should be.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

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
    state = tool_context.state
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


def get_water_status(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Gets current water intake status and calculates required pace.
    Use this to remind users about hydration.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

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
    state = tool_context.state
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


def get_step_count(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Gets current step count and calculates required pace for 10k goal.
    Use this to push users toward their step goal, especially in evening.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

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
    state = tool_context.state
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


# ═══════════════════════════════════════════════════════════════
# WHOOP INTEGRATION TOOLS - DISCREPANCY DETECTION
# ═══════════════════════════════════════════════════════════════

def get_whoop_status(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Gets the current Whoop data including recovery, strain, and sleep.
    Use this to check the user's biometric status and adjust recommendations.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

    Returns:
        Dictionary containing:
        - connected: Boolean if Whoop is connected
        - recovery: Recovery data (score, hrv, resting_hr, status)
        - strain: Today's strain data (score, status)
        - sleep: Last night's sleep data (hours, efficiency, performance)
        - workouts: Today's workouts from Whoop
        - insights: AI-generated insights from the data
        - training_recommendation: What intensity to train at
    """
    state = tool_context.state

    if not state.get("whoop_connected"):
        return {
            "connected": False,
            "message": "Whoop not connected. Connect your Whoop to enable biometric tracking and discrepancy detection.",
            "connect_url": "/auth/whoop"
        }

    whoop_data = state.get("whoop_data", {})

    recovery = whoop_data.get("recovery", {})
    strain = whoop_data.get("strain", {})
    sleep = whoop_data.get("sleep", {})
    workouts = whoop_data.get("workouts", [])
    insights = whoop_data.get("insights", [])

    # Generate training recommendation based on recovery
    recovery_score = recovery.get("score", 0) if recovery else 0
    if recovery_score >= 67:
        training_rec = "HIGH_INTENSITY - Your body is ready. Push hard today!"
    elif recovery_score >= 34:
        training_rec = "MODERATE_INTENSITY - Train smart, don't overdo it."
    elif recovery_score > 0:
        training_rec = "ACTIVE_RECOVERY - Rest day. Walking, stretching, yoga only."
    else:
        training_rec = "UNKNOWN - No recovery data available."

    return {
        "connected": True,
        "recovery": recovery,
        "strain": strain,
        "sleep": sleep,
        "workouts": workouts,
        "workout_count": len(workouts),
        "insights": insights,
        "training_recommendation": training_rec,
        "last_updated": whoop_data.get("timestamp", "Unknown")
    }


def verify_workout_claim(tool_context: ToolContext, intensity_claimed: str = "high") -> Dict[str, Any]:
    """
    DISCREPANCY DETECTOR: Verifies if the user's workout claim matches Whoop data.
    Use this when a user reports completing a workout to catch lies.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).
        intensity_claimed: The intensity the user claimed - "high", "moderate", or "low"

    Returns:
        Dictionary containing:
        - verified: Boolean if claim matches data (None if Whoop not connected)
        - whoop_strain: Actual strain recorded by Whoop
        - discrepancy: Description of any discrepancy found
        - message: Confrontation or verification message for the user
        - recommendation: What to tell the user
    """
    state = tool_context.state

    if not state.get("whoop_connected"):
        return {
            "verified": None,
            "message": "Cannot verify workout - Whoop not connected. Your word is all I have... for now.",
            "recommendation": "Connect Whoop for real accountability. No more hiding!"
        }

    whoop_data = state.get("whoop_data", {})
    strain = whoop_data.get("strain", {})
    workouts = whoop_data.get("workouts", [])

    strain_score = strain.get("score", 0) if strain else 0
    workout_count = len(workouts)

    # Set thresholds based on claimed intensity
    thresholds = {
        "high": 14.0,
        "moderate": 10.0,
        "low": 6.0
    }
    threshold = thresholds.get(intensity_claimed, 10.0)

    result = {
        "verified": False,
        "whoop_strain": strain_score,
        "workout_count": workout_count,
        "discrepancy": None,
        "message": None,
        "recommendation": None
    }

    if strain_score >= threshold:
        result["verified"] = True
        result["message"] = f"VERIFIED! Whoop confirms strain of {strain_score:.1f}. OUTSTANDING WORK, WARRIOR!"
        result["recommendation"] = "Log this victory and keep the momentum!"
    else:
        result["verified"] = False
        result["discrepancy"] = f"Claimed {intensity_claimed} intensity but Whoop shows strain of {strain_score:.1f}"

        if strain_score < 5:
            result["message"] = f"Your Whoop says strain is {strain_score:.1f}. That's basically SITTING ON THE COUCH. Where's the workout you claimed?"
            result["recommendation"] = "Get back out there and earn that check-mark. No credit for lying."
        elif strain_score < 10:
            result["message"] = f"Whoop recorded strain of {strain_score:.1f}. That's a WARM-UP, not a workout. Don't lie to yourself."
            result["recommendation"] = "Push harder next time. A real workout should hit strain 10+."
        else:
            result["message"] = f"Whoop shows strain of {strain_score:.1f}. Decent effort, but not the '{intensity_claimed}' intensity you claimed. Be honest with yourself."
            result["recommendation"] = "Good effort, but own your actual performance level."

    return result


def verify_sleep_claim(tool_context: ToolContext, hours_claimed: float) -> Dict[str, Any]:
    """
    DISCREPANCY DETECTOR: Verifies if the user's sleep claim matches Whoop data.
    Use this when a user reports how much they slept.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).
        hours_claimed: Hours of sleep the user claimed to have gotten

    Returns:
        Dictionary containing:
        - verified: Boolean if claim is accurate (within 30 min tolerance)
        - whoop_hours: Actual hours recorded by Whoop
        - difference: Difference between claimed and actual
        - message: Response message for the user
    """
    state = tool_context.state

    if not state.get("whoop_connected"):
        return {
            "verified": None,
            "message": "Cannot verify sleep - Whoop not connected.",
            "whoop_hours": None
        }

    whoop_data = state.get("whoop_data", {})
    sleep = whoop_data.get("sleep", {})

    actual_hours = sleep.get("sleep_hours", 0) if sleep else 0

    result = {
        "verified": False,
        "whoop_hours": actual_hours,
        "claimed_hours": hours_claimed,
        "difference": abs(hours_claimed - actual_hours),
        "message": None
    }

    # 30 minute tolerance
    tolerance = 0.5
    difference = abs(hours_claimed - actual_hours)

    if difference <= tolerance:
        result["verified"] = True
        result["message"] = f"VERIFIED. Whoop confirms {actual_hours:.1f} hours of sleep. GOOD REPORT, WARRIOR."
    else:
        result["verified"] = False
        if hours_claimed > actual_hours:
            result["message"] = f"You said {hours_claimed} hours. Whoop says {actual_hours:.1f} hours. That's a {difference:.1f} hour discrepancy. Stop deceiving yourself."
        else:
            result["message"] = f"Actually, Whoop shows you got MORE sleep than you thought ({actual_hours:.1f}h vs {hours_claimed}h). Know your data!"

    return result


def get_training_readiness(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Determines if the user should train hard today based on Whoop recovery.
    Use this before recommending workout intensity.

    Args:
        tool_context: The tool execution context (automatically provided by the framework).

    Returns:
        Dictionary containing:
        - can_train_hard: Boolean recommendation
        - recovery_score: Current recovery percentage
        - recovery_status: GREEN/YELLOW/RED
        - recommendation: HIGH_INTENSITY/MODERATE/ACTIVE_RECOVERY
        - message: Explanation for the user
        - factors: Contributing factors (HRV, sleep, etc.)
    """
    state = tool_context.state

    if not state.get("whoop_connected"):
        return {
            "can_train_hard": None,
            "message": "Whoop not connected. Cannot assess training readiness. Connect Whoop for personalized recommendations.",
            "recommendation": "PROCEED_WITH_CAUTION"
        }

    whoop_data = state.get("whoop_data", {})
    recovery = whoop_data.get("recovery", {})
    sleep = whoop_data.get("sleep", {})

    recovery_score = recovery.get("score", 0) if recovery else 0
    recovery_status = recovery.get("status", "UNKNOWN") if recovery else "UNKNOWN"
    hrv = recovery.get("hrv") if recovery else None
    resting_hr = recovery.get("resting_hr") if recovery else None
    sleep_hours = sleep.get("sleep_hours", 0) if sleep else 0

    factors = []

    if recovery_score >= 67:
        can_train_hard = True
        recommendation = "HIGH_INTENSITY"
        message = f"Recovery is GREEN at {recovery_score}%. Your body is READY. Time to ATTACK that workout!"
        factors.append(f"Strong recovery ({recovery_score}%)")
    elif recovery_score >= 34:
        can_train_hard = True
        recommendation = "MODERATE_INTENSITY"
        message = f"Recovery is YELLOW at {recovery_score}%. You can train, but pace yourself. Don't overdo it."
        factors.append(f"Moderate recovery ({recovery_score}%)")
    else:
        can_train_hard = False
        recommendation = "ACTIVE_RECOVERY"
        message = f"Recovery is RED at {recovery_score}%. Your body needs REST. Today is active recovery only - walking, stretching, yoga. Trust the data."
        factors.append(f"Low recovery ({recovery_score}%) - rest needed")

    # Add sleep factor
    if sleep_hours < 6:
        factors.append(f"Sleep deficit ({sleep_hours:.1f} hours)")
        if can_train_hard:
            message += " However, sleep was low - consider reducing intensity."
    elif sleep_hours >= 7.5:
        factors.append(f"Good sleep ({sleep_hours:.1f} hours)")

    # Add HRV factor
    if hrv:
        factors.append(f"HRV: {hrv}ms")

    return {
        "can_train_hard": can_train_hard,
        "recovery_score": recovery_score,
        "recovery_status": recovery_status,
        "recommendation": recommendation,
        "message": message,
        "factors": factors,
        "sleep_hours": sleep_hours
    }


# Create FunctionTool wrappers - these automatically inject tool_context
get_calendar_gaps_tool = FunctionTool(get_calendar_gaps)
check_goal_progress_tool = FunctionTool(check_goal_progress)
calculate_urgency_level_tool = FunctionTool(calculate_urgency_level)
get_water_status_tool = FunctionTool(get_water_status)
get_step_count_tool = FunctionTool(get_step_count)

# Whoop tools
get_whoop_status_tool = FunctionTool(get_whoop_status)
verify_workout_claim_tool = FunctionTool(verify_workout_claim)
verify_sleep_claim_tool = FunctionTool(verify_sleep_claim)
get_training_readiness_tool = FunctionTool(get_training_readiness)

# List of all proactive tools for easy import
proactive_tools = [
    get_calendar_gaps,
    check_goal_progress,
    calculate_urgency_level,
    get_water_status,
    get_step_count,
    # Whoop tools
    get_whoop_status,
    verify_workout_claim,
    verify_sleep_claim,
    get_training_readiness
]
