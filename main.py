import os
import asyncio
import httpx
from collections import deque
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from agent import process_whatsapp_message

# Load environment variables from the .env file
load_dotenv()

app = FastAPI()

WHATSAPP_VERIFY_TOKEN   = os.getenv("WEBHOOK_VERIFY_TOKEN")
WHATSAPP_TOKEN          = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_URL        = (
    f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
)

# Per-user conversation history keyed by the sender's phone number.
# In production this should be a persistent store (Redis, DB, etc.).
chat_sessions: dict[str, list] = {}

# Deduplication guard — WhatsApp retries webhooks if it doesn't get a fast 200.
# We track the last 500 message IDs (set for O(1) lookup, deque for eviction).
_seen_ids: set[str] = set()
_seen_ids_queue: deque[str] = deque(maxlen=500)

def _is_duplicate(msg_id: str) -> bool:
    if msg_id in _seen_ids:
        return True
    if len(_seen_ids_queue) == _seen_ids_queue.maxlen:
        _seen_ids.discard(_seen_ids_queue[0])
    _seen_ids.add(msg_id)
    _seen_ids_queue.append(msg_id)
    return False


@app.get("/")
async def root():
    return {"message": "Autonomous Calendar Agent is running."}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Required by Meta to verify your webhook URL.
    When you register the URL in the WhatsApp Cloud API dashboard, Meta sends a
    GET request here with hub.mode, hub.verify_token, and hub.challenge.
    """
    mode      = request.query_params.get("hub.mode")
    token     = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            print("Webhook verified successfully!")
            return PlainTextResponse(content=challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification token mismatch")

    raise HTTPException(status_code=400, detail="Missing parameters")

async def handle_message_background(sender: str, user_text: str, history: list):
    try:
        # 1. Get the AI's reply (this takes a few seconds)
        # We run the synchronous Gemini code in a thread so it doesn't block FastAPI
        reply_text, updated_history = await asyncio.to_thread(process_whatsapp_message, user_text, history)
        
        # 2. Save history
        chat_sessions[sender] = updated_history
        
        # 3. Send the WhatsApp reply
        await _send_whatsapp_message(sender, reply_text)
    except Exception as e:
        print(f"Error in background task: {e}")


@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks): # Add it here
    body = await request.json()
    print(f"Incoming Webhook Payload: {body}")

    try:
        entry   = body.get("entry",   [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_message"}

        message = messages[0]
        if message.get("type") != "text":
            return {"status": "non_text_ignored"}

        # Drop retried/duplicate deliveries
        if _is_duplicate(message.get("id", "")):
            return {"status": "duplicate_ignored"}

        sender    = message["from"]
        user_text = message["text"]["body"]
        history = chat_sessions.get(sender, [])

        # Add the heavy lifting to the background task queue
        background_tasks.add_task(handle_message_background, sender, user_text, history)

    except Exception as e:
        print(f"Error parsing webhook: {e}")

    # Return 200 OK instantly to keep WhatsApp happy!
    return {"status": "success"}


async def _send_whatsapp_message(to: str, text: str) -> dict:
    """Sends a text reply to the given WhatsApp number via the Cloud API."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"WhatsApp API error {response.status_code}: {response.text}")
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)