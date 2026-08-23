# Architecture

## How it works

`src/run.py` is the whole control flow: it opens an ngrok tunnel, starts a local FastAPI
server, and asks Twilio to place a call from our number to the assessment line. Twilio
fetches TwiML from the tunnel, which answers with `<Connect><Stream>` — instructing
Twilio to open a bidirectional WebSocket back to us and stream the live call audio
through it. `src/bridge.py` connects that socket to an OpenAI Realtime session
configured with a patient persona, then pumps audio frames in both directions until
either side hangs up. The persona comes from a scenario YAML via `src/persona.py`, which
supplies the identity and goal and wraps them in fixed conversational rules. Because
Twilio media streams and the Realtime session are both configured for G.711 μ-law at
8 kHz, audio passes through as opaque base64 with no transcoding — which is the main
reason the relay is about 150 lines rather than a DSP project. Meanwhile Twilio records
the call in dual-channel mode, and the Realtime session transcribes both what it hears
and what it says, so `src/transcribe.py` can write a timestamped, speaker-labelled
transcript and pull the MP3 the moment the call ends.

## Why it is built this way

**Speech-to-speech rather than a cascade.** The obvious alternative is
STT → LLM → TTS (Deepgram, a chat model, ElevenLabs). We rejected it on latency: each
hop adds delay and they compound to 1.5–3 seconds per turn, which on a phone call reads
as a stilted, obviously-synthetic caller. Since voice-interaction quality is evaluated
before any code is read, and the brief asks for a caller that behaves like a real user
rather than a benchmark runner, per-turn latency was the constraint we could least
afford to lose. A single speech-to-speech session keeps turn latency in the hundreds of
milliseconds and handles voice-activity detection and barge-in natively. The tradeoff we
accepted is weaker control over exact wording — a cascade would let us script utterances
verbatim, which matters for deterministic regression tests but not for exploratory
testing, where we *want* the caller to improvise around a goal.

**Raw Twilio instead of a managed voice platform.** Vapi, Retell or Bland would have
produced a working call faster, but the engineering then lives in a vendor config screen,
and we would not control the recording format or the transcript pipeline — both of which
are graded deliverables here. Pipecat and LiveKit Agents were the middle option; we
skipped them because a direct WebSocket relay is short enough to read in one sitting,
and a framework would have added an abstraction to explain and debug on a one-day clock.

**Dual-channel recording as the source of truth.** Asking Twilio for
`recording_channels="dual"` puts our caller on one channel and the agent under test on
the other. Speaker attribution therefore becomes a property of the audio file rather than
an inference from a diarisation model, so every quote in the bug report can be checked
against the audio it came from. It also satisfies the MP3 deliverable with no
post-processing.

**Turn-taking was tuned, not defaulted.** Two voice models talking to each other is
unstable out of the box. Three changes did most of the work: we never send
`response.create` on connect, because the agent under test greets first and a caller that
speaks on answer talks straight over it; server VAD `silence_duration_ms` was raised from
500 ms to 800 ms, since the default is tuned for a human who pauses more than a model
does; and on barge-in we clear Twilio's playback buffer so a queued sentence stops
immediately instead of continuing over the other party.

**One process, one call.** No concurrency, no queue, no database. Calls run serially via
`tools/run_batch.py`. The free ngrok tier permits one tunnel anyway, and serialising also
avoids hammering the system under test. Transcripts and recordings are files on disk
because 13 calls do not need anything more.

## Notes on the Realtime API

The audio format was resolved empirically rather than from documentation, using
`tools/probe_realtime.py`. The GA API rejects the beta's flat `input_audio_format` /
`output_audio_format` keys in favour of a nested `session.audio.{input,output}`, and
`format` must be an **object** — but the published reference does not enumerate valid
values for it, and the μ-law type string turned out to be `audio/pcmu`, not the
`g711_ulaw` used by the beta API and by every integration guide we found. The probe tries
each candidate and lets the API's own error response decide, which took about a minute
and removed the guesswork. `tools/probe_session.py` then validates the complete session
config — voice, VAD thresholds, transcription — before any call is placed, so a malformed
session fails for free instead of on a live call.
