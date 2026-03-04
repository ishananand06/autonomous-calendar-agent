import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

CONFIG_FILE = "user_config.json"

def load_user_preferences():
    """Loads preferences from the JSON file."""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_user_preferences(prefs):
    """Saves updated preferences back to the JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(prefs, f, indent=4)

# Now, instead of a hardcoded dict, use:
user_preferences = load_user_preferences()

def get_system_prompt(prefs):
    """Generates a prompt based on the CURRENT state of preferences."""
    return f"""
    You are an autonomous scheduling assistant. 
    Current Rules:
    1. Max Cognitive Load: {prefs['daily_cognitive_limit_hours']} hours/day.
    2. Active Habits: {json.dumps(prefs['habits'])}
    3. Active Projects: {prefs['projects']}

    Logic:
    - Protect the cognitive load strictly UNLESS the user explicitly commands an override (e.g., 'Exceed the limit for today').
    - If the user asks to change a habit or a limit, use your reasoning to acknowledge the change and update your future scheduling behavior.
    - Always check the calendar before proposing a plan.
    """

# Initialize model without a fixed instruction (we pass it per chat session)
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=get_system_prompt(user_preferences),
    # Here you will eventually pass your tool functions from calendar_tools.py
    tools=[] 
)

def process_whatsapp_message(user_message, chat_history=None):
    # We pass the LATEST preferences into the system instruction for every message
    prompt = get_system_prompt(user_preferences)
    
    # In a real MLE setup, you'd load user_preferences from a database or JSON file here
    chat = model.start_chat(history=chat_history or [])
    
    # We send the system prompt as the first 'instruction' in the session
    response = chat.send_message(f"SYSTEM INSTRUCTION: {prompt}\n\nUSER MESSAGE: {user_message}")
    
    return response.text, chat.history

if __name__ == "__main__":
    # Test the agent with a "hard" request
    msg = "I need to read a 4-hour research paper tomorrow."
    reply, history = process_whatsapp_message(msg)
    print(f"Agent Reply: {reply}")