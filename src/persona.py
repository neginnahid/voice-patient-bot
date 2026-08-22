"""Turns a scenario YAML file into a Realtime system prompt.

The prompt is deliberately opinionated about *conversational behaviour*, not just
content. Two voice models talking to each other will trample each other unless the
caller is explicitly told to yield, so the turn-taking rules live here rather than
being left to the model's defaults.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

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


def load(path: str | Path) -> Scenario:
    data = yaml.safe_load(Path(path).read_text())

    identity_lines = "\n".join(f"- {k}: {v}" for k, v in (data.get("identity") or {}).items())
    notes = "\n".join(f"- {n}" for n in (data.get("notes") or []))

    instructions = f"""{BEHAVIOUR_RULES}

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
