import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
# We are using the highest level scope so the AI can read and write events.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    """
    Handles Google Calendar OAuth2 authentication.
    Expects a 'credentials.json' file downloaded from Google Cloud Console.
    Saves the session in 'token.json' to avoid re-logging in on every run.
    """
    creds = None
    
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, prompt the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This triggers the browser popup for Google Login
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Build and return the Calendar API service
        service = build('calendar', 'v3', credentials=creds)
        print("Calendar authentication successful.")
        return service
    except Exception as error:
        print(f"An error occurred during Calendar authentication: {error}")
        return None

def get_upcoming_events(service, time_min=None, time_max=None):
    """
    Retrieves events from ALL of the user's calendars within a specific timeframe.
    """
    if time_min is None:
        time_min = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if time_max is None:
        time_max = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).isoformat()

    all_events = []

    try:
        # 1. Get the list of all calendars the user has access to
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])

        # 2. Loop through every single calendar
        for calendar in calendars:
            calendar_id = calendar['id']
            try:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                all_events.extend(events)
            except Exception as e:
                # Some shared/holiday calendars might block API reads, so we safely skip them
                print(f"Skipping calendar {calendar.get('summary')} due to error: {e}")

        # 3. Deduplicate (a shared-calendar event can appear in multiple calendar lists)
        seen_ids: set = set()
        unique_events = []
        for ev in all_events:
            eid = ev.get('id')
            if eid and eid in seen_ids:
                continue
            seen_ids.add(eid)
            unique_events.append(ev)
        all_events = unique_events

        # 4. Sort all combined events chronologically
        def get_start_time(event):
            # All-day events use 'date', timed events use 'dateTime'
            return event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))

        all_events.sort(key=get_start_time)
        print(f"Retrieved {len(all_events)} total events across {len(calendars)} calendars.")
        return all_events

    except Exception as error:
        print(f"An error occurred fetching calendars: {error}")
        return []

def get_calendar_id_by_name(service, calendar_name):
    """Searches the user's account and returns the true ID of a specific calendar."""
    try:
        calendar_list = service.calendarList().list().execute()
        for calendar in calendar_list.get('items', []):
            if calendar.get('summary', '').lower() == calendar_name.lower():
                return calendar['id']
        return None
    except Exception as e:
        print(f"Error fetching calendar list for ID lookup: {e}")
        return None

def add_calendar_event(service, summary, start_time, end_time, timezone='UTC'):
    """
    Adds a new event to the specific 'AI calendar'.
    If 'AI calendar' is not found, it falls back to 'primary' as a safety net.
    This is the 'Execution Tool' the LLM agent will use after approving a task.

    Args:
        service: Authenticated Google Calendar service object.
        summary: Title of the event.
        start_time: ISO 8601 start datetime string (e.g. '2026-03-05T09:00:00').
        end_time: ISO 8601 end datetime string.
        timezone: IANA timezone name (default 'UTC').
    """
    target_calendar_name = "AI Calendar" # The exact name of your new calendar
    
    # 1. Look up the specific ID for the AI Calendar
    target_id = get_calendar_id_by_name(service, target_calendar_name)
    
    if not target_id:
        print(f"⚠️ Calendar '{target_calendar_name}' not found! Falling back to 'primary'.")
        target_id = 'primary'

    # 2. Build the event payload
    event_body = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': timezone},
        'end':   {'dateTime': end_time,   'timeZone': timezone},
    }
    
    # 3. Insert the event into the targeted calendar
    created_event = service.events().insert(
        calendarId=target_id, 
        body=event_body
    ).execute()
    
    print(f"Event successfully created in {target_calendar_name}: {created_event.get('htmlLink')}")
    return created_event

def add_calendar_event(service, summary, start_time, end_time, timezone='UTC'):
    """
    Adds a new event to the calendar.
    This is the 'Execution Tool' the LLM agent will use after approving a task.

    Args:
        service: Authenticated Google Calendar service object.
        summary: Title of the event.
        start_time: ISO 8601 start datetime string (e.g. '2026-03-05T09:00:00').
        end_time: ISO 8601 end datetime string.
        timezone: IANA timezone name (default 'UTC').
    """
    event_body = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': timezone},
        'end':   {'dateTime': end_time,   'timeZone': timezone},
    }
    created_event = service.events().insert(
        calendarId='primary',
        body=event_body
    ).execute()
    print(f"Event created: {created_event.get('htmlLink')}")
    return created_event

if __name__ == "__main__":
    # A quick test to ensure authentication works when you run this file directly
    authenticate_google_calendar()