"""
Google Calendar Integration Service for Spartan Coach.
Provides calendar event fetching and gap analysis for proactive coaching.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger("SpartanCoach.Calendar")


class CalendarService:
    """Service for Google Calendar integration and gap analysis."""

    def __init__(self, credentials: Optional[Dict] = None):
        """
        Initialize the calendar service.

        Args:
            credentials: Google OAuth credentials dict with access_token, refresh_token, etc.
        """
        self.credentials = credentials
        self.service = None

        if credentials:
            self._init_service()

    def _init_service(self):
        """Initialize the Google Calendar API service."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=self.credentials.get('access_token'),
                refresh_token=self.credentials.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.credentials.get('client_id'),
                client_secret=self.credentials.get('client_secret')
            )
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Calendar service: {e}")
            self.service = None

    def get_today_events(self) -> List[Dict]:
        """
        Fetch all events for today from the user's primary calendar.

        Returns:
            List of event dictionaries with start, end, summary
        """
        if not self.service:
            logger.warning("Calendar service not initialized, returning empty events")
            return []

        try:
            now = datetime.utcnow()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_of_day.isoformat() + 'Z',
                timeMax=end_of_day.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime',
                maxResults=50
            ).execute()

            events = events_result.get('items', [])

            # Parse and normalize events
            parsed_events = []
            for event in events:
                start = event.get('start', {})
                end = event.get('end', {})

                # Skip all-day events (they have 'date' instead of 'dateTime')
                if 'dateTime' not in start:
                    continue

                parsed_events.append({
                    'id': event.get('id'),
                    'summary': event.get('summary', 'Busy'),
                    'start': start.get('dateTime'),
                    'end': end.get('dateTime'),
                    'location': event.get('location', ''),
                    'description': event.get('description', '')[:100] if event.get('description') else ''
                })

            logger.info(f"Fetched {len(parsed_events)} events for today")
            return parsed_events

        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return []

    def find_gaps(
        self,
        events: List[Dict],
        wake_time: str = "07:00",
        sleep_time: str = "22:00",
        min_gap_minutes: int = 15
    ) -> List[Dict]:
        """
        Find available time gaps between events.

        Args:
            events: List of event dictionaries
            wake_time: User's wake time (HH:MM format)
            sleep_time: User's sleep time (HH:MM format)
            min_gap_minutes: Minimum gap duration to include

        Returns:
            List of gap dictionaries with start, end, duration, time_of_day
        """
        gaps = []
        now = datetime.now()
        today = now.date()

        # Parse wake and sleep times
        wake_hour, wake_min = map(int, wake_time.split(':'))
        sleep_hour, sleep_min = map(int, sleep_time.split(':'))

        wake_dt = datetime.combine(today, datetime.min.time().replace(hour=wake_hour, minute=wake_min))
        sleep_dt = datetime.combine(today, datetime.min.time().replace(hour=sleep_hour, minute=sleep_min))

        # Filter and sort events
        valid_events = []
        for event in events:
            if event.get('start') and event.get('end'):
                try:
                    start = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).replace(tzinfo=None)
                    end = datetime.fromisoformat(event['end'].replace('Z', '+00:00')).replace(tzinfo=None)
                    valid_events.append({'start': start, 'end': end, 'summary': event.get('summary', '')})
                except ValueError:
                    continue

        valid_events.sort(key=lambda e: e['start'])

        # Start from current time or wake time (whichever is later)
        current_time = max(now, wake_dt)

        for event in valid_events:
            event_start = event['start']
            event_end = event['end']

            # Skip past events
            if event_end <= current_time:
                continue

            # Skip events that start after sleep time
            if event_start >= sleep_dt:
                break

            # Check for gap before this event
            if event_start > current_time:
                gap_end = min(event_start, sleep_dt)
                gap_duration = (gap_end - current_time).total_seconds() / 60

                if gap_duration >= min_gap_minutes:
                    gaps.append({
                        'start': current_time.isoformat(),
                        'end': gap_end.isoformat(),
                        'duration_minutes': int(gap_duration),
                        'time_of_day': self._classify_time(current_time),
                        'next_event': event.get('summary', 'Unknown')
                    })

            # Move current time to end of this event
            current_time = max(current_time, event_end)

        # Add gap from last event to sleep time
        if current_time < sleep_dt:
            gap_duration = (sleep_dt - current_time).total_seconds() / 60
            if gap_duration >= min_gap_minutes:
                gaps.append({
                    'start': current_time.isoformat(),
                    'end': sleep_dt.isoformat(),
                    'duration_minutes': int(gap_duration),
                    'time_of_day': self._classify_time(current_time),
                    'next_event': 'End of day'
                })

        logger.info(f"Found {len(gaps)} gaps in calendar")
        return gaps

    def _classify_time(self, dt: datetime) -> str:
        """
        Classify time of day for workout recommendations.

        Args:
            dt: datetime object

        Returns:
            'morning', 'afternoon', or 'evening'
        """
        hour = dt.hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

    def get_current_gap(self, gaps: List[Dict]) -> Optional[Dict]:
        """
        Find if there's a gap happening right now.

        Args:
            gaps: List of gap dictionaries

        Returns:
            Current gap dict or None
        """
        now = datetime.now()

        for gap in gaps:
            gap_start = datetime.fromisoformat(gap['start'])
            gap_end = datetime.fromisoformat(gap['end'])

            if gap_start <= now <= gap_end:
                remaining = int((gap_end - now).total_seconds() / 60)
                return {
                    **gap,
                    'remaining_minutes': remaining
                }

        return None

    def get_next_event(self, events: List[Dict]) -> Optional[Dict]:
        """
        Find the next upcoming event.

        Args:
            events: List of event dictionaries

        Returns:
            Next event dict with minutes_until, or None
        """
        now = datetime.now()

        for event in events:
            if not event.get('start'):
                continue

            try:
                event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).replace(tzinfo=None)

                if event_start > now:
                    minutes_until = int((event_start - now).total_seconds() / 60)
                    return {
                        'summary': event.get('summary', 'Unknown'),
                        'start': event['start'],
                        'minutes_until': minutes_until
                    }
            except ValueError:
                continue

        return None


def get_workout_suggestions(gap_duration: int, time_of_day: str) -> List[Dict]:
    """
    Get workout suggestions based on available time and time of day.

    Args:
        gap_duration: Available minutes
        time_of_day: 'morning', 'afternoon', or 'evening'

    Returns:
        List of workout suggestions
    """
    suggestions = []

    if time_of_day == "morning":
        if gap_duration >= 15:
            suggestions.append({
                "name": "Morning Energizer",
                "duration": 15,
                "exercises": "50 push-ups, 30 squats, 20 burpees",
                "intensity": "high"
            })
        if gap_duration >= 30:
            suggestions.append({
                "name": "Full Morning Routine",
                "duration": 30,
                "exercises": "100 push-ups, 50 pull-ups, 100 squats, 50 lunges",
                "intensity": "high"
            })

    elif time_of_day == "afternoon":
        if gap_duration >= 10:
            suggestions.append({
                "name": "Standing Break",
                "duration": 10,
                "exercises": "Walk around, stretches, 20 squats",
                "intensity": "low"
            })
        if gap_duration >= 20:
            suggestions.append({
                "name": "Desk Warrior",
                "duration": 20,
                "exercises": "30 push-ups, 15 pull-ups, 2-minute plank, stretches",
                "intensity": "medium"
            })
        if gap_duration >= 45:
            suggestions.append({
                "name": "Afternoon Power Session",
                "duration": 45,
                "exercises": "Full body workout or 30-min walk + 15-min strength",
                "intensity": "medium"
            })

    else:  # evening
        if gap_duration >= 30:
            suggestions.append({
                "name": "Evening Walk",
                "duration": 30,
                "exercises": "Brisk walk (3,500 steps)",
                "intensity": "low"
            })
        if gap_duration >= 45:
            suggestions.append({
                "name": "Step Crusher",
                "duration": 45,
                "exercises": "45-min walk or jog (4,500-5,000 steps)",
                "intensity": "medium"
            })
        if gap_duration >= 60:
            suggestions.append({
                "name": "Sport Session",
                "duration": 60,
                "exercises": "Basketball, tennis, or running (6,000+ steps)",
                "intensity": "high"
            })

    return suggestions
