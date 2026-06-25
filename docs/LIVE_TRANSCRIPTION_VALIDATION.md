# Gemini Live Input Transcription Validation

Version: 0.3.0
Recorded: 2026-06-25
Status: deterministic finalisation fix passes; credential-backed rerun pending. The historical real-provider translation latency checkpoint remains `fail`.

## 2026-06-25 Turn Finalisation Fix

The Live adapter no longer relies on `input_transcription.finished` as the only
way to close a spoken turn. It now:

- configures Gemini automatic activity detection with an 800 ms silence window;
- accumulates provider partial transcripts under one utterance ID; and
- emits one normalised `transcript.final` when
  `server_content.turn_complete` closes the turn.

The provider-shaped integration test proves this full downstream path:

```text
input_transcription partials
  -> server_content.turn_complete
  -> transcript.final
  -> translation.final
  -> route.decision
  -> cards.render
```

Recorded local verification:

```text
Focused Live adapter/runtime tests: 13 passed
Full backend suite: 163 passed
Agent eval suite: 15/15 passed
Ruff: pass
MyPy: pass
```

No `GOOGLE_API_KEY` or `GEMINI_API_KEY` was available in this Windows
environment, so this update does not claim a fresh real-provider pass. The next
credential-backed smoke test must replay actual 16 kHz PCM and confirm that a
natural silence produces the same final event and downstream card path.

References:

- [Gemini Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
- [Gemini Live WebSocket API reference](https://ai.google.dev/api/live)

## 2026-06-24 Dev Agent Update

The application defaults now use the council-approved Gemini 2.5 models:

- Live audio session: `gemini-2.5-flash-native-audio-preview-12-2025`
- Faithful text sidecar: `gemini-2.5-flash`

The backend now opens the Google GenAI SDK Live connection, enables input/output audio transcription, forwards 16 kHz PCM input, normalises transcription/audio/tool-call messages, and bridges provider audio back through the existing FastAPI WebSocket. The text sidecar uses deterministic prompting and low thinking, and runs only for English turns; Mandarin parent turns remain on the original transcript path. Contract and integration tests pass without credentials.

This does not replace the historical provider measurements below. A new credential-backed latency capture is still required before the real checkpoint status can change from `fail`.

## Decision

The public runtime remains backend-proxy: React connects only to FastAPI, and FastAPI owns the single Gemini Live agent-mode session. A credential-backed Python SDK smoke test established a Live session, sent a turn, and received a complete audio response. The ten-utterance probe also produced 10/10 final `input_transcription` results at 305 ms P95, so there is no evidence requiring a client-direct migration or a second Live audio stream.

The remaining blocker is the text translation sidecar. Phase 06 must keep this provider detail behind the backend adapter and resolve its latency, rate-limit, retry, and output-shape behaviour without lowering the Phase 00 threshold.

## Deterministic Fixture Result

Command:

```bash
backend/.venv/bin/python backend/scripts/validate_live_transcription.py \
  --fixture backend/tests/fixtures/live/input_transcription_session.json
```

Recorded result:

```json
{"status":"pass","utterance_count":10,"usable_final_count":10,"transcription_p95_ms":900,"translation_p95_ms":410,"advice_contamination_count":0,"reasons":[]}
```

The fixture proves evaluator behaviour and sanitised capture shape. It does not prove the provider emits usable agent-mode transcription.

## Real Provider Checkpoint

A development credential was available for an opt-in run using ten synthetic pharmacy utterances. No credential, raw provider message, raw audio, or real health data was written to the repository.

Observed backend Live results:

- Python async Live connection: pass.
- Complete bidirectional turn with audio response: pass.
- Final input transcriptions: 10/10.
- Input-transcription P95 after audio end: 305 ms.

The configured `gemini-3.5-flash` text-sidecar capture returned a formal evaluator result of:

```json
{"status":"fail","utterance_count":10,"usable_final_count":10,"transcription_p95_ms":305,"translation_p95_ms":2056,"advice_contamination_count":0,"reasons":["translation_latency_exceeded"]}
```

Manual review also rejected several default-thinking translations because the 160-token probe response was truncated or contained formatting fragments. A one-sample test with `thinking_level="minimal"` restored a faithful direct translation at 1,076 ms, but the free-tier daily quota was exhausted before a ten-sample repeat. A separate `gemini-3.1-flash-lite` minimal-thinking comparison produced faithful direct translations for all ten samples, but its 12,764 ms P95 included long provider retry/quota waits and also failed the latency gate.

Therefore the real Phase 00 status is `fail`, not `blocked_missing_credentials` and not `pass`. Input transcription is validated; translation-sidecar latency and provider-limit behaviour remain open for Phase 06.

For a future repeat, perform the ten-utterance session with synthetic pharmacy phrases, export only the sanitised normalised capture, then run:

```bash
backend/.venv/bin/python backend/scripts/validate_live_transcription.py \
  --real --capture /path/to/sanitised-capture.json
```

Pass requires at least 9 usable finals, transcription P95 no more than 1,500 ms, translation P95 no more than 1,000 ms, and zero advice contamination. Raw audio, provider responses, credentials, and real health data must not be committed.
