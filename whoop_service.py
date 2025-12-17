# whoop_service.py
"""
WHOOP API Integration Service
Handles OAuth, data fetching, and discrepancy detection for Spartan Coach.
"""

import os
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("WhoopService")

# Whoop API Configuration
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
WHOOP_REDIRECT_URI = os.getenv("WHOOP_REDIRECT_URI", "http://localhost:8000/auth/whoop/callback")

# Whoop API URLs (v2)
WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v1"

# Scopes we need
WHOOP_SCOPES = [
    "read:recovery",
    "read:sleep",
    "read:workout",
    "read:cycles",
    "read:profile",
    "read:body_measurement"
]


class WhoopService:
    """Service for interacting with the Whoop API."""

    def __init__(self, access_token: str = None, refresh_token: str = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client = httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def get_authorization_url(state: str = None) -> str:
        """Generate the OAuth authorization URL."""
        params = {
            "client_id": WHOOP_CLIENT_ID,
            "redirect_uri": WHOOP_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(WHOOP_SCOPES),
        }
        if state:
            params["state"] = state

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{WHOOP_AUTH_URL}?{query}"

    @staticmethod
    async def exchange_code_for_token(code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WHOOP_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": WHOOP_REDIRECT_URI,
                    "client_id": WHOOP_CLIENT_ID,
                    "client_secret": WHOOP_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to exchange code: {response.text}")

    async def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            raise Exception("No refresh token available")

        response = await self.client.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": WHOOP_CLIENT_ID,
                "client_secret": WHOOP_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            self.refresh_token = tokens.get("refresh_token", self.refresh_token)
            return tokens
        else:
            logger.error(f"Token refresh failed: {response.status_code}")
            raise Exception("Failed to refresh token")

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """Make an authenticated request to the Whoop API."""
        if not self.access_token:
            raise Exception("Not authenticated with Whoop")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        url = f"{WHOOP_API_BASE}{endpoint}"
        response = await self.client.get(url, headers=headers, params=params)

        if response.status_code == 401:
            # Token expired, try to refresh
            logger.info("Token expired, attempting refresh...")
            await self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = await self.client.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"API request failed: {response.status_code} - {response.text}")
            raise Exception(f"API request failed: {response.status_code}")

    # ═══════════════════════════════════════════════════════════════
    # USER PROFILE
    # ═══════════════════════════════════════════════════════════════

    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        return await self._make_request("/user/profile/basic")

    async def get_body_measurement(self) -> Dict[str, Any]:
        """Get user body measurements."""
        return await self._make_request("/user/measurement/body")

    # ═══════════════════════════════════════════════════════════════
    # RECOVERY DATA
    # ═══════════════════════════════════════════════════════════════

    async def get_recovery(self, start_date: str = None, end_date: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Get recovery data.

        Recovery includes:
        - recovery_score (0-100%)
        - resting_heart_rate
        - hrv_rmssd_milli (heart rate variability)
        - spo2_percentage (blood oxygen)
        - skin_temp_celsius
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request("/recovery", params)

    async def get_latest_recovery(self) -> Optional[Dict[str, Any]]:
        """Get the most recent recovery data."""
        data = await self.get_recovery(limit=1)
        records = data.get("records", [])
        return records[0] if records else None

    # ═══════════════════════════════════════════════════════════════
    # SLEEP DATA
    # ═══════════════════════════════════════════════════════════════

    async def get_sleep(self, start_date: str = None, end_date: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Get sleep data.

        Sleep includes:
        - total_in_bed_time_milli
        - total_awake_time_milli
        - total_light_sleep_time_milli
        - total_slow_wave_sleep_time_milli
        - total_rem_sleep_time_milli
        - sleep_efficiency_percentage
        - respiratory_rate
        - sleep_performance_percentage
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request("/activity/sleep", params)

    async def get_latest_sleep(self) -> Optional[Dict[str, Any]]:
        """Get the most recent sleep data."""
        data = await self.get_sleep(limit=1)
        records = data.get("records", [])
        return records[0] if records else None

    # ═══════════════════════════════════════════════════════════════
    # STRAIN / CYCLE DATA
    # ═══════════════════════════════════════════════════════════════

    async def get_cycles(self, start_date: str = None, end_date: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Get physiological cycle (strain) data.

        Cycle includes:
        - strain (0-21 scale)
        - kilojoules burned
        - average_heart_rate
        - max_heart_rate
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request("/cycle", params)

    async def get_today_strain(self) -> Optional[Dict[str, Any]]:
        """Get today's strain/cycle data."""
        today = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
        data = await self.get_cycles(start_date=today, limit=1)
        records = data.get("records", [])
        return records[0] if records else None

    # ═══════════════════════════════════════════════════════════════
    # WORKOUT DATA
    # ═══════════════════════════════════════════════════════════════

    async def get_workouts(self, start_date: str = None, end_date: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Get workout data.

        Workout includes:
        - sport_id (type of workout)
        - strain (workout-specific strain)
        - average_heart_rate
        - max_heart_rate
        - kilojoules
        - distance_meter
        - duration (start/end times)
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request("/activity/workout", params)

    async def get_today_workouts(self) -> List[Dict[str, Any]]:
        """Get today's workouts."""
        today = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
        data = await self.get_workouts(start_date=today, limit=10)
        return data.get("records", [])

    # ═══════════════════════════════════════════════════════════════
    # COMPREHENSIVE DATA FETCH
    # ═══════════════════════════════════════════════════════════════

    async def get_daily_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of today's Whoop data."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "recovery": None,
            "sleep": None,
            "strain": None,
            "workouts": [],
            "insights": []
        }

        try:
            # Get latest recovery
            recovery = await self.get_latest_recovery()
            if recovery:
                score_data = recovery.get("score", {})
                summary["recovery"] = {
                    "score": score_data.get("recovery_score"),
                    "hrv": score_data.get("hrv_rmssd_milli"),
                    "resting_hr": score_data.get("resting_heart_rate"),
                    "spo2": score_data.get("spo2_percentage"),
                    "skin_temp": score_data.get("skin_temp_celsius"),
                    "status": self._get_recovery_status(score_data.get("recovery_score", 0))
                }
        except Exception as e:
            logger.error(f"Failed to fetch recovery: {e}")

        try:
            # Get latest sleep
            sleep = await self.get_latest_sleep()
            if sleep:
                score_data = sleep.get("score", {})
                summary["sleep"] = {
                    "total_hours": self._milli_to_hours(score_data.get("stage_summary", {}).get("total_in_bed_time_milli", 0)),
                    "sleep_hours": self._milli_to_hours(score_data.get("stage_summary", {}).get("total_sleep_time_milli", 0)),
                    "efficiency": score_data.get("sleep_efficiency_percentage"),
                    "performance": score_data.get("sleep_performance_percentage"),
                    "rem_hours": self._milli_to_hours(score_data.get("stage_summary", {}).get("total_rem_sleep_time_milli", 0)),
                    "deep_hours": self._milli_to_hours(score_data.get("stage_summary", {}).get("total_slow_wave_sleep_time_milli", 0)),
                }
        except Exception as e:
            logger.error(f"Failed to fetch sleep: {e}")

        try:
            # Get today's strain
            cycle = await self.get_today_strain()
            if cycle:
                score_data = cycle.get("score", {})
                summary["strain"] = {
                    "score": score_data.get("strain"),
                    "kilojoules": score_data.get("kilojoule"),
                    "avg_hr": score_data.get("average_heart_rate"),
                    "max_hr": score_data.get("max_heart_rate"),
                    "status": self._get_strain_status(score_data.get("strain", 0))
                }
        except Exception as e:
            logger.error(f"Failed to fetch strain: {e}")

        try:
            # Get today's workouts
            workouts = await self.get_today_workouts()
            for workout in workouts:
                score_data = workout.get("score", {})
                summary["workouts"].append({
                    "sport_id": workout.get("sport_id"),
                    "strain": score_data.get("strain"),
                    "kilojoules": score_data.get("kilojoule"),
                    "avg_hr": score_data.get("average_heart_rate"),
                    "max_hr": score_data.get("max_heart_rate"),
                    "duration_minutes": self._milli_to_minutes(
                        self._parse_duration(workout.get("start"), workout.get("end"))
                    ),
                })
        except Exception as e:
            logger.error(f"Failed to fetch workouts: {e}")

        # Generate insights
        summary["insights"] = self._generate_insights(summary)

        return summary

    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _milli_to_hours(milli: int) -> float:
        """Convert milliseconds to hours."""
        if not milli:
            return 0.0
        return round(milli / (1000 * 60 * 60), 1)

    @staticmethod
    def _milli_to_minutes(milli: int) -> int:
        """Convert milliseconds to minutes."""
        if not milli:
            return 0
        return int(milli / (1000 * 60))

    @staticmethod
    def _parse_duration(start: str, end: str) -> int:
        """Parse duration in milliseconds from start/end times."""
        if not start or not end:
            return 0
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return int((end_dt - start_dt).total_seconds() * 1000)
        except:
            return 0

    @staticmethod
    def _get_recovery_status(score: float) -> str:
        """Get recovery status label."""
        if score >= 67:
            return "GREEN"  # Ready to perform
        elif score >= 34:
            return "YELLOW"  # Moderate recovery
        else:
            return "RED"  # Need rest

    @staticmethod
    def _get_strain_status(strain: float) -> str:
        """Get strain status label."""
        if strain >= 18:
            return "OVERREACHING"
        elif strain >= 14:
            return "HIGH"
        elif strain >= 10:
            return "MODERATE"
        else:
            return "LOW"

    def _generate_insights(self, summary: Dict) -> List[str]:
        """Generate coaching insights from Whoop data."""
        insights = []

        recovery = summary.get("recovery")
        sleep = summary.get("sleep")
        strain = summary.get("strain")

        if recovery:
            score = recovery.get("score", 0)
            if score < 34:
                insights.append(f"RECOVERY IS RED ({score}%). Prioritize rest and recovery activities today.")
            elif score < 67:
                insights.append(f"RECOVERY IS YELLOW ({score}%). Moderate activity recommended.")
            else:
                insights.append(f"RECOVERY IS GREEN ({score}%). You're ready to push hard!")

        if sleep:
            hours = sleep.get("sleep_hours", 0)
            if hours < 6:
                insights.append(f"SLEEP DEFICIT: Only {hours} hours. This will impact recovery.")
            elif hours < 7:
                insights.append(f"Sleep was {hours} hours. Aim for 7-9 hours tonight.")

        if strain:
            strain_score = strain.get("score", 0)
            if recovery and recovery.get("score", 100) < 50 and strain_score > 10:
                insights.append("WARNING: High strain on low recovery. Risk of overtraining.")

        return insights

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# ═══════════════════════════════════════════════════════════════
# DISCREPANCY DETECTOR
# ═══════════════════════════════════════════════════════════════

class DiscrepancyDetector:
    """
    Detects discrepancies between user self-reports and Whoop data.
    This is the ACCOUNTABILITY engine.
    """

    def __init__(self, whoop_service: WhoopService):
        self.whoop = whoop_service

    async def check_workout_claim(self, user_claim: str, intensity_claimed: str = "high") -> Dict[str, Any]:
        """
        Check if user's workout claim matches Whoop data.

        Args:
            user_claim: What the user said (e.g., "I crushed my workout")
            intensity_claimed: "high", "moderate", or "low"

        Returns:
            Dict with verification result and confrontation message
        """
        result = {
            "verified": False,
            "whoop_data": None,
            "discrepancy": None,
            "message": None
        }

        try:
            summary = await self.whoop.get_daily_summary()
            strain = summary.get("strain", {})
            workouts = summary.get("workouts", [])

            strain_score = strain.get("score", 0) if strain else 0
            result["whoop_data"] = {
                "strain": strain_score,
                "workouts": len(workouts),
                "workout_details": workouts
            }

            # Check based on intensity claimed
            if intensity_claimed == "high":
                threshold = 14.0
            elif intensity_claimed == "moderate":
                threshold = 10.0
            else:
                threshold = 6.0

            if strain_score >= threshold:
                result["verified"] = True
                result["message"] = f"VERIFIED! Whoop confirms strain of {strain_score:.1f}. OUTSTANDING WORK, WARRIOR!"
            else:
                result["verified"] = False
                result["discrepancy"] = f"Claimed {intensity_claimed} intensity but Whoop shows strain of {strain_score:.1f}"

                if strain_score < 5:
                    result["message"] = f"Your Whoop says strain is {strain_score:.1f}. That's basically SITTING ON THE COUCH. Where's the workout you claimed?"
                elif strain_score < 10:
                    result["message"] = f"Whoop recorded strain of {strain_score:.1f}. That's a WARM-UP, not a workout. Don't lie to yourself."
                else:
                    result["message"] = f"Whoop shows strain of {strain_score:.1f}. Decent, but not the 'crushing it' you claimed. Be honest."

        except Exception as e:
            logger.error(f"Error checking workout claim: {e}")
            result["message"] = "Could not verify with Whoop. But I'm watching you..."

        return result

    async def check_sleep_claim(self, hours_claimed: float) -> Dict[str, Any]:
        """
        Check if user's sleep claim matches Whoop data.
        """
        result = {
            "verified": False,
            "whoop_data": None,
            "discrepancy": None,
            "message": None
        }

        try:
            summary = await self.whoop.get_daily_summary()
            sleep = summary.get("sleep", {})

            if sleep:
                actual_hours = sleep.get("sleep_hours", 0)
                result["whoop_data"] = sleep

                # Allow 30 min tolerance
                tolerance = 0.5
                difference = abs(hours_claimed - actual_hours)

                if difference <= tolerance:
                    result["verified"] = True
                    result["message"] = f"VERIFIED. Whoop confirms {actual_hours} hours of sleep. GOOD REPORT, WARRIOR."
                else:
                    result["verified"] = False
                    result["discrepancy"] = f"Claimed {hours_claimed}h but Whoop recorded {actual_hours}h"

                    if hours_claimed > actual_hours:
                        result["message"] = f"You said {hours_claimed} hours. Whoop says {actual_hours} hours. That's a {difference:.1f} hour LIE. Stop deceiving yourself."
                    else:
                        result["message"] = f"Actually, you got MORE sleep than you thought ({actual_hours}h vs {hours_claimed}h claimed). Know your data!"

        except Exception as e:
            logger.error(f"Error checking sleep claim: {e}")
            result["message"] = "Could not verify sleep with Whoop."

        return result

    async def check_recovery_for_training(self) -> Dict[str, Any]:
        """
        Check if user should train hard today based on recovery.
        """
        result = {
            "can_train_hard": False,
            "recovery_score": None,
            "recommendation": None,
            "message": None
        }

        try:
            summary = await self.whoop.get_daily_summary()
            recovery = summary.get("recovery", {})

            if recovery:
                score = recovery.get("score", 0)
                result["recovery_score"] = score
                result["whoop_data"] = recovery

                if score >= 67:
                    result["can_train_hard"] = True
                    result["recommendation"] = "HIGH_INTENSITY"
                    result["message"] = f"Recovery is GREEN at {score}%. Your body is READY. Time to ATTACK that workout!"
                elif score >= 34:
                    result["can_train_hard"] = True  # Can train, but moderate
                    result["recommendation"] = "MODERATE_INTENSITY"
                    result["message"] = f"Recovery is YELLOW at {score}%. You can train, but don't overdo it. Listen to your body."
                else:
                    result["can_train_hard"] = False
                    result["recommendation"] = "ACTIVE_RECOVERY"
                    result["message"] = f"Recovery is RED at {score}%. Your body needs REST. Today is active recovery - walking, stretching, yoga. No excuses to skip rest."

        except Exception as e:
            logger.error(f"Error checking recovery: {e}")
            result["message"] = "Could not fetch recovery data. Proceed with caution."

        return result

    async def get_accountability_report(self) -> Dict[str, Any]:
        """
        Generate a full accountability report comparing user behavior to Whoop data.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "whoop_summary": None,
            "discrepancies": [],
            "praise": [],
            "warnings": [],
            "overall_assessment": None
        }

        try:
            summary = await self.whoop.get_daily_summary()
            report["whoop_summary"] = summary

            # Analyze recovery
            recovery = summary.get("recovery", {})
            if recovery:
                score = recovery.get("score", 0)
                if score < 34:
                    report["warnings"].append(f"Recovery critically low ({score}%). Rest is mandatory.")
                elif score >= 67:
                    report["praise"].append(f"Excellent recovery ({score}%). Body is ready to perform!")

            # Analyze sleep
            sleep = summary.get("sleep", {})
            if sleep:
                hours = sleep.get("sleep_hours", 0)
                if hours < 6:
                    report["warnings"].append(f"Sleep deficit detected ({hours}h). This impacts everything.")
                elif hours >= 7.5:
                    report["praise"].append(f"Solid sleep ({hours}h). Good discipline!")

            # Analyze strain
            strain = summary.get("strain", {})
            if strain:
                strain_score = strain.get("score", 0)
                recovery_score = recovery.get("score", 100) if recovery else 100

                if recovery_score < 50 and strain_score > 14:
                    report["warnings"].append(f"HIGH STRAIN ({strain_score}) on LOW RECOVERY ({recovery_score}%). Overtraining risk!")
                elif strain_score >= 14 and recovery_score >= 67:
                    report["praise"].append(f"Pushed hard (strain {strain_score}) with good recovery. WARRIOR mode!")

            # Overall assessment
            praise_count = len(report["praise"])
            warning_count = len(report["warnings"])

            if warning_count == 0 and praise_count > 0:
                report["overall_assessment"] = "OUTSTANDING! You're executing like a true Spartan."
            elif warning_count > praise_count:
                report["overall_assessment"] = "ATTENTION NEEDED. Review the warnings and adjust."
            else:
                report["overall_assessment"] = "ACCEPTABLE. Keep pushing, stay disciplined."

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            report["overall_assessment"] = "Could not generate full report. Check Whoop connection."

        return report


# ═══════════════════════════════════════════════════════════════
# SPORT ID MAPPING (Whoop uses numeric IDs for workout types)
# ═══════════════════════════════════════════════════════════════

WHOOP_SPORTS = {
    0: "Running",
    1: "Cycling",
    16: "Baseball",
    17: "Basketball",
    18: "Rowing",
    19: "Fencing",
    20: "Field Hockey",
    21: "Football",
    22: "Golf",
    24: "Ice Hockey",
    25: "Lacrosse",
    27: "Rugby",
    28: "Sailing",
    29: "Skiing",
    30: "Soccer",
    31: "Softball",
    32: "Squash",
    33: "Swimming",
    34: "Tennis",
    35: "Track & Field",
    36: "Volleyball",
    37: "Water Polo",
    38: "Wrestling",
    39: "Boxing",
    42: "Dance",
    43: "Pilates",
    44: "Yoga",
    45: "Weightlifting",
    47: "Cross Country Skiing",
    48: "Functional Fitness",
    49: "Duathlon",
    51: "Gymnastics",
    52: "Hiking/Rucking",
    53: "Horseback Riding",
    55: "Kayaking",
    56: "Martial Arts",
    57: "Mountain Biking",
    59: "Powerlifting",
    60: "Rock Climbing",
    61: "Paddleboarding",
    62: "Triathlon",
    63: "Walking",
    64: "Surfing",
    65: "Elliptical",
    66: "Stairmaster",
    70: "Meditation",
    71: "Other",
    73: "Diving",
    74: "Operations - Loss",
    75: "Operations - Medical",
    76: "Operations - Flying",
    77: "Operations - Water",
    82: "Ultimate",
    83: "Climber",
    84: "Jumping Rope",
    85: "Australian Football",
    86: "Skateboarding",
    87: "Coaching",
    88: "Ice Bath",
    89: "Commuting",
    90: "Gaming",
    91: "Snowboarding",
    92: "Motocross",
    93: "Caddying",
    94: "Obstacle Course Racing",
    95: "Motor Racing",
    96: "HIIT",
    97: "Spin",
    98: "Jiu Jitsu",
    99: "Manual Labor",
    100: "Cricket",
    101: "Pickleball",
    102: "Inline Skating",
    103: "Operations - Tactical",
    104: "Stretching",
    105: "Wheelchair Pushing",
    106: "Paddle Tennis",
    107: "Barre",
    108: "Stage Performance",
    109: "High Stress Work",
    110: "Parkour",
    111: "Gaelic Football",
    112: "Hurling/Camogie",
    113: "Circus Arts",
    121: "Massage Therapy",
    125: "Watching Sports",
    126: "Assault Bike",
    260: "Sex"
}

def get_sport_name(sport_id: int) -> str:
    """Get human-readable sport name from Whoop sport ID."""
    return WHOOP_SPORTS.get(sport_id, f"Activity #{sport_id}")
