"""Send the REAL session config from bridge.py and confirm the API accepts it.

Cheaper than discovering a malformed session on a live phone call.
    python tools/probe_session.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets
from src import config, persona
from src.bridge import session_config


async def main() -> None:
    scenario = persona.load("scenarios/01_simple_schedule.yaml")
    payload = session_config(scenario)
    print(json.dumps(payload["session"]["audio"], indent=2))
    print(f"voice: {scenario.voice}   model: {config.REALTIME_MODEL}\n")

    url = f"wss://api.openai.com/v1/realtime?model={config.REALTIME_MODEL}"
    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    ) as ws:
        await ws.send(json.dumps(payload))
        for _ in range(8):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if msg.get("type") == "session.updated":
                print("PASS - full session config accepted")
                return
            if msg.get("type") == "error":
                print("FAIL -", json.dumps(msg.get("error", msg), indent=2))
                return
    print("no decisive response")


if __name__ == "__main__":
    asyncio.run(main())
