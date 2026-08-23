"""Post-call artefacts: pull the dual-channel recording, write the transcript.

Twilio records the call with our caller on one channel and the agent under test on
the other. That means speaker attribution is a property of the audio file, not a
guess made by a diarisation model — which is why the transcripts are trustworthy.
"""
import time
from pathlib import Path

import httpx

from . import config
from .bridge import CallLog

RECORDINGS = Path("recordings")
TRANSCRIPTS = Path("transcripts")


def _free_path(directory: Path, slug: str, suffix: str) -> Path:
    """Never overwrite an existing call.

    Rerunning a scenario used to clobber the original transcript and recording,
    which quietly destroys the evidence a bug report cites. Reruns now land
    alongside as _rerun1, _rerun2, and so on.
    """
    path = directory / f"{slug}{suffix}"
    n = 0
    while path.exists():
        n += 1
        path = directory / f"{slug}_rerun{n}{suffix}"
    return path


def write_transcript(log: CallLog, slug: str) -> Path:
    TRANSCRIPTS.mkdir(exist_ok=True)
    path = _free_path(TRANSCRIPTS, slug, ".txt")
    lines = [f"Call: {slug}", f"CallSid: {log.call_sid}", "-" * 60]
    for turn in log.turns:
        stamp = time.strftime("%M:%S", time.gmtime(turn.at))
        lines.append(f"[{stamp}] {turn.speaker}: {turn.text}")
    path.write_text("\n".join(lines) + "\n")
    return path


def fetch_recording(call_sid: str, slug: str, attempts: int = 12) -> Path | None:
    """Twilio finalises recordings a few seconds after hangup, so poll briefly."""
    RECORDINGS.mkdir(exist_ok=True)
    auth = (config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    list_url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}"
        f"/Calls/{call_sid}/Recordings.json"
    )

    for _ in range(attempts):
        resp = httpx.get(list_url, auth=auth, timeout=30)
        resp.raise_for_status()
        recordings = resp.json().get("recordings", [])
        if recordings:
            sid = recordings[0]["sid"]
            mp3 = httpx.get(
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{config.TWILIO_ACCOUNT_SID}/Recordings/{sid}.mp3",
                auth=auth, timeout=120, follow_redirects=True,
            )
            mp3.raise_for_status()
            path = _free_path(RECORDINGS, slug, ".mp3")
            path.write_bytes(mp3.content)
            return path
        time.sleep(5)

    print("!! recording not available yet; fetch it later with tools/fetch_recording.py")
    return None
