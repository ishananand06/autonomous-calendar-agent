# Autonomous LLM Scheduling Agent

An opinionated, serverless scheduling assistant accessed via WhatsApp. Unlike standard calendar tools that blindly schedule tasks, this agent acts as a constraint satisfaction engine. It evaluates your current Google Calendar state against predefined cognitive load limits and actively pushes back if a requested task exceeds your daily bandwidth.

## Core Features
* **WhatsApp Interface:** Natural language input via Meta's WhatsApp Cloud API webhook.
* **State Management:** Real-time bi-directional sync with Google Calendar API.
* **Cognitive Load Protection:** Enforces a maximum daily limit of deep-work hours.
* **Habit Anchoring:** Automatically protects time for non-negotiable daily routines.

## Example Interaction
**User:** "Add 3 hours of debugging the people tracking model tomorrow afternoon."
**Agent:** "I cannot schedule 3 hours for tomorrow. You already have 6 hours blocked for Audio Medusa and your daily 45-minute LeetCode session. Adding this pushes you over your 8-hour cognitive limit. Should I move the people tracking work to Friday, or do you want to cancel the Audio Medusa block?"

## Architecture (Python)
1. `main.py`: FastAPI server handling the WhatsApp webhook payload asynchronously.
2. `agent.py`: Google Gemini API integration with strict System Instructions and Tool Calling.
3. `calendar_tools.py`: Google Calendar API authentication, event retrieval, and event insertion.

## Local Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your Gemini and Google Cloud credentials.
4. Run the local server: `uvicorn main:app --reload`