# Phase 03: Elderly UI on Mock Runtime Implementation Plan

> Execute with strict TDD, frontend-app-builder design approval, and browser snapshot verification.

## Goal

Build the complete pharmacy conversation UI against canonical mock runtime events.

## Non-Goals

No backend, Gemini, real microphone upload, persistence, or tool execution.

## Source of Truth

`docs/UI_UX_PLAN.md`, runtime/card specs, Phase 02 frontend types.

## Previous Phase Artifacts

Wire schemas, mappers, fixtures, constants, and error codes.

## Entry Conditions

Phase 02 is green and the primary mobile screen, Guardian warning, confirmation sheet, summary, and error concepts are approved.

## Exit Checkpoint

All required states are accessible, responsive, test-covered, and browser-verified without typing.

## Files

### Create

Pages and components listed in `AGENTS.md`; conversation hooks; mock runtime adapter; design tokens; component tests.

### Modify

`frontend/src/app/App.tsx`, router, Tailwind entry.

### Test

RTL tests for every visible state and action.

### Fixtures

Phase 02 runtime fixtures plus complete mock pharmacy sequences.

### Migrations

None.

## Public Contracts

`ConversationRuntime` exposes `connect`, `disconnect`, `sendCommand`, and event subscription. Components receive view models and callbacks only.

## Data Flows

- Normal: mock event → runtime hook → mapper → component.
- Error: typed fallback/error → action-based message.
- Replay: duplicate event ID ignored.
- Safety: warning visually separate from translation.
- Cleanup: disconnect removes listeners and media handles.

## TDD Tasks

1. RED status-bar tests; GREEN event-driven states; refactor state labels.
2. RED subtitle tests; GREEN replaceable partial English and append-only Chinese.
3. RED card tests; GREEN selection then confirmation sheet with no immediate action.
4. RED Guardian/self-speak tests; GREEN safe controls.
5. RED summary/fallback tests; GREEN review/retry/cancel states.
6. RED accessibility tests; GREEN 48px targets, labels, focus, contrast classes.

Each RED uses `npm --prefix frontend run test -- <file> --run` and must fail the named assertion. Each GREEN reruns the focused file; refactor reruns the full frontend suite.

## Rollback

Remove Phase 03 UI files; retain Phase 02 contracts.

## Checkpoint

Lint, typecheck, tests, and build pass. Playwright CLI snapshots mobile and desktop, exercises select/cancel/self-speak, and stores only ignored QA output.

## Stop Conditions

Translation/advice mixing, icon-only critical controls, inert buttons, `any`, or timer-faked status blocks progress.

## Commit Boundaries

- `feat(ui): add accessible conversation states`
- `feat(ui): add confirmation and Guardian flows`

## Next Artifacts

Complete UI, runtime interface, mock adapter, and browser QA ledger.

## Exact File Manifest

- Create: `frontend/src/pages/StartPage.tsx`, `ConversationPage.tsx`, `VisitSummaryPage.tsx`.
- Create: `frontend/src/components/StatusBar.tsx`, `TwoLayerSubtitle.tsx`, `ResponseCard.tsx`, `ConfirmationSheet.tsx`, `GuardianWarningCard.tsx`, `BottomControls.tsx`.
- Create: `frontend/src/features/conversation/hooks/useLiveConversation.ts`, `useCardConfirmation.ts`.
- Create: `frontend/src/features/conversation/runtime/ConversationRuntime.ts`, `MockConversationRuntime.ts`.
- Create: `frontend/src/features/conversation/reducer.ts`, `viewModels.ts` and colocated `*.test.tsx` files.
- Create fixtures: `frontend/src/test/fixtures/mock-pharmacy-flow.ts`, `mock-privacy-flow.ts`, `mock-fallback-flow.ts`.
- Modify: `frontend/src/app/App.tsx`, `frontend/src/app/router.tsx`, `frontend/src/styles/index.css`.
- Migration/seed: none. Cleanup command: `rm -rf frontend/coverage frontend/dist output` only after confirming those paths contain generated artifacts.

## Exact Public Types and Error Codes

```ts
export interface ConversationRuntime {
  connect(sessionId: string): Promise<void>;
  disconnect(): Promise<void>;
  sendCommand(command: RuntimeCommandView): Promise<void>;
  subscribe(listener: (event: RuntimeViewEvent) => void): () => void;
}

export type ConversationStatus =
  | "idle" | "listening" | "transcribing" | "translating"
  | "checking" | "needs_confirmation" | "speaking" | "blocked"
  | "error" | "reconnecting" | "ended";

export interface ConversationState {
  status: ConversationStatus;
  partialEnglish: string;
  chineseSegments: readonly TranslationSegmentView[];
  activeCardSet: CardSetView | null;
  confirmation: ConfirmationView | null;
  guardianWarning: GuardianWarningView | null;
  visibleError: SafeRuntimeMessageView | null;
  seenEventIds: ReadonlySet<string>;
}
```

Frontend error codes rendered in this phase are `INVALID_EVENT_PAYLOAD`, `SEQUENCE_GAP`, `TRANSLATION_UNAVAILABLE`, `SESSION_RESUME_UNAVAILABLE`, and `RUNTIME_DISCONNECTED`. Components receive already mapped safe messages and never raw exceptions.

## Executable TDD Ledger

Each row is an independent RED→GREEN→REFACTOR cycle. Write only the named test first. Verify RED with `npm --prefix frontend run test -- <test-file>` and require the named assertion to fail, not an import/config error. GREEN may create only the listed production file. Verify GREEN with the same command, then run `npm --prefix frontend run test`. REFACTOR may extract view-only helpers; rerun test, lint, and typecheck.

| Cycle | RED test and exact assertion | GREEN file/behaviour |
|---|---|---|
| 03.1 | `StatusBar.test.tsx::shows status from runtime events`; expects `正在聆听` after `audio.listening` | `StatusBar.tsx`; exhaustive label map, no timer |
| 03.2 | `TwoLayerSubtitle.test.tsx::replaces partial and appends finals`; expects one replaced English partial and two immutable Chinese segments | `TwoLayerSubtitle.tsx`, `reducer.ts`; dedup by event and segment IDs |
| 03.3 | `ResponseCard.test.tsx::selection_only_opens_confirmation`; expects no `card.confirm` until confirmation button | `ResponseCard.tsx`, `ConfirmationSheet.tsx`, `useCardConfirmation.ts` |
| 03.4 | `GuardianWarningCard.test.tsx::warning_is_not_translation`; expects separate alert region and privacy label | `GuardianWarningCard.tsx` |
| 03.5 | `BottomControls.test.tsx::self_speak_sends_escape_only`; expects one `control.self_speak` and no card/tool command | `BottomControls.tsx` |
| 03.6 | `ConversationPage.test.tsx::fallback_keeps_english`; expects English final retained and Chinese area unchanged | `ConversationPage.tsx` reducer binding |
| 03.7 | `ConversationPage.a11y.test.tsx::critical_controls_are_named`; expects accessible names and minimum `min-h-12` class | shared components and Tailwind tokens |

Canonical RED test shape:

```tsx
it("selection only opens confirmation", async () => {
  const runtime = new MockConversationRuntime(cardFlow);
  render(<ConversationPage runtime={runtime} sessionId="ses_test" />);
  await userEvent.click(await screen.findByRole("button", { name: /请问这个药/ }));
  expect(runtime.commands).toEqual([
    { eventType: "card.select", payload: { cardSetId: "set_1", cardId: "card_1", revision: 1 } },
  ]);
  expect(screen.getByRole("dialog", { name: "确认让 KK 代您表达" })).toBeVisible();
});
```

## Checkpoint Output and Stop Line

Run `npm --prefix frontend run lint`, `typecheck`, `test`, and `build`, then browser-check widths 360px and 1280px. Expected output is zero lint/type errors, all test files passing, and a Vite bundle with no privileged environment names. Do not enter Phase 04 if any critical control lacks a label, selection sends confirmation, translated segments mutate, or browser verification requires typed text.
