"""Relays audio between a Twilio Media Stream and an OpenAI Realtime session.

Both sides speak G.711 mu-law at 8 kHz, so audio is passed through as opaque
base64 with no resampling. That is the single biggest reason this file is short.

Transcript capture is a side effect of the relay: the Realtime session already
transcribes both what it hears (their agent) and what it says (our patient), so
we log those events as they arrive rather than running a separate STT pass live.
"""
import asyncio
import base64
import json
import time
from dataclasses import dataclass, field

import websockets

from . import config
from .persona import Scenario

REALTIME_URL = "wss://api.openai.com/v1/realtime"

# Server-VAD tuning. The defaults are tuned for a human talking to a bot; here a bot
# talks to a bot, and the default 500ms silence window makes our caller cut in while
# their agent is still mid-sentence. Longer silence = politer caller.
TURN_DETECTION = {
    "type": "server_vad",
    "threshold": 0.6,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 800,
}


@dataclass
class Turn:
    at: float          # seconds since call start
    speaker: str       # "AGENT" (system under test) or "PATIENT" (our bot)
    text: str


@dataclass
class CallLog:
    started_at: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)
    call_sid: str | None = None

    def start_clock(self) -> None:
        """Reset t=0 to the moment the media stream opens.

        Twilio starts its recording when the call is answered, but this object is
        created when we place the call - so without this, transcript timestamps run
        20-25s ahead of the same moment in the MP3.
        """
        self.started_at = time.time()

    def add(self, speaker: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.turns.append(Turn(time.time() - self.started_at, speaker, text))
        stamp = time.strftime("%M:%S", time.gmtime(time.time() - self.started_at))
        print(f"[{stamp}] {speaker}: {text}", flush=True)


def session_config(scenario: Scenario) -> dict:
    """GA-shape session.update.

    Two non-obvious details, both established empirically via tools/probe_realtime.py
    because the published reference does not document them:
      - The GA API rejects the old flat input_audio_format/output_audio_format keys;
        audio config now lives under session.audio.{input,output}.
      - `format` must be an OBJECT, and the mu-law type string is "audio/pcmu",
        not the "g711_ulaw" used by the beta API and every tutorial online.
    """
    fmt = {"type": config.REALTIME_AUDIO_FORMAT_TYPE}
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": config.REALTIME_MODEL,
            "instructions": scenario.instructions,
            "audio": {
                "input": {
                    "format": fmt,
                    "turn_detection": TURN_DETECTION,
                    "transcription": {"model": "whisper-1", "language": "en"},
                },
                "output": {
                    "format": fmt,
                    "voice": scenario.voice,
                    "speed": 1.0,
                },
            },
        },
    }


async def run(twilio_ws, scenario: Scenario, log: CallLog) -> None:
    """Pump audio in both directions until either side hangs up."""
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    url = f"{REALTIME_URL}?model={config.REALTIME_MODEL}"

    async with websockets.connect(url, additional_headers=headers) as oai_ws:
        await oai_ws.send(json.dumps(session_config(scenario)))

        # response_active tracks whether the model is mid-response. Cancelling when
        # nothing is active is an API error, and their agent pauses often enough that
        # we would otherwise spam it on every silence.
        state = {"stream_sid": None, "response_active": False}

        # NOTE: we deliberately do NOT send response.create here. Their agent answers
        # the phone and greets first; a caller that starts talking on connect talks
        # straight over the greeting and the call never recovers.

        async def twilio_to_openai() -> None:
            async for raw in twilio_ws.iter_text():
                msg = json.loads(raw)
                event = msg.get("event")

                if event == "start":
                    log.start_clock()
                    state["stream_sid"] = msg["start"]["streamSid"]
                    log.call_sid = msg["start"].get("callSid")
                elif event == "media":
                    await oai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": msg["media"]["payload"],
                    }))
                elif event == "stop":
                    break

        async def openai_to_twilio() -> None:
            async for raw in oai_ws:
                msg = json.loads(raw)
                mtype = msg.get("type", "")

                # Streamed output audio. GA renamed this from response.audio.delta;
                # accept both so a version bump does not silently mute the caller.
                if mtype in ("response.output_audio.delta", "response.audio.delta"):
                    if state["stream_sid"]:
                        await twilio_ws.send_text(json.dumps({
                            "event": "media",
                            "streamSid": state["stream_sid"],
                            "media": {"payload": msg["delta"]},
                        }))

                # Their agent started talking while we were talking: stop our audio
                # immediately, otherwise Twilio keeps playing a buffered sentence over
                # the top of them and both sides sound broken.
                elif mtype == "response.created":
                    state["response_active"] = True

                elif mtype in ("response.done", "response.cancelled"):
                    state["response_active"] = False

                elif mtype == "input_audio_buffer.speech_started":
                    if state["stream_sid"]:
                        await twilio_ws.send_text(json.dumps({
                            "event": "clear",
                            "streamSid": state["stream_sid"],
                        }))
                    if state["response_active"]:
                        await oai_ws.send(json.dumps({"type": "response.cancel"}))
                        state["response_active"] = False

                elif mtype == "conversation.item.input_audio_transcription.completed":
                    log.add("AGENT", msg.get("transcript", ""))

                elif mtype in ("response.output_audio_transcript.done",
                               "response.audio_transcript.done"):
                    log.add("PATIENT", msg.get("transcript", ""))

                elif mtype == "error":
                    print(f"!! realtime error: {json.dumps(msg, indent=2)}", flush=True)

        await asyncio.wait(
            [asyncio.create_task(twilio_to_openai()),
             asyncio.create_task(openai_to_twilio())],
            return_when=asyncio.FIRST_COMPLETED,
        )
