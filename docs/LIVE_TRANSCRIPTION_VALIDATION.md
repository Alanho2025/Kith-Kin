# Gemini Live Input Transcription Validation

Version: 0.1.0
Recorded: 2026-06-22
Status: `blocked_missing_credentials` for the real provider checkpoint

## Decision

The public runtime remains backend-proxy: React connects only to FastAPI, and FastAPI owns the single Gemini Live agent-mode session. The visual track consumes final `input_transcription` and sends it to the Gemini text translation adapter. If an authenticated run proves agent-mode transcription unreliable, Phase 06 may enable the dedicated Live Translate fallback behind the backend adapter without changing public WebSocket events.

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

No `GOOGLE_API_KEY` is present in the workspace. Running `--real` therefore exits with code 2 and reports `blocked_missing_credentials`; it never fabricates metrics or marks the real gate passed.

After the owner provides a development credential, perform the ten-utterance AI Studio session with synthetic pharmacy phrases, export only the sanitised normalised capture, then run:

```bash
backend/.venv/bin/python backend/scripts/validate_live_transcription.py \
  --real --capture /path/to/sanitised-capture.json
```

Pass requires at least 9 usable finals, transcription P95 no more than 1,500 ms, translation P95 no more than 1,000 ms, and zero advice contamination. Raw audio, provider responses, credentials, and real health data must not be committed.
