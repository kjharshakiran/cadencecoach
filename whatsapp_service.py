"""
WhatsApp Service - Twilio WhatsApp API Integration
Enables proactive coaching notifications via WhatsApp.
"""
import os
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Handles WhatsApp messaging via Twilio API."""

    TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    def is_configured(self) -> bool:
        """Check if Twilio credentials are configured."""
        return bool(self.account_sid and self.auth_token)

    async def send_message(self, to_number: str, message: str) -> Dict[str, Any]:
        """
        Send a WhatsApp message via Twilio.

        Args:
            to_number: Recipient's phone number (with or without whatsapp: prefix)
            message: Message text to send

        Returns:
            Twilio API response as dict
        """
        if not self.is_configured():
            logger.error("Twilio credentials not configured")
            return {"error": "Twilio not configured", "success": False}

        # Format number if needed
        if not to_number.startswith("whatsapp:"):
            # Ensure number has country code
            if not to_number.startswith("+"):
                to_number = f"+{to_number}"
            to_number = f"whatsapp:{to_number}"

        url = f"{self.TWILIO_API_BASE}/Accounts/{self.account_sid}/Messages.json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "From": self.from_number,
                        "To": to_number,
                        "Body": message
                    }
                )

                result = response.json()

                if response.status_code in [200, 201]:
                    logger.info(f"WhatsApp message sent to {to_number}: SID {result.get('sid')}")
                    return {"success": True, "sid": result.get("sid"), "status": result.get("status")}
                else:
                    logger.error(f"WhatsApp send failed: {result}")
                    return {"success": False, "error": result.get("message", "Unknown error")}

        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return {"success": False, "error": str(e)}

    async def send_template_message(
        self,
        to_number: str,
        template_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a pre-formatted coaching message using templates.

        Args:
            to_number: Recipient's phone number
            template_type: One of the predefined template types
            **kwargs: Template variables

        Returns:
            Twilio API response
        """
        templates = {
            # Morning briefing at 7 AM
            "morning_briefing": (
                "🌅 MORNING BRIEFING, WARRIOR!\n\n"
                "Today's Mission:\n{daily_plan_summary}\n\n"
                "Total Goals: {total_goals}\n\n"
                "Remember: \"{reason}\"\n\n"
                "LET'S CRUSH IT! 💪"
            ),

            # Water reminder every 2 hours
            "water_reminder": (
                "💧 HYDRATION CHECK!\n\n"
                "Current: {glasses}/{target} glasses\n"
                "Time since last: {hours_since}h\n\n"
                "Remember: \"{reason}\"\n\n"
                "DRINK WATER NOW! 🥤"
            ),

            # Proactive check-in every 2 hours
            "proactive_checkin": (
                "📊 STATUS REPORT\n\n"
                "Goals: {completed}/{total} ({percentage}%)\n"
                "Urgency: LEVEL {urgency_level}\n\n"
                "{message}\n\n"
                "⏰ {hours_remaining}h remaining today"
            ),

            # Workout reminder 15 min before
            "workout_reminder": (
                "💪 WORKOUT TIME!\n\n"
                "Activity: {activity}\n"
                "Scheduled: {scheduled_time}\n\n"
                "{recovery_info}\n\n"
                "NO EXCUSES. EXECUTE. 🔥"
            ),

            # Step count alert in evening
            "step_alert": (
                "👟 STEP COUNT ALERT!\n\n"
                "Current: {current:,} steps\n"
                "Target: {target:,} steps\n"
                "Remaining: {remaining:,}\n\n"
                "TIME IS RUNNING OUT!\n"
                "MOVE NOW! 🏃"
            ),

            # Goal completion celebration
            "goal_complete": (
                "🏆 OUTSTANDING, WARRIOR!\n\n"
                "Completed: {goal_name}\n\n"
                "Progress: {completed}/{total} goals\n\n"
                "KEEP PUSHING! 💪"
            ),

            # Evening summary at 9 PM
            "evening_summary": (
                "🌙 END OF DAY REPORT\n\n"
                "Goals: {completed}/{total} ({percentage}%)\n"
                "Water: {water_glasses}/8 glasses\n"
                "Steps: {steps:,}/10,000\n\n"
                "{verdict}\n\n"
                "Rest well, warrior. Tomorrow we go again. 🛡️"
            ),

            # Schedule reminder (meal, movement, etc.)
            "schedule_reminder": (
                "⏰ REMINDER: {activity_type}\n\n"
                "{activity}\n"
                "Time: {scheduled_time}\n\n"
                "EXECUTE. 🎯"
            ),

            # Test message
            "test": (
                "🔔 SPARTAN COACH CONNECTED!\n\n"
                "WhatsApp notifications are now active.\n"
                "You will receive:\n"
                "• Morning briefings\n"
                "• Hydration reminders\n"
                "• Workout alerts\n"
                "• Progress updates\n\n"
                "PREPARE FOR DISCIPLINE. 🛡️"
            ),

            # Generic message fallback
            "generic": "{message}"
        }

        template = templates.get(template_type, templates["generic"])

        try:
            # Handle missing kwargs gracefully
            formatted_message = template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable {e}, using fallback")
            formatted_message = kwargs.get("message", f"Notification: {template_type}")

        return await self.send_message(to_number, formatted_message)

    async def send_test_message(self, to_number: str) -> Dict[str, Any]:
        """Send a test message to verify the connection works."""
        return await self.send_template_message(to_number, "test")


# Singleton instance for the application
whatsapp_service = WhatsAppService()
