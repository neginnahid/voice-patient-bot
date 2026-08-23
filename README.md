# Voice patient bot

An automated caller that phones a healthcare voice agent, behaves like a real patient,
and captures both sides of every call so failures can be found and cited.

It places a call over Twilio, plays a patient persona driven by OpenAI's Realtime API,
captures both sides of the conversation as audio and text, and leaves you with a
transcript and an MP3 per call to analyse.

Built for the Pretty Good AI engineering challenge. All calls target the assessment
line, **+1-805-439-8008**, which is hardcoded as the default in `src/config.py`.

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how it works and why it is built this way
- **[BUG_REPORT.md](BUG_REPORT.md)** — 9 verified issues across 13 calls
- **[ANALYSIS.md](ANALYSIS.md)** — automated triage pass, unverified candidates
- **[transcripts/](transcripts/)** — timestamped, speaker-labelled, one file per call
  (13 scenarios, plus one rerun after a fix to the caller persona)
- **[recordings/](recordings/)** — dual-channel MP3, one file per call

## Setup

Requires Python 3.12+, an [ngrok](https://ngrok.com) account, a Twilio account with a
voice-capable number, and an OpenAI API key with credit.

```bash
git clone https://github.com/neginnahid/voice-patient-bot
cd voice-patient-bot

python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Prompts for each credential; secrets are typed hidden and never echoed.
.venv/bin/python tools/setup_env.py

# One-time ngrok registration, reading the token straight out of .env
ngrok config add-authtoken "$(grep NGROK_AUTHTOKEN .env | cut -d= -f2)"
```

See [.env.example](.env.example) for the variables involved. `.env` is gitignored.

## Run

One scenario, end to end — dials out, holds the conversation, saves the transcript and
downloads the recording:

```bash
.venv/bin/python -m src.run --scenario scenarios/01_simple_schedule.yaml
```

Every scenario, unattended (~45 minutes for all 13):

```bash
.venv/bin/python tools/run_batch.py
```

Or a subset: `.venv/bin/python tools/run_batch.py 05 06 12`

The live conversation prints to your terminal as it happens:

```
[00:20] AGENT: Thanks for calling Pivot Point Orthopedics. How may I help you today?
[00:21] PATIENT: Hi, this is Dana Whitfield. I'm calling to set up a follow-up for my knee.
```

## Writing a scenario

Scenarios are YAML. `persona.py` wraps them in a fixed set of conversational rules —
short turns, never interrupt, steer toward the goal, hang up when done — so each file
only describes *who is calling and why*.

```yaml
id: "14"
title: "Late cancellation"
voice: marin
goal: >
  Cancel an appointment that is two hours away and find out whether
  there is a late-cancellation fee.
identity:
  Name: Dana Whitfield
  Date of birth: March 4th, 1991
notes:
  - You are already running late and slightly flustered.
  - Ask twice about the fee if the first answer is vague.
```

## Tools

| Command | Purpose |
|---|---|
| `tools/setup_env.py` | Interactive credential setup, hidden input |
| `tools/check_env.py` | Validates `.env`, prints masked values only |
| `tools/probe_realtime.py` | Resolves the accepted Realtime audio-format value |
| `tools/probe_session.py` | Validates the full session config before spending a call |
| `tools/run_batch.py` | Runs scenarios back to back |
| `tools/show_persona.py` | Prints the prompt a scenario generates, without calling |
| `python -m src.analyze` | Scores every transcript against a rubric into `ANALYSIS.md` |

## Cost

About $0.45 per three-minute call — Realtime API audio dominates, Twilio voice and
recording are roughly $0.04. The full 13-call run came to well under $10.
