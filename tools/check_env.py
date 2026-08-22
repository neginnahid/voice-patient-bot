"""Validate .env without printing secrets. Shows shape and length only."""
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

CHECKS = [
    ("TWILIO_ACCOUNT_SID", r"^AC[0-9a-f]{32}$", "starts with AC + 32 hex chars"),
    ("TWILIO_AUTH_TOKEN",  r"^[0-9a-f]{32}$",   "32 hex chars"),
    ("TWILIO_FROM_NUMBER", r"^\+1\d{10}$",      "E.164, e.g. +14706644675"),
    ("TARGET_NUMBER",      r"^\+18054398008$",  "must be the assessment line"),
    ("OPENAI_API_KEY",     r"^sk-[A-Za-z0-9_\-]{20,}$", "starts with sk-"),
    ("NGROK_AUTHTOKEN",    r"^[A-Za-z0-9_]{30,}$",      "long alphanumeric token"),
]

ok = True
for name, pattern, hint in CHECKS:
    value = os.getenv(name, "")
    if not value or "xxx" in value.lower() or value.startswith("your_"):
        print(f"  MISSING  {name:22} <- still a placeholder")
        ok = False
    elif not re.match(pattern, value):
        masked = value[:6] + "..." + value[-4:] if len(value) > 12 else "(short)"
        print(f"  BAD      {name:22} got {masked} ({len(value)} chars) - expected {hint}")
        ok = False
    else:
        masked = value[:6] + "..." + value[-4:] if len(value) > 12 else value
        print(f"  ok       {name:22} {masked}")

print()
print("All credentials look right." if ok else "Fix the entries above, then re-run.")
sys.exit(0 if ok else 1)
