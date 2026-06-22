# Gemini Live Input Transcription Validation

Version: 0.2.0
Recorded: 2026-06-22
Status: `fail` for the real provider checkpoint (`translation_latency_exceeded`)

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
