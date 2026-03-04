import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

app = FastAPI()

WHATSAPP_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")

@app.get("/")
async def root():
    return {"message": "Autonomous Calendar Agent is running."}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    This endpoint is required by Meta to verify your webhook URL.
    When you set up WhatsApp Cloud API, Meta will send a GET request here.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
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
    This endpoint receives the actual WhatsApp messages (POST request).
    """
    body = await request.json()
    
    # Print the incoming message to the terminal so we can see what Meta sends
    print(f"Incoming Webhook Payload: {body}")
    
    # TODO: Extract the user's text message from the JSON payload
    # TODO: Pass the text to agent.py (Gemini)
    # TODO: Send Gemini's response back to WhatsApp using httpx
    
    # We must return a 200 OK quickly so WhatsApp doesn't think the server is dead
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)