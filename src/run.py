"""One command: tunnel up, server up, place the call, save the artefacts.

    python -m src.run --scenario scenarios/01_simple_schedule.yaml
"""
import argparse
import threading
import time

import uvicorn
from pyngrok import ngrok
from twilio.rest import Client

from . import config, persona, server, transcribe
from .bridge import CallLog


def _serve() -> None:
    uvicorn.run(server.app, host="0.0.0.0", port=config.LOCAL_PORT, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()

    scenario = persona.load(args.scenario)
    log = CallLog()

    threading.Thread(target=_serve, daemon=True).start()
    time.sleep(2)

    public_url = ngrok.connect(config.LOCAL_PORT, "http").public_url
    server.ACTIVE.update({"scenario": scenario, "log": log, "public_url": public_url})
    print(f"tunnel: {public_url}")

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        to=config.TARGET_NUMBER,
        from_=config.TWILIO_FROM_NUMBER,
        url=f"{public_url}/twiml",
        method="POST",
        record=True,
        recording_channels="dual",   # our caller and their agent on separate channels
        time_limit=config.MAX_CALL_SECONDS,
    )
    print(f"calling {config.TARGET_NUMBER} as '{scenario.title}' (sid {call.sid})\n")

    server.CALL_FINISHED.wait(timeout=config.MAX_CALL_SECONDS + 30)
    time.sleep(3)

    path = transcribe.write_transcript(log, scenario.slug)
    print(f"\ntranscript -> {path}")

    recording = transcribe.fetch_recording(call.sid, scenario.slug)
    if recording:
        print(f"recording  -> {recording}")

    ngrok.kill()


if __name__ == "__main__":
    main()
