"""Environment configuration. Loaded once at import."""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}. See .env.example")
    return value


TWILIO_ACCOUNT_SID = _require("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _require("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = _require("TWILIO_FROM_NUMBER")

# Hard-coded default so a stray edit can never dial anything but the assessment line.
TARGET_NUMBER = os.getenv("TARGET_NUMBER", "+18054398008")

OPENAI_API_KEY = _require("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-realtime-2")
REALTIME_AUDIO_FORMAT_TYPE = os.getenv("REALTIME_AUDIO_FORMAT_TYPE", "audio/pcmu")

LOCAL_PORT = int(os.getenv("LOCAL_PORT", "8000"))

# Safety rails: every call is capped so a runaway session cannot drain the budget.
MAX_CALL_SECONDS = int(os.getenv("MAX_CALL_SECONDS", "210"))
