import os
import httpx
from fastapi import FastAPI, Request, HTTPException
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
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification token mismatch")

    raise HTTPException(status_code=400, detail="Missing parameters")


@app.post("/webhook")
async def receive_message(request: Request):
    """
    Receives WhatsApp messages, routes them through the Gemini agent, and
    sends the reply back via the WhatsApp Cloud API.
    """
    body = await request.json()
    print(f"Incoming Webhook Payload: {body}")

    try:
        entry   = body.get("entry",   [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Could be a status update (delivered/read receipt) — safe to ignore
            return {"status": "no_message"}

        message = messages[0]
        if message.get("type") != "text":
            # Non-text messages (images, voice notes, etc.) are not yet supported
            return {"status": "non_text_ignored"}

        sender    = message["from"]
        user_text = message["text"]["body"]

        # Retrieve (or create) the conversation history for this user
        history = chat_sessions.get(sender, [])
        reply_text, updated_history = process_whatsapp_message(user_text, history)
        chat_sessions[sender] = updated_history

        await _send_whatsapp_message(sender, reply_text)

    except Exception as e:
        # Always return 200 so WhatsApp doesn't retry endlessly
        print(f"Error processing message: {e}")

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
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)