import os
import json
import datetime
import google.generativeai as genai
from dotenv import load_dotenv
from calendar_tools import authenticate_google_calendar, get_upcoming_events, add_calendar_event

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
    """Generates a prompt based on the CURRENT state of preferences."""
    today = datetime.date.today().isoformat()
    return f"""
    You are an autonomous scheduling assistant. Today's date is {today}.
    Current Rules:
    1. Max Cognitive Load: {prefs['daily_cognitive_limit_hours']} hours/day.
    2. Active Habits: {json.dumps(prefs['habits'])}
    3. Active Projects: {prefs['projects']}

    Logic:
    - ALWAYS call check_calendar for the relevant day before making any scheduling decision.
    - Sum up event durations for the target day. If adding the requested task exceeds the
      cognitive limit, refuse and explain clearly — unless the user explicitly overrides.
    - If the user asks to change a habit or the daily limit, call update_preferences.
    - If scheduling is approved, call create_event to actually add it to the calendar.
    """

# ── Tool functions exposed to Gemini ─────────────────────────────────────────

def check_calendar(date: str) -> dict:
    """
    Returns all Google Calendar events for a single day.

    Args:
        date: Target date in YYYY-MM-DD format.
    """
    service = _get_calendar_service()
    day_start = datetime.datetime.fromisoformat(date)
    day_end   = day_start + datetime.timedelta(days=1)
    events = get_upcoming_events(
        service,
        time_min=day_start.isoformat() + 'Z',
        time_max=day_end.isoformat() + 'Z',
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
    event = add_calendar_event(service, summary, start_datetime, end_datetime)
    return {"event_id": event.get("id"), "html_link": event.get("htmlLink")}

def update_preferences(key: str, value) -> dict:
    """
    Persists a change to the user's scheduling preferences.

    Args:
        key:   The preference to update ('daily_cognitive_limit_hours', or a habit name).
        value: The new value.
    """
    prefs = load_user_preferences()
    if key == "daily_cognitive_limit_hours":
        prefs["daily_cognitive_limit_hours"] = int(value)
    else:
        # Treat as a habit duration update by name
        for habit in prefs.get("habits", []):
            if habit["name"].lower() == key.lower():
                habit["duration_minutes"] = int(value)
                break
    save_user_preferences(prefs)
    return {"updated": key, "new_value": value}

# ─────────────────────────────────────────────────────────────────────────────

def process_whatsapp_message(user_message: str, chat_history=None):
    """
    Routes a WhatsApp message through Gemini with live tool calling.
    Preferences are reloaded on every call so in-session changes take effect immediately.
    """
    prefs = load_user_preferences()  # always fresh

    # Rebuild the model so the system instruction reflects the current preferences
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=get_system_prompt(prefs),
        tools=[check_calendar, create_event, update_preferences],
    )

    chat = model.start_chat(
        history=chat_history or [],
        enable_automatic_function_calling=True,
    )
    response = chat.send_message(user_message)
    return response.text, chat.history


if __name__ == "__main__":
    # Quick smoke-test — does not require a real calendar connection
    msg = "I need to read a 4-hour research paper tomorrow."
    reply, history = process_whatsapp_message(msg)
    print(f"Agent Reply: {reply}")
