import os
import json
import datetime
import zoneinfo
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
    4. User Timezone: {prefs.get('timezone', 'UTC')} — all scheduled event times are in this timezone.

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

    Args:
        key: The preference to update. Supported values:
             'daily_cognitive_limit_hours'     — set the daily hour cap (value: int)
             'timezone'                         — update the IANA timezone (value: str)
             'habit_add'                        — add a new habit (value: dict with
                                                  name, duration_minutes, frequency)
             'habit_remove:<name>'              — remove a habit by name
             'habit_duration:<name>'            — update a habit's duration in minutes
             'habit_frequency:<name>'           — update a habit's frequency string
        value: The new value corresponding to the key.
    """
    prefs = load_user_preferences()

    if key == "daily_cognitive_limit_hours":
        prefs["daily_cognitive_limit_hours"] = int(value)

    elif key == "timezone":
        prefs["timezone"] = str(value)

    elif key == "habit_add":
        prefs.setdefault("habits", []).append({
            "name":             value["name"],
            "duration_minutes": int(value["duration_minutes"]),
            "frequency":        value.get("frequency", "daily"),
        })

    elif key.startswith("habit_remove:"):
        habit_name = key.split(":", 1)[1]
        prefs["habits"] = [
            h for h in prefs.get("habits", [])
            if h["name"].lower() != habit_name.lower()
        ]

    elif key.startswith("habit_duration:"):
        habit_name = key.split(":", 1)[1]
        for habit in prefs.get("habits", []):
            if habit["name"].lower() == habit_name.lower():
                habit["duration_minutes"] = int(value)
                break

    elif key.startswith("habit_frequency:"):
        habit_name = key.split(":", 1)[1]
        for habit in prefs.get("habits", []):
            if habit["name"].lower() == habit_name.lower():
                habit["frequency"] = str(value)
                break

    else:
        return {"error": f"Unknown preference key: '{key}'"}

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
        model_name='gemini-3-flash-preview',
        system_instruction=get_system_prompt(prefs),
        tools=[check_calendar, create_event, update_preferences],
    )

    # Cap history to avoid hitting Gemini's context window limit
    MAX_HISTORY = 20
    trimmed_history = (chat_history or [])[-MAX_HISTORY:]

    chat = model.start_chat(
        history=trimmed_history,
        enable_automatic_function_calling=True,
    )
    response = chat.send_message(user_message)
    return response.text, chat.history


if __name__ == "__main__":
    # Quick smoke-test — does not require a real calendar connection
    msg = "I want to spend 9 hours on Audio Medusa today."
    reply, history = process_whatsapp_message(msg)
    print(f"Agent Reply: {reply}")
