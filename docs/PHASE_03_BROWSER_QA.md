# Phase 03 Browser QA Ledger

Recorded: 2026-06-22
Status: partial; final responsive screenshot sign-off blocked by external browser-tool usage limit

## Design References

- `docs/design/phase-03-conversation-responsive.png`
- `docs/design/phase-03-safety-confirmation-summary.png`

The design system uses a deep navy status rail and text, teal listening/primary actions, calm amber Guardian warnings, true white content surfaces, robust Chinese typography, open desktop rails, and minimum 48px named controls.

## Browser Method

The in-app Browser could not initialize because its control bridge lacked required sandbox metadata. The fallback used the bundled Playwright CLI against `http://127.0.0.1:5173` with a real Vite browser session. No typing, microphone permission, credential, or personal data was used.

## Verified Workflow

1. Start page rendered the Kith&Kin heading, privacy note, and one-tap `开始药房对话` action.
2. Conversation rendered event-driven `KK 正在聆听`, secondary English, dominant append-only Chinese, a separate KK hint, two named response cards, and four named bottom controls.
3. Selecting a response card emitted only selection behaviour and opened the `确认让 KK 代您表达` dialog.
4. The dialog exposed explicit `确认并说给药剂师`, `取消`, and `我自己说` controls.
5. Browser testing found that synchronous mock acknowledgement could interrupt a real click; the mock now responds on a later task and the RTL regression passes.
6. Browser testing found that cancel did not dismiss local confirmation state; an RTL RED now proves dismissal plus the `card.cancel` command, and the GREEN passes.

## Fidelity Ledger

| Comparison point | Concept | Browser/DOM evidence | Status |
|---|---|---|---|
| Copy hierarchy | Chinese dominant, English secondary | Separate labelled regions with 3xl–5xl Chinese and base English | matched structurally |
| Container model | open conversation column plus desktop recent rail | desktop DOM exposes one recent rail and one open main column | matched structurally |
| Palette | navy, teal, white, amber | implemented tokens and semantic component classes | implemented; final screenshot pending |
| Confirmation safety | selection then named bottom sheet | real browser opened the named modal; no automatic confirm | verified |
| Escape controls | named, minimum 48px | DOM and RTL cover self-speak, wait, repeat, end, cancel | verified |
| Responsive layout | 360px mobile and 1280px desktop | responsive CSS/build present | final visual screenshots pending |

## Remaining Gate

The external Playwright action quota was exhausted immediately before the post-fix cancel recheck and 360px/1280px screenshots. The rejection prohibited retries or alternate automation workarounds. Until those screenshots and final `view_image` comparison are completed, Phase 03 is implemented but not fully browser-accepted, and Phase 04 retains that dependency.
