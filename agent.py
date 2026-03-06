import os
import json
import datetime
import zoneinfo
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv
from calendar_tools import authenticate_google_calendar, get_upcoming_events, add_calendar_event

load_dotenv()

# Create the master client object
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CONFIG_FILE = "user_config.json"

# Lazily initialised so tests that don't touch the calendar don't require auth
_calendar_service = None

def _get_calendar_service():
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = authenticate_google_calendar()
    return _calendar_service

def load_user_preferences():
    """Loads preferences from the JSON file."""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_user_preferences(prefs):
    """Saves updated preferences back to the JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(prefs, f, indent=4)

def get_system_prompt(prefs):
    today = datetime.date.today().isoformat()
    return f"""
    You are an autonomous constraint-satisfaction scheduling assistant. Today's date is {today}.

    ═══════════════════════════════════════════════
    CURRENT STATE
    ═══════════════════════════════════════════════
    1. Max Daily Cognitive Load : {prefs.get('daily_cognitive_limit_hours', 8)} hours/day
    2. User Timezone        : {prefs.get('timezone', 'UTC')}
    3. Active Habits            : {json.dumps(prefs.get('habits', []))}
    4. Active Projects          : {json.dumps(prefs.get('projects', []))}
    5. Active Deadlines         : {json.dumps(prefs.get('active_deadlines', []))}

    ═══════════════════════════════════════════════
    COGNITIVE MATH (apply strictly)
    ═══════════════════════════════════════════════
    - Meals, exercise, travel       → 0 cognitive hours consumed
    - Classes, deep work, studying  → consumes cognitive hours
    - Track remaining bandwidth = daily_limit − scheduled cognitive hours

    ═══════════════════════════════════════════════
    CALENDAR CLASSIFICATION
    ═══════════════════════════════════════════════
    Classify every calendar event as HARD or SOFT before scheduling decisions:

    HARD events (cannot be moved):
      → Classes (APL105, COL106, etc.), meetings with others, flights, appointments
      → If asked to schedule over one: "This time is blocked for a hard commitment and cannot be changed."

    SOFT events (flexible, can be traded):
      → Solo study sessions, reading a paper, coding practice, flexible project blocks
      → If cognitive bandwidth is exhausted but a high-priority task needs scheduling,
        scan for SOFT events and propose a trade-off:
        "You have 2 hrs blocked for reading a paper. Since that's flexible, should I
        replace it with this urgent task?"

    ═══════════════════════════════════════════════
    STATE MANAGEMENT (tool: update_preferences)
    ═══════════════════════════════════════════════
    You have full CRUD access to the user's config via update_preferences.

    DIRECT UPDATES (act immediately, no clarification needed):
      • Cognitive limit change → "change my limit to 10 hours"
        ↳ Call update_preferences with key 'daily_cognitive_limit_hours'
      • Urgency/context update → "The Among Us project is getting super urgent"
        ↳ Call update_preferences with key 'project_context:<name>'
      • New deadline → "Prep for mentor meeting next week, takes 4 hours"
        ↳ Call update_preferences with key 'deadline_add'
           Required fields: task, due_date (YYYY-MM-DD format), hours_needed
      • Partial completion → Call update_preferences with key 'deadline_update_hours:<task>'

    ASK FIRST, THEN UPDATE (new projects or habits):
      • Do NOT add blindly. Ask:
        - "What is the priority or context for this?"
        - "How long does it usually take per session?"
      • Only call update_preferences after the user responds.

    ═══════════════════════════════════════════════
    PROACTIVE SCHEDULING
    ═══════════════════════════════════════════════
    On every calendar check:
    1. Scan Active Deadlines for approaching due dates (≤ 3 days away).
    2. If the user has open cognitive bandwidth today AND a deadline is close,
       proactively suggest scheduling a work block:
       "You have 3 hrs free today and [Task X] is due in 2 days (needs Y hrs).
        Want me to block time this afternoon to chip away at it?"
    3. Distribute hours_needed across available days before the due_date when helpful.

    ═══════════════════════════════════════════════
    CONFIRMATION RULE (non-negotiable)
    ═══════════════════════════════════════════════
    ALWAYS get explicit user confirmation before calling create_event,
    especially when modifying, overriding, or trading existing schedule blocks.
    """

# ── Tool functions exposed to Gemini ─────────────────────────────────────────

def check_calendar(date: str) -> dict:
    """
    Returns all Google Calendar events for a single day.

    Args:
        date: Target date in YYYY-MM-DD format.
    """
    service = _get_calendar_service()
    prefs = load_user_preferences()
    tz = zoneinfo.ZoneInfo(prefs.get('timezone', 'UTC'))
    # Use local midnight so the window matches the user's calendar day, not UTC's
    day_start = datetime.datetime(
        *[int(x) for x in date.split('-')], 0, 0, 0, tzinfo=tz
    )
    day_end = day_start + datetime.timedelta(days=1)
    events = get_upcoming_events(
        service,
        time_min=day_start.isoformat(),
        time_max=day_end.isoformat(),
    )
    # Return only the fields the model needs to reason about cognitive load
    simplified = [
        {
            "summary": e.get("summary", "Untitled"),
            "start":   e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end":     e.get("end",   {}).get("dateTime") or e.get("end",   {}).get("date"),
        }
        for e in events
    ]
    return {"date": date, "events": simplified}

def create_event(summary: str, start_datetime: str, end_datetime: str) -> dict:
    """
    Creates a new event on the user's Google Calendar.

    Args:
        summary: Title of the event.
        start_datetime: ISO 8601 start (e.g. '2026-03-05T09:00:00').
        end_datetime:   ISO 8601 end   (e.g. '2026-03-05T12:00:00').
    """
    service = _get_calendar_service()
    prefs = load_user_preferences()
    timezone = prefs.get('timezone', 'UTC')
    event = add_calendar_event(service, summary, start_datetime, end_datetime, timezone=timezone)
    return {"event_id": event.get("id"), "html_link": event.get("htmlLink")}

def update_preferences(key: str, value) -> dict:
    """
    Persists a change to the user's scheduling preferences.
    
    Supported keys:
    'daily_cognitive_limit_hours', 'timezone'
    'habit_add' (value: dict with name, duration_minutes, frequency, context)
    'habit_remove:<name>', 'habit_context:<name>' (updates context string)
    'project_add' (value: dict with name, context)
    'project_remove:<name>'
    'project_context:<name>' (updates the context string)
    'deadline_add' (value: dict with task, due_date YYYY-MM-DD, hours_needed)
    'deadline_remove:<task>'
    'deadline_update_hours:<task>' (value: new float hours remaining)
    """
    prefs = load_user_preferences()

    if key == "daily_cognitive_limit_hours":
        prefs["daily_cognitive_limit_hours"] = int(value)
    elif key == "timezone":
        prefs["timezone"] = str(value)
        
    # --- Habit Management ---
    elif key == "habit_add":
        prefs.setdefault("habits", []).append({
            "name": value["name"],
            "duration_minutes": int(value["duration_minutes"]),
            "frequency": value.get("frequency", "daily"),
            "context": value.get("context", "Standard habit.")
        })
    elif key.startswith("habit_remove:"):
        name = key.split(":", 1)[1]
        prefs["habits"] = [h for h in prefs.get("habits", []) if h["name"].lower() != name.lower()]
    elif key.startswith("habit_context:"):
        name = key.split(":", 1)[1]
        for h in prefs.get("habits", []):
            if h["name"].lower() == name.lower():
                h["context"] = str(value)
                break

    # --- Project Management ---
    elif key == "project_add":
        prefs.setdefault("projects", []).append({
            "name": value["name"],
            "context": value.get("context", "New project.")
        })
    elif key.startswith("project_remove:"):
        name = key.split(":", 1)[1]
        prefs["projects"] = [p for p in prefs.get("projects", []) if p["name"].lower() != name.lower()]
    elif key.startswith("project_context:"):
        name = key.split(":", 1)[1]
        for p in prefs.get("projects", []):
            if p["name"].lower() == name.lower():
                p["context"] = str(value)
                break
    
    # --- Deadline Management ---
    elif key == "deadline_add":
        prefs.setdefault("active_deadlines", []).append({
            "task": value["task"],
            "hours_needed": float(value["hours_needed"]),
            "due_date": value["due_date"] # Must be YYYY-MM-DD
        })
    elif key.startswith("deadline_remove:"):
        task_name = key.split(":", 1)[1]
        prefs["active_deadlines"] = [d for d in prefs.get("active_deadlines", []) if d["task"].lower() != task_name.lower()]
    elif key.startswith("deadline_update_hours:"):
        task_name = key.split(":", 1)[1]
        for d in prefs.get("active_deadlines", []):
            if d["task"].lower() == task_name.lower():
                d["hours_needed"] = float(value)
                break
    
    else:
        return {"error": f"Unknown preference key: '{key}'"}

    save_user_preferences(prefs)
    return {"updated": key, "new_value": value}

# ─────────────────────────────────────────────────────────────────────────────

def cleanup_expired_deadlines():
    """Silently removes deadlines from user_config.json that are in the past."""
    prefs = load_user_preferences()
    today = datetime.date.today().isoformat()
    
    deadlines = prefs.get("active_deadlines", [])
    if not deadlines:
        return prefs

    # Keep only deadlines where the due_date is today or in the future
    valid_deadlines = [d for d in deadlines if d.get("due_date", "") >= today]
    
    # Only save to disk if something was actually deleted to save I/O operations
    if len(valid_deadlines) < len(deadlines):
        prefs["active_deadlines"] = valid_deadlines
        save_user_preferences(prefs)
        
    return prefs

FALLBACK_MODELS = [
    'gemini-3-flash-preview',          # Primary: Best reasoning for complex logic
    'gemini-3.1-flash-lite-preview',   # Fallback 1: Fast, scalable, adjustable thinking
    'gemini-2.5-flash'         # Fallback 2: The old reliable workhorse
]

def process_whatsapp_message(user_message: str, chat_history=None):
    """
    Routes a WhatsApp message through Gemini with live tool calling.
    Includes a Model Fallback cascade if the primary model hits its daily quota.
    """
    prefs = cleanup_expired_deadlines()
    
    MAX_HISTORY = 20
    trimmed_history = (chat_history or [])[-MAX_HISTORY:]

    # --- MODEL FALLBACK CASCADE ---
    for model_name in FALLBACK_MODELS:
        try:
            print(f"🧠 Attempting inference with {model_name}...")
            
            # 1. Package the prompt and tools into the new Config object
            config = types.GenerateContentConfig(
                system_instruction=get_system_prompt(prefs),
                tools=[check_calendar, create_event, update_preferences],
            )

            # 2. Create the chat session using the new client
            chat = client.chats.create(
                model=model_name,
                config=config,
                history=trimmed_history
            )
            
            # 3. Send the message
            response = chat.send_message(user_message)
            
            # Note: The new SDK uses .get_history() instead of .history
            return response.text, chat.get_history()
            
        except APIError as e:
            # The new SDK packages HTTP errors cleanly inside APIError
            if e.code == 429:
                print(f"⚠️ {model_name} hit its rate limit (429). Cascading to next model...")
                continue 
            else:
                print(f"❌ Unexpected API error with {model_name}: {e}")
                return "I encountered an unexpected internal error. Please check the server logs.", chat_history

        except Exception as e:
            print(f"❌ System error with {model_name}: {e}")
            return "I encountered an unexpected internal error. Please check the server logs.", chat_history
        
    # If the loop finishes, you have literally exhausted every model's free tier
    print("❌ All models in the fallback cascade are rate limited.")
    return "I am completely out of cognitive bandwidth for the day across all my models! Please try again later.", chat_history


if __name__ == "__main__":
    # Quick smoke-test — does not require a real calendar connection
    msg = "I want to spend 9 hours on Audio Medusa today."
    reply, history = process_whatsapp_message(msg)
    print(f"Agent Reply: {reply}")
