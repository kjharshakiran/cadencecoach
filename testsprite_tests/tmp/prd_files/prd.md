# Spartan Coach - Product Requirements Document

## Overview
Spartan Coach is an AI-powered fitness accountability application that uses a multi-agent architecture to provide personalized fitness and nutrition planning with strict accountability.

## Target Users
- Individuals seeking personalized fitness guidance
- Users who need accountability and discipline in their fitness journey
- People who want integrated fitness tracking with Whoop devices
- Users comfortable with AI-driven coaching

## Core Features

### 1. User Onboarding
- **Profile Creation**: Users provide age, height, weight, fitness goals, target dates
- **Authentication**: Support for username/password and Google OAuth
- **Profile Persistence**: Multi-user support with session management

### 2. Fitness Planning
- **BMR/TDEE Calculation**: Automatic calculation using Mifflin-St Jeor equation
- **7-Day Workout Plans**: Customized based on workout split preferences and available equipment
- **Exercise Library**: Comprehensive exercise database with form guidance
- **Plan Confirmation**: Users must confirm/lock plans before execution

### 3. Nutrition Planning
- **Diet Principles**: Strategic nutrition approach based on goals (cutting/bulking/maintenance)
- **Daily Meal Plans**: Specific meal suggestions with macros
- **Calorie Targets**: Based on TDEE calculations and goals

### 4. Progress Monitoring
- **Daily Check-ins**: Automated check-ins at 9AM, 12PM, 3PM, 9PM (timezone-aware)
- **Progress Logs**: Text-based log entries
- **Whoop Integration**: Fitness tracker data analysis via screenshot uploads
- **Metric Tracking**: JSON-formatted metrics from monitoring agent

### 5. Integrations
- **Google Calendar**: Workout scheduling and reminders
- **Whoop**: Fitness tracker data synchronization
- **WhatsApp**: Two-way chat interface for mobile access

### 6. Multi-Agent System
- **THE_SPARTAN**: Root orchestrator agent
- **Planner Agent**: Creates comprehensive fitness plans
- **Fitness Agent**: Generates workout routines
- **Nutrition Agent**: Develops meal plans
- **Monitoring Agent**: Analyzes progress and provides feedback

## API Endpoints

### Authentication
- `POST /auth/login` - Username/password login
- `GET /auth/google` - Google OAuth flow
- `POST /auth/logout` - Session logout

### Core Functionality
- `POST /api/chat` - Main chat interface with agents
- `POST /api/onboard` - User onboarding flow
- `GET /api/state` - Get current session state
- `POST /api/reset` - Reset session and plans

### Integrations
- `GET /auth/whoop` - Whoop OAuth
- `POST /whatsapp/webhook` - WhatsApp message handling

## Technical Requirements

### Backend
- FastAPI server on port 8000
- SQLite database for session storage
- Google ADK for agent orchestration
- LiteLLM for multi-provider LLM support (Claude/Gemini)
- APScheduler for automated check-ins

### Frontend
- Vanilla JavaScript SPA
- Chart.js for progress visualization
- Responsive design
- Dark theme with red accents

### Security
- Session-based authentication
- OAuth 2.0 for Google/Whoop
- Password hashing (SHA-256)
- CORS configuration

### Performance
- LLM retry logic with exponential backoff
- Session state caching
- Efficient database queries

## User Flows

### Onboarding Flow
1. User accesses application
2. Login/authentication
3. Profile creation (if new user)
4. Goal setting
5. Plan generation by planner_agent
6. Plan review and confirmation
7. Plan locked for execution

### Daily Usage Flow
1. User receives automated check-in
2. User logs progress (text or Whoop screenshot)
3. Monitoring agent analyzes data
4. Agent provides feedback and adjustments
5. User follows daily workout/meal plan

### Plan Modification Flow
1. User requests plan changes
2. THE_SPARTAN routes to appropriate agent
3. Agent generates modifications
4. User reviews and confirms
5. Plan updated and re-locked

## Success Metrics
- User engagement (daily check-ins completed)
- Plan completion rates
- User retention
- Goal achievement rates
- Response time of agent interactions

## Future Enhancements
- Mobile app (iOS/Android)
- Additional fitness tracker integrations
- Social features (accountability partners)
- Advanced analytics and insights
- Meal prep guides
- Exercise video demonstrations
