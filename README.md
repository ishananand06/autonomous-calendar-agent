# Autonomous LLM Scheduling Agent

An opinionated, serverless scheduling assistant accessed via WhatsApp. Unlike standard calendar tools that blindly schedule tasks, this agent acts as a constraint satisfaction engine. It evaluates your current Google Calendar state against predefined cognitive load limits and actively pushes back if a requested task exceeds your daily bandwidth.

## Core Features
* **WhatsApp Interface:** Natural language input via Meta's WhatsApp Cloud API webhook.
* **State Management:** Real-time bi-directional sync with Google Calendar API.
* **Cognitive Load Protection:** Enforces a maximum daily limit of deep-work hours.
* **Habit Anchoring:** Automatically protects time for non-negotiable daily routines.
* **Dynamic Preferences:** Habits and cognitive limits are not hardcoded. Users can update their daily "budget" or habit durations in real-time via natural language or by modifying `user_config.json`.

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
6. Initialize your profile: `python configure.py`
7. Copy `.env.example` to `.env` and add your API credentials.
8. Run the local server: `uvicorn main:app --reload`

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

## Setting up WhatsApp & Webhooks (Meta Cloud API)
To interact with the agent via WhatsApp, you need to connect your local server to Meta's API using a secure public tunnel.

**Step 1: Create a Public Tunnel with ngrok**
1. Download and install [ngrok](https://ngrok.com/download).
2. Authenticate your ngrok account in your terminal: `ngrok config add-authtoken YOUR_TOKEN`
3. Open a separate terminal and start the tunnel on port 8000: `ngrok http 8000`
4. Copy the `Forwarding` URL (e.g., `https://1a2b-34.ngrok-free.app`). *(Keep this terminal running).*

**Step 2: Create a Meta Developer App**
1. Go to the [Meta Developer Portal](https://developers.facebook.com/) and click **Create App**.
2. Select **Other**, then **Business**. Name your app and create it.
3. On the product setup page, scroll down to **WhatsApp** and click **Set Up**.
4. If prompted, follow the instructions to create a free Meta Business Portfolio.

**Step 3: Configure the Webhook**
1. In the left menu under **WhatsApp**, click **Configuration**.
2. Click **Edit** under the Webhook section.
3. **Callback URL:** Paste your ngrok URL and append `/webhook` (e.g., `https://1a2b-34.ngrok-free.app/webhook`).
4. **Verify Token:** Enter a custom password (e.g., `my_custom_secret_token_123`).
5. Click **Verify and Save**. *(Note: Your local FastAPI server must be running for this to succeed).*
6. Click **Manage** under Webhook fields, find the **messages** row, and click **Subscribe**.

**Step 4: Update Environment Variables**
1. Go to **WhatsApp > API Setup** to find your **Temporary access token** and **Phone number ID**.
2. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
3. Open your `.env` file and update the values.
4. Restart your `uvicorn` server to load the new environment variables.

**Step 5: Talk to Your Agent**
1. On the Meta **API Setup** page, add and verify your personal phone number in the **To** section.
2. Add the provided **Test phone number** to your mobile device's contacts.
3. Send a WhatsApp message to the test number to wake up the agent!
