"""Turns a scenario YAML file into a Realtime system prompt.

The prompt is deliberately opinionated about *conversational behaviour*, not just
content. Two voice models talking to each other will trample each other unless the
caller is explicitly told to yield, so the turn-taking rules live here rather than
being left to the model's defaults.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config

BEHAVIOUR_RULES = """
You are a real person calling a medical clinic on the telephone. You are the PATIENT,
not an assistant. Never offer to help the other person and never break character.

How to speak:
- Wait until the other person has completely finished talking before you respond.
  Never talk over them. If you both start at once, stop and let them finish.
- Say one or two short sentences at a time, the way people actually talk on the phone.
  Never more than two sentences in a single turn. If you have several things to say,
  say one and wait. Do not restate information you have already given.
- Use natural filler occasionally: "um", "okay", "yeah, that works", "sorry, say again?"
- Do not read lists aloud or sound like you are reciting. You are speaking off the cuff.
- If you are asked for information you have, give it directly. If you are asked for
  something you do not have, say so plainly.

Your objective:
- Steer the conversation toward your goal. If the other person drifts, politely bring
  it back: "Sorry, before we move on, can we sort out the appointment?"
- Once your goal is resolved, or it becomes clear it cannot be, thank them and end the
  call naturally ("okay, great, thanks so much, bye"). Do not linger.
"""

# A real patient knows their own phone number; ours did not, and answered "I don't have
# that handy" whenever the agent asked for the number on file (calls 04, 05, 06, 10, 13)
# or read it back for confirmation (01, 06). That is unrealistic caller behaviour and it
# confounds the record-lookup failures - we cannot tell whether the agent could not find
# the record, or was never given a fair chance to. This removes that variable; it is a
# control, not a proven fix for those calls.
PHONE_RULE = """
Your phone number:
- You are calling from {phone}. It is your own number and it is the number the clinic
  has on file for you. You know it perfectly well.
- If you are asked for your phone number, just say it: "{phone}". Say the digits
  clearly. Never say you are unsure of it or that you do not have it handy.
- If they read a number back to you and it matches {phone}, confirm it plainly:
  "yep, that's it". Do not hedge and do not refuse to confirm digits.
"""

# For a scenario that deliberately tests the unknown-number path.
NO_PHONE_RULE = """
Your phone number:
- You genuinely do not know which number the clinic has on file, and you should say so
  if asked. Offer your name and date of birth instead.
"""


def spoken_number(e164: str) -> str:
    """+14706644675 -> '470-664-4675', the way a person says it on the phone."""
    digits = "".join(c for c in e164 if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return e164


@dataclass
class Scenario:
    id: str
    title: str
    goal: str
    instructions: str
    voice: str

    @property
    def slug(self) -> str:
        return f"{self.id}_{self.title.lower().replace(' ', '-')}"


def load(path: str | Path, caller_number: str | None = None) -> Scenario:
    data = yaml.safe_load(Path(path).read_text())

    identity = dict(data.get("identity") or {})

    # The caller ID Twilio presents is a fact about the call, not something a scenario
    # author should have to restate - so it is injected here rather than written into
    # each YAML, where it would drift the moment the from-number changes.
    if data.get("phone_known", True):
        phone = spoken_number(caller_number or config.TWILIO_FROM_NUMBER)
        identity["Phone"] = phone
        phone_rule = PHONE_RULE.format(phone=phone)
    else:
        identity.pop("Phone", None)
        phone_rule = NO_PHONE_RULE

    identity_lines = "\n".join(f"- {k}: {v}" for k, v in identity.items())
    notes = "\n".join(f"- {n}" for n in (data.get("notes") or []))

    instructions = f"""{BEHAVIOUR_RULES}
{phone_rule}
Who you are:
{identity_lines}

Why you are calling:
{data['goal']}

Details to use if asked:
{notes or "- (nothing beyond the above)"}
"""

    return Scenario(
        id=str(data["id"]),
        title=data["title"],
        goal=data["goal"],
        instructions=instructions,
        voice=data.get("voice", "marin"),
    )
