"""Resolve which mu-law format value this Realtime API build actually accepts.

The GA API replaced the flat input_audio_format key with a nested
session.audio.input.format, and the published reference does not enumerate the
valid values. Rather than guess, connect once and try each candidate: the API's
own error message is the authoritative answer.

    python tools/probe_realtime.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets
from src import config

CANDIDATES = [
    "g711_ulaw",
    "audio/pcmu",
    {"type": "audio/pcmu"},
    {"type": "g711_ulaw"},
]


async def try_format(candidate) -> tuple[bool, str]:
    url = f"wss://api.openai.com/v1/realtime?model={config.REALTIME_MODEL}"
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    async with websockets.connect(url, additional_headers=headers) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": config.REALTIME_MODEL,
                "audio": {
                    "input": {"format": candidate},
                    "output": {"format": candidate},
                },
            },
        }))
        for _ in range(6):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if msg.get("type") == "session.updated":
                return True, "accepted"
            if msg.get("type") == "error":
                return False, msg.get("error", {}).get("message", json.dumps(msg))
    return False, "no decisive response"


async def main() -> None:
    print(f"model: {config.REALTIME_MODEL}\n")
    for candidate in CANDIDATES:
        label = json.dumps(candidate)
        try:
            ok, detail = await try_format(candidate)
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        print(f"{'PASS' if ok else 'FAIL'}  {label}\n      {detail}\n")
        if ok:
            print(f"Set REALTIME_AUDIO_FORMAT to {label} in your .env")
            return
    print("None accepted. Read the error text above - it usually lists valid values.")


if __name__ == "__main__":
    asyncio.run(main())
