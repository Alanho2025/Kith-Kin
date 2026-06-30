# Round 1 Failure Matrix

Round 1 is intentionally fail-first. These checks convert the pharmacy-counter gaps into deterministic tests/evals before runtime fixes.

| Gap | Test / Eval IDs | Expected current failure |
|---|---|---|
| Confirmed response-card content is appended to the conversation log as `KK 代说`, even though it is not actual AI speech. | T01, T02, T03, E18 | Reducer still appends `speaker: "kk"` turns on `card.confirmed`; trace replay contains `KK 代说` card text. |
| Card action lifecycle is mixed with real speech/translation turns. | T01, T02, T03, E18 | Select/confirm/cancel does not stay isolated from `turns`. |
| Main workspace can lose the latest useful translation or stay in a confusing state after routing/product/card events. | T04, T13, T24, T18 | Passive route remains `checking`; backend browser smoke expects the main translation and product table to stay visible. |
| Typed pharmacist fallback can be attributed as elder speech because active mic speaker overrides the declared typed speaker. | T05, E24 | `audio.speaker_changed(parent)` causes typed `speaker=pharmacist` transcript to be observed as `parent`. |
| Typed fallback and microphone audio can both feed the backend session. | T06 | Runtime keeps sending mic binary frames after typed `transcript.final`. |
| Gemini Live model thought/status text enters transcript, translation, routing, and card generation. | T07, T08, E20 | `model_turn.parts[].text` and thought strings become `ProviderTranscriptEvent` / runtime payload text. |
| Confirmed speech can report completion without actual audio bytes. | T09, T10, E23 | No-audio provider turn can emit `audio.speaking completed`; trace has `binary_frame_count = 0`. |
| Natural pharmacist product wording does not create a product options table. | T11, T12, T13, T18, E16, E21 | Parser/runtime fail on `Panadol costs eight dollars...` style wording; browser smoke expects table. |
| Cards are not grounded to the latest pharmacist question. | T15, E19 | Identity request can show medication/allergy or generic cards instead of name/birthday response. |
| Health disclosure cards over-bundle allergy and medication facts. | T16 | One spoken card can disclose both Lisinopril and Penicillin instead of a split/checklist confirmation. |
| Spoken card text uses third-person or meta instruction instead of direct utterance. | T14 | Guardian currently does not block `The patient...` / `Let KK...` card text. |
| Mock E2E is labelled like real product E2E. | T17 | Existing e2e is now explicitly named mock smoke; new backend smoke carries the real-backend contract. |
| Backend browser flow is not covered with typed pharmacist input, product table, no fake KK log, and summary. | T18, T22 | New backend smoke is expected to fail until real backend flow satisfies the product goal. |
| Ticket/origin failures are silent or not user-visible. | T19, T20 | Runtime rejects ticket request instead of emitting safe Chinese error; development defaults omit `127.0.0.1:5173`. |
| Session end summary is missing or incomplete in the end-to-end flow. | T21, T22, E22 | Browser/trace does not show a summary with products/payment; service-level summary checks protect structured fields. |
| Purchase/payment checkout is not covered end-to-end. | T23, E22 | Summary/browser flow must preserve purchase intent, payment instruction, and price without medical recommendation. |
