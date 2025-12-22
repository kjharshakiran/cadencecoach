#!/usr/bin/env python3
"""
Test Notifications - Generate test notifications for Spartan Coach users.

Usage:
    python test_notifications.py                    # List all users
    python test_notifications.py <username>         # Trigger check-in for user
    python test_notifications.py <username> --add   # Add simple test notification
    python test_notifications.py <username> --view  # View user's notifications
    python test_notifications.py <username> --clear # Clear user's notifications
"""

import sys
import os
import json
import sqlite3
from datetime import datetime

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(os.path.dirname(__file__), "spartan_phalanx.db")


def get_db_connection():
    """Get SQLite database connection."""
    return sqlite3.connect(DB_PATH)


def list_users():
    """List all registered users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT username FROM registered_users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()

    print("\n=== Registered Users ===")
    for user in users:
        print(f"  - {user}")
    print(f"\nTotal: {len(users)} users")
    return users


def get_user_state(username: str) -> dict:
    """Get user's session state."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state FROM sessions WHERE user_id = ? LIMIT 1",
        (username,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    return None


def update_user_state(username: str, state: dict):
    """Update user's session state."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET state = ? WHERE user_id = ?",
        (json.dumps(state), username)
    )
    conn.commit()
    conn.close()


def view_notifications(username: str):
    """View user's pending notifications."""
    state = get_user_state(username)
    if not state:
        print(f"User '{username}' not found!")
        return

    reminders = state.get("pending_reminders", [])

    print(f"\n=== Notifications for {username} ===")
    print(f"Plan accepted: {state.get('plan_accepted', False)}")
    print(f"Total notifications: {len(reminders)}\n")

    for i, r in enumerate(reminders, 1):
        print(f"[{i}] {r.get('type', 'unknown')} - {r.get('time', 'no time')}")
        print(f"    {r.get('message', 'no message')[:100]}...")
        print()


def add_test_notification(username: str, message: str = None):
    """Add a simple test notification for a user."""
    state = get_user_state(username)
    if not state:
        print(f"User '{username}' not found!")
        return

    warrior_profile = state.get("warrior_profile", {})
    name = warrior_profile.get("name", "Warrior")

    if message is None:
        message = f"🔥 {name}, this is a TEST notification!\n\nYour coach is checking in. Stay focused on your goals!"

    reminders = state.get("pending_reminders", [])
    reminders.append({
        "id": f"test_{datetime.now().strftime('%H%M%S')}",
        "type": "test_notification",
        "time": datetime.now().isoformat(),
        "message": message,
        "read": False
    })
    state["pending_reminders"] = reminders[-10:]  # Keep last 10

    update_user_state(username, state)
    print(f"Added test notification for {username}. Total: {len(state['pending_reminders'])}")


def clear_notifications(username: str):
    """Clear all notifications for a user."""
    state = get_user_state(username)
    if not state:
        print(f"User '{username}' not found!")
        return

    count = len(state.get("pending_reminders", []))
    state["pending_reminders"] = []
    update_user_state(username, state)
    print(f"Cleared {count} notifications for {username}.")


def trigger_checkin(username: str):
    """Trigger a forced check-in for a user (uses the server's check-in logic)."""
    import asyncio

    async def run_checkin():
        from server import _force_proactive_checkin_for_user
        await _force_proactive_checkin_for_user(username)
        print(f"Triggered forced check-in for {username}!")

    asyncio.run(run_checkin())


def main():
    if len(sys.argv) < 2:
        list_users()
        print("\nUsage:")
        print("  python test_notifications.py <username>         # Trigger check-in")
        print("  python test_notifications.py <username> --add   # Add test notification")
        print("  python test_notifications.py <username> --view  # View notifications")
        print("  python test_notifications.py <username> --clear # Clear notifications")
        return

    username = sys.argv[1]

    if len(sys.argv) >= 3:
        action = sys.argv[2]
        if action == "--add":
            message = sys.argv[3] if len(sys.argv) > 3 else None
            add_test_notification(username, message)
        elif action == "--view":
            view_notifications(username)
        elif action == "--clear":
            clear_notifications(username)
        else:
            print(f"Unknown action: {action}")
    else:
        # Default: trigger check-in
        trigger_checkin(username)
        view_notifications(username)


if __name__ == "__main__":
    main()
