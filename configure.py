import json
import os
from tzlocal import get_localzone

def run_setup():
    print("--- 🚀 Autonomous Calendar Agent Setup ---")
    
    if os.path.exists("user_config.json"):
        confirm = input("user_config.json already exists. Overwrite? (y/n): ")
        if confirm.lower() != 'y': return

    # 1. Single Daily Limit
    print("\n--- Cognitive Limits ---")
    limit = input("What is your absolute daily cognitive limit in hours? (Classes + Deep Work) (Default 8): ") or "8"

    # Auto-detect system timezone
    detected_tz = str(get_localzone())
    print(f"\nDetected system timezone: {detected_tz}")
    timezone_input = input("Press Enter to use it, or type a different IANA timezone: ").strip()
    timezone = timezone_input if timezone_input else detected_tz
    
    # 2. Detailed Project Context Collection
    print("\nEnter your main projects (comma separated, e.g., Audio Medusa, Among Us Simulation):")
    projects_input = input("> ")
    project_names = [p.strip() for p in projects_input.split(",")] if projects_input else []
    
    projects_with_context = []
    if project_names:
        print("\n--- Project Context ---")
        for name in project_names:
            print(f"\nDescribe '{name}':")
            context = input("(Tip: Using words like 'high stakes', 'strict deadline', or 'flexible' helps the AI assign priority)\n> ")
            projects_with_context.append({
                "name": name,
                "context": context
            })

    # 3. Detailed Habit Collection
    print("\nEnter your daily/weekly habits (comma separated, e.g., LeetCode, Gym, Read):")
    habits_input = input("> ")
    habit_names = [h.strip() for h in habits_input.split(",")] if habits_input else []

    habits_with_context = []
    if habit_names:
        print("\n--- Habit Context ---")
        for name in habit_names:
            print(f"\nSettings for '{name}':")
            duration = input("Duration in minutes (Default 60): ") or "60"
            freq = input("Frequency (e.g., daily, weekends, bi-weekly) (Default daily): ") or "daily"
            context = input("(Tip: Using words like 'non-negotiable', 'strict', or 'can skip if busy' helps the AI decide what to drop)\n> ")
            
            habits_with_context.append({
                "name": name,
                "duration_minutes": int(duration),
                "frequency": freq,
                "context": context
            })

    # Compile the final configuration
    config = {
        "daily_cognitive_limit_hours": int(limit),
        "timezone": timezone,
        "habits": habits_with_context,
        "projects": projects_with_context,
        "active_deadlines": []
    }

    with open("user_config.json", "w") as f:
        json.dump(config, f, indent=4)
    
    print("\n✅ user_config.json created with semantic context and a unified daily limit!")

if __name__ == "__main__":
    run_setup()