import json
import os

def run_setup():
    print("--- 🚀 Autonomous Calendar Agent Setup ---")
    
    if os.path.exists("user_config.json"):
        confirm = input("user_config.json already exists. Overwrite? (y/n): ")
        if confirm.lower() != 'y': return

    # Core Questions
    limit = input("What is your daily cognitive limit in hours? (Default 8): ") or "8"
    
    print("\nEnter your 5 main projects (comma separated):")
    projects_input = input("> ")
    projects = [p.strip() for p in projects_input.split(",")]

    # Default Habits (Can be expanded)
    config = {
        "daily_cognitive_limit_hours": int(limit),
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