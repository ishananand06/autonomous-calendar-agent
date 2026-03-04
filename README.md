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
1. Clone the repository: `git clone https://github.com/ishananand06/autonomous-calendar-agent.git`
2. Navigate into the directory: `cd autonomous-calendar-agent`
3. Create a virtual environment: `python -m venv .venv`
4. Activate the virtual environment:
   - Mac/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and add your API credentials.
7. Run the local server: `uvicorn main:app --reload`

## Setting up Google Calendar API Credentials
To allow the AI to read and modify your schedule, you must connect it to your own Google Account. Google requires you to generate a secure `credentials.json` file.

**Step 1: Create a Google Cloud Project**
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown (top left) and select **New Project**.
3. Name it `Calendar-Agent` (or similar) and click **Create**.

**Step 2: Enable the Calendar API**
1. In your new project, navigate to **APIs & Services > Library** using the left sidebar.
2. Search for **Google Calendar API**.
3. Click on it and hit **Enable**.

**Step 3: Configure the OAuth Consent Screen**
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** and click **Create**.
3. Fill in the required fields (App name, User support email, and Developer contact information).
4. Click **Save and Continue** through the "Scopes" screen.
5. On the **Test users** screen, click **Add Users** and enter the exact Gmail address you use for your calendar. *(Crucial: If you skip this, Google will block your login attempts).*
6. Click **Save and Continue**.

**Step 4: Download Your Credentials**
1. Go to **APIs & Services > Credentials**.
2. Click **+ CREATE CREDENTIALS** at the top and select **OAuth client ID**.
3. Set the **Application type** to **Desktop app**.
4. Name it `Python Calendar Script` and click **Create**.
5. Click **Download JSON** on the popup that appears.
6. Move the downloaded file into the root folder of this repository and rename it exactly to `credentials.json`.

**SECURITY WARNING**
Never share your `credentials.json` or `token.json` files, and **never commit them to version control**. Ensure your `.gitignore` file includes these filenames before running `git push`.