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
    Retrieves events from the user's primary calendar within a specific timeframe.
    This is the 'Context Tool' the LLM agent will use to check cognitive load.
    Defaults to the next 7 days if no range is provided.
    """
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if time_min is None:
        time_min = now.isoformat() + 'Z'
    if time_max is None:
        time_max = (now + datetime.timedelta(days=7)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    print(f"Retrieved {len(events)} events.")
    return events

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