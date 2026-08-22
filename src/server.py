"""FastAPI app Twilio talks to: one TwiML endpoint and one media WebSocket."""
import threading

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import PlainTextResponse

from . import bridge
from .persona import Scenario

app = FastAPI()

# Set by run.py before the call is placed. Single-call-per-process by design:
# concurrency here would buy nothing and cost readability.
ACTIVE: dict = {"scenario": None, "log": None, "public_url": None}
CALL_FINISHED = threading.Event()


@app.post("/twiml")
async def twiml(request: Request) -> PlainTextResponse:
    """Tell Twilio to open a bidirectional media stream back to us."""
    ws_url = ACTIVE["public_url"].replace("https://", "wss://") + "/media"
    return PlainTextResponse(
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Connect><Stream url=\"{ws_url}\" /></Connect></Response>",
        media_type="application/xml",
    )


@app.websocket("/media")
async def media(ws: WebSocket) -> None:
    await ws.accept()
    scenario: Scenario = ACTIVE["scenario"]
    log: bridge.CallLog = ACTIVE["log"]
    try:
        await bridge.run(ws, scenario, log)
    finally:
        CALL_FINISHED.set()
