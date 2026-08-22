"""Interactive .env writer. Secrets are typed hidden and never echoed.

Run it in your own Terminal:  .venv/bin/python tools/setup_env.py
"""
import getpass
import re
from pathlib import Path

FIELDS = [
    ("TWILIO_ACCOUNT_SID", "Twilio Account SID (starts AC...)", False, r"^AC[0-9a-f]{32}$"),
    ("TWILIO_AUTH_TOKEN",  "Twilio Auth Token (32 chars, hidden)", True, r"^[0-9a-f]{32}$"),
    ("TWILIO_FROM_NUMBER", "Your Twilio number, E.164", False, r"^\+1\d{10}$"),
    ("OPENAI_API_KEY",     "OpenAI API key (sk-..., hidden)", True, r"^sk-[A-Za-z0-9_\-]{20,}$"),
    ("NGROK_AUTHTOKEN",    "ngrok authtoken (hidden)", True, r"^[A-Za-z0-9_]{30,}$"),
]

STATIC = {
    "TARGET_NUMBER": "+18054398008",
    "REALTIME_MODEL": "gpt-realtime-2",
    "REALTIME_AUDIO_FORMAT_TYPE": "audio/pcmu",
    "LOCAL_PORT": "8000",
}

print("\nFill in each value. Hidden fields will not show as you paste - that is normal.")
print("Press Ctrl+C any time to abort.\n")

values = {}
for name, prompt, hidden, pattern in FIELDS:
    while True:
        raw = (getpass.getpass(f"  {prompt}: ") if hidden else input(f"  {prompt}: ")).strip()
        raw = raw.strip('"').strip("'")
        if re.match(pattern, raw):
            values[name] = raw
            print(f"    ok ({len(raw)} chars)\n")
            break
        print(f"    that does not look right - expected pattern {pattern}. Try again.\n")

lines = [f"{k}={v}" for k, v in values.items()] + [f"{k}={v}" for k, v in STATIC.items()]
Path(".env").write_text("\n".join(lines) + "\n")
print("Wrote .env  (already gitignored - it will never be committed)")
print("\nNext:  ngrok config add-authtoken <same token you just pasted>")
