#!/usr/bin/env python3
"""
Test script for Spartan Coach - Tests different weight loss scenarios
and verifies master plan parsing, fitness targets, and goals.
"""

import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api"

def reset_session():
    """Reset the session to start fresh."""
    try:
        resp = requests.post(f"{BASE_URL}/reset")
        print(f"  Reset: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"  Reset error: {e}")
        return False

def submit_profile(name, age, height, weight, goal, days_from_now, reason):
    """Submit a profile and get the master plan."""
    target_date = (datetime.now() + timedelta(days=days_from_now)).strftime("%Y-%m-%d")

    payload = {
        "name": name,
        "age": age,
        "height": height,
        "weight": weight,
        "goal": goal,
        "target_date": target_date,
        "reason": reason
    }

    print(f"\n  Submitting profile:")
    print(f"    Name: {name}, Weight: {weight} lbs, Goal: {goal}")
    print(f"    Target: {target_date} ({days_from_now} days)")
    print(f"    Reason: {reason[:50]}...")

    try:
        resp = requests.post(f"{BASE_URL}/onboard", json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Profile submitted successfully")
            return data
        else:
            print(f"  ❌ Error: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None

def get_state():
    """Get current session state."""
    try:
        resp = requests.get(f"{BASE_URL}/state")
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"  State error: {e}")
        return None

def get_water_status():
    """Get water status."""
    try:
        resp = requests.get(f"{BASE_URL}/water/status")
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"  Water status error: {e}")
        return None

def get_steps_status():
    """Get steps status."""
    try:
        resp = requests.get(f"{BASE_URL}/steps/status")
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"  Steps status error: {e}")
        return None

def check_fitness_targets(expected_water=None, expected_steps=None):
    """Check if fitness targets are correctly set."""
    # We need to check the internal state - let's use a debug endpoint
    # For now, check via water and steps status

    water = get_water_status()
    steps = get_steps_status()

    results = {"water": None, "steps": None, "errors": []}

    if water:
        results["water"] = water.get("target")
        print(f"  Water target: {water.get('target')} glasses")
        if expected_water and water.get("target") != expected_water:
            results["errors"].append(f"Water: expected {expected_water}, got {water.get('target')}")
    else:
        results["errors"].append("Could not get water status")

    if steps:
        results["steps"] = steps.get("target")
        print(f"  Steps target: {steps.get('target'):,}")
        if expected_steps and steps.get("target") != expected_steps:
            results["errors"].append(f"Steps: expected {expected_steps}, got {steps.get('target')}")
    else:
        results["errors"].append("Could not get steps status")

    return results

def verify_plan_structure(plan_text):
    """Verify that the plan contains all required sections."""
    required_sections = [
        "MASTER PLAN",
        "YOUR WHY",
        "FEASIBILITY ASSESSMENT",
        "CALCULATIONS",
        "STRATEGIC PHASES",
        "WORKOUT STRATEGY",
        "NUTRITION STRATEGY",
        "DAILY NON-NEGOTIABLES"
    ]
    
    plan_upper = plan_text.upper()
    missing = []
    for section in required_sections:
        if section not in plan_upper:
            missing.append(section)
            
    return missing

def extract_plan_details(plan_text):
    """Extract details from plan text for verification."""
    import re

    details = {
        "water": None,
        "steps": None,
        "feasibility": None,
        "risk_level": None,
        "days_remaining": None
    }

    text_lower = plan_text.lower()

    # Water patterns
    water_match = re.search(r'(\d+)\s*glasses?\s*(?:of\s*)?water', text_lower)
    if water_match:
        details["water"] = int(water_match.group(1))

    # Steps patterns
    step_match = re.search(r'(\d{1,2}),?(\d{3})\s*steps', text_lower)
    if step_match:
        details["steps"] = int(step_match.group(1) + step_match.group(2))
    else:
        step_match = re.search(r'(\d+)k\s*steps', text_lower)
        if step_match:
            details["steps"] = int(step_match.group(1)) * 1000

    # Feasibility
    if "feasibility: achievable" in text_lower:
        details["feasibility"] = "ACHIEVABLE"
    elif "feasibility: challenging" in text_lower:
        details["feasibility"] = "CHALLENGING"
    elif "feasibility: needs adjustment" in text_lower:
        details["feasibility"] = "NEEDS ADJUSTMENT"

    # Risk Level
    if "risk level: low" in text_lower:
        details["risk_level"] = "LOW"
    elif "risk level: medium" in text_lower:
        details["risk_level"] = "MEDIUM"
    elif "risk level: high" in text_lower:
        details["risk_level"] = "HIGH"
        
    return details

def run_scenario(scenario_name, name, age, height, weight, goal, days, reason):
    """Run a single test scenario."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*60}")

    # Reset
    print("\n1. Resetting session...")
    if not reset_session():
        print("  ❌ Failed to reset session")
        return False

    time.sleep(1)

    # Submit profile
    print("\n2. Submitting profile and generating master plan...")
    result = submit_profile(name, age, height, weight, goal, days, reason)

    if not result:
        print("  ❌ Failed to submit profile")
        return False

    # Extract plan text
    plan_text = result.get("agent_response", "")
    print(f"\n3. Master Plan Response (first 500 chars):")
    print(f"  {plan_text[:500]}...")
    
    # Verify Structure
    print("\n4. Verifying plan structure...")
    missing_sections = verify_plan_structure(plan_text)
    if missing_sections:
        print(f"  ❌ Missing sections: {missing_sections}")
        print("\n--- FULL RESPONSE ---")
        print(plan_text)
        print("---------------------\n")
        return False
    print("  ✅ All required sections present")

    # Check what targets were mentioned in the plan
    print("\n5. Extracting details from plan text...")
    details = extract_plan_details(plan_text)
    print(f"  Found: Water={details['water']}, Steps={details['steps']}")
    print(f"  Feasibility: {details['feasibility']}, Risk: {details['risk_level']}")
    print(f"  Timeline: {details['days_remaining']} days (Expected: ~{days})")

    # Check actual targets set
    print("\n6. Checking actual fitness targets...")
    targets = check_fitness_targets()

    if targets["errors"]:
        for err in targets["errors"]:
            print(f"  ⚠️ {err}")

    # Verify targets match
    print("\n7. Verifying targets match plan...")
    match_water = details["water"] is None or targets["water"] == details["water"]
    match_steps = details["steps"] is None or targets["steps"] == details["steps"]

    if match_water and match_steps:
        print("  ✅ Targets correctly parsed and set!")
    else:
        if not match_water:
            print(f"  ❌ Water mismatch: plan says {details['water']}, system set {targets['water']}")
        if not match_steps:
            print(f"  ❌ Steps mismatch: plan says {details['steps']}, system set {targets['steps']}")
            
    # Check state has profile with reason
    print("\n9. Checking profile saved correctly...")
    state = get_state()
    if state:
        print(f"  Profile locked: {state.get('profile_locked')}")
        print(f"  Plan accepted: {state.get('plan_accepted')}")

    return match_water and match_steps

def main():
    print("\n" + "="*60)
    print("SPARTAN COACH - SCENARIO TESTING")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test scenarios
    scenarios = [
        {
            "name": "Aggressive Short-Term",
            "profile": {
                "name": "John", "age": 30, "height": 175, "weight": 200,
                "goal": "Lose 15 lbs", "days": 30,
                "reason": "I have a wedding in a month and want to look my best"
            }
        },
        {
            "name": "Moderate Medium-Term",
            "profile": {
                "name": "Sarah", "age": 28, "height": 165, "weight": 160,
                "goal": "Lose 10 lbs and tone up", "days": 60,
                "reason": "I want to feel confident in summer clothes"
            }
        },
        {
            "name": "Conservative Long-Term",
            "profile": {
                "name": "Mike", "age": 45, "height": 180, "weight": 220,
                "goal": "Lose 25 lbs", "days": 120,
                "reason": "My doctor said I need to lose weight for my health"
            }
        },
        {
            "name": "Muscle Building",
            "profile": {
                "name": "Alex", "age": 25, "height": 178, "weight": 155,
                "goal": "Build muscle and gain 10 lbs", "days": 90,
                "reason": "I want to get stronger and more athletic"
            }
        },
        {
            "name": "Quick Transformation",
            "profile": {
                "name": "Emma", "age": 32, "height": 168, "weight": 145,
                "goal": "Lose 5 lbs and get fit", "days": 14,
                "reason": "Beach vacation coming up!"
            }
        }
    ]

    results = []

    for scenario in scenarios:
        try:
            success = run_scenario(
                scenario["name"],
                scenario["profile"]["name"],
                scenario["profile"]["age"],
                scenario["profile"]["height"],
                scenario["profile"]["weight"],
                scenario["profile"]["goal"],
                scenario["profile"]["days"],
                scenario["profile"]["reason"]
            )
            results.append({"scenario": scenario["name"], "success": success, "error": None})
        except Exception as e:
            print(f"\n  ❌ EXCEPTION: {e}")
            results.append({"scenario": scenario["name"], "success": False, "error": str(e)})

        # Wait between scenarios
        print("\n  Waiting 3 seconds before next scenario...")
        time.sleep(3)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for r in results if r["success"])
    total = len(results)

    for r in results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        error = f" - {r['error']}" if r["error"] else ""
        print(f"  {status}: {r['scenario']}{error}")

    print(f"\nTotal: {passed}/{total} scenarios passed")

    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
