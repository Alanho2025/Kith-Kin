# Real-Time Submission Readiness

This checklist supersedes the older coverage-first priority for the final sprint.
The final demo path is real-time Live API, not Mock mode.

## Direction

- Final demo uses the real-time Live API path.
- Mock mode may remain a development aid, but it is not the submission demo path.
- Visual translation is faithful transcript translation only. It must not include agent advice.
- English audio output is allowed only after the user confirms a response card.

## P0 Pass Bar

- [ ] Live session can be established with `LIVE_TRANSPORT=gemini_live`.
- [x] Frontend can send microphone audio through the backend WebSocket.
- [x] Backend normalizes `input_transcription` into full English utterances.
- [x] Final English utterances enter the text translation sidecar.
- [x] Chinese subtitle segments are append-only.
- [x] Router and Guardian run on final risk turns.
- [x] Companion and MCP tool trajectory are visible in deterministic eval traces.
- [x] Card confirmation can complete.
- [x] Provider audio is ignored unless a confirmed response card requested speech.
- [x] Confirmed card speech enters half-duplex playback.

## Verification Commands

```bash
cd backend
env LIVE_TRANSPORT=backend_proxy GOOGLE_API_KEY= GEMINI_API_KEY= ./.venv/bin/pytest --tb=short -q
./.venv/bin/python ../evals/run.py ../evals/cases.json
./.venv/bin/ruff check .
./.venv/bin/mypy app

cd ../frontend
npm run test -- --run
npm run lint
npm run typecheck
```

## Manual Real-Time Smoke

Run:

```bash
cd backend
LIVE_TRANSPORT=gemini_live ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --host localhost --port 5173
```

Manual checks:

- [ ] Open `http://localhost:5173/`.
- [ ] Start a real session.
- [ ] Speak a complete English sentence.
- [ ] English transcript appears as a full sentence, not only the final fragment.
- [ ] Chinese translation appears only after the utterance is final.
- [ ] Gemini does not speak back automatically.
- [ ] Select and confirm a response card.
- [ ] Only then, the confirmed English card text is sent for audio output.
