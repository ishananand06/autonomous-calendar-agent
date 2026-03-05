import json
import os
import datetime
from tzlocal import get_localzone

def run_setup():
    print("--- 🚀 Autonomous Calendar Agent Setup ---")
    
    if os.path.exists("user_config.json"):
        confirm = input("user_config.json already exists. Overwrite? (y/n): ")
        if confirm.lower() != 'y': return

    # Core Questions
    limit = input("What is your daily cognitive limit in hours? (Default 8): ") or "8"

    # Auto-detect system timezone — tzlocal returns a proper IANA name (e.g. Asia/Kolkata)
    detected_tz = str(get_localzone())
    print(f"\nDetected system timezone: {detected_tz}")
    timezone_input = input("Press Enter to use it, or type a different IANA timezone (e.g. America/New_York): ").strip()
    timezone = timezone_input if timezone_input else detected_tz
    
    print("\nEnter your 5 main projects (comma separated):")
    projects_input = input("> ")
    projects = [p.strip() for p in projects_input.split(",")]

    # Default Habits (Can be expanded)
    config = {
        "daily_cognitive_limit_hours": int(limit),
        "timezone": timezone,
        "habits": [
            {"name": "LeetCode", "duration_minutes": 45, "frequency": "daily"},
            {"name": "Movie/Rest", "duration_minutes": 120, "frequency": "bi-weekly"}
        ],
        "projects": projects
    }

    with open("user_config.json", "w") as f:
        json.dump(config, f, indent=4)
    
    print("\n✅ user_config.json created successfully!")

if __name__ == "__main__":
    run_setup()