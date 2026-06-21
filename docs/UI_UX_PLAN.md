# Kith&Kin UI/UX Plan

Version: 0.1
Status: Engineering handoff draft
Primary users: Elderly Chinese-speaking users in Australia
Primary scenario: Pharmacy visit
Primary device assumption: Mobile phone
Primary language pair: Mandarin Chinese <-> English

---

## 1. Purpose

This document defines the UI and UX plan for Kith&Kin.

Kith&Kin is not a normal translation app. It is a real-time AI companion for elderly users who need to communicate safely with pharmacy professionals when their family members are not present.

The UI must help elderly users:

1. Understand what the pharmacist says.
2. See faithful Chinese translation in large text.
3. Choose from three simple Chinese response options.
4. Confirm before the agent speaks for them.
5. Stay protected when the conversation involves health, payment, identity, or family information.
6. Pause, stop, or speak by themselves at any time.

This document is written for engineers. It defines user flows, screen structure, component behaviour, accessibility requirements, safety UX, and acceptance criteria.

---

## 2. UX Strategy

The product must follow this UX principle:

```text
Reduce cognitive load during high-pressure pharmacy conversations.
```

The elderly user may be nervous, may not read English well, may have hearing difficulty, and may not be confident using complex mobile apps. The UI must avoid complex navigation and must focus on the current conversation.

The user should never need to search through menus during the pharmacy interaction.

The main screen must answer four questions at all times:

1. Is KK listening?
2. What did the pharmacist say?
3. What should I do next?
4. Is it safe to share or say this?

---

## 3. Target User Assumptions

### 3.1 Elderly user characteristics

The user may:

- have limited English ability
- have reduced vision
- have reduced hearing
- have slower reading speed
- have slower touch accuracy
- feel nervous during medical or pharmacy conversations
- be unfamiliar with mobile app patterns
- hesitate before confirming a response
- depend on family members for health-related follow-up

### 3.2 Context of use

The user may be:

- standing at a pharmacy counter
- holding the phone with one hand
- in a noisy environment
- under time pressure
- speaking to a professional staff member
- worried about making a medical or payment mistake

### 3.3 UX implication

The UI must be:

- large
- calm
- simple
- low-interaction
- confirmation-based
- safety-first
- readable at a glance
- usable without typing

---

## 4. Design Principles

### 4.1 One-screen conversation

The main pharmacy experience should happen on one screen.

Do not use multi-page navigation during the live conversation.

### 4.2 Large Chinese first

Chinese translation and Chinese response cards must be visually dominant.

English transcript can be shown, but it must be secondary.

### 4.3 Action cards over free typing

The elderly user should not need to type.

When a reply is needed, KK should generate 2-3 simple Chinese cards.

### 4.4 Confirm before speaking

KK must never speak for the user without explicit confirmation.

Every card that triggers TTS must require a confirmation tap.

### 4.5 Safety must be visible

Guardian safety actions must be shown clearly.

If KK blocks a privacy or medical risk, the user should understand why.

### 4.6 No silent waiting

Face-to-face conversation cannot tolerate dead silence.

If KK is checking memory, medicine, or safety, show a visible checking state and optionally play a short filler such as:

```text
KK 正在帮您确认，请稍等。
```

### 4.7 Always provide an escape path

The user must always have:

- 我自己说
- 请稍等
- 重复一下
- 停止
- 返回

---

## 5. Information Architecture

The app should have a minimal structure.

```text
Start Screen
  ↓
Pharmacy Conversation Screen
  ↓
Visit Summary Review
  ↓
Family Notification Confirmation
  ↓
Session Complete
```

No deep navigation is required for the MVP.

---

## 6. Core User Flow

### 6.1 Happy path

```text
User opens KK
→ User taps "Start pharmacy conversation"
→ KK shows listening state
→ Pharmacist speaks English
→ English transcript appears in small text
→ Chinese translation appears in large text
→ Router detects that the user may need help replying
→ Companion generates three Chinese response cards
→ Guardian checks cards
→ User selects one card
→ User confirms
→ KK speaks or shows the English response to the pharmacist
→ Visit ends
→ KK shows a Chinese summary
→ User confirms whether to notify family
→ KK sends or saves summary
```

### 6.2 Privacy risk path

```text
Pharmacist asks for sensitive information
→ Guardian detects privacy risk
→ Normal response path is blocked
→ UI shows privacy warning card
→ User sees safe choices
→ User confirms what to share or declines
```

### 6.3 Medical risk path

```text
Pharmacist suggests a new medicine
→ Router marks pharmacy risk
→ Companion checks memory and medication profile
→ Companion calls drug interaction check
→ KK does not give medical advice
→ UI shows three safe question cards
→ User asks pharmacist to confirm
```

### 6.4 User speaks by themselves

```text
User taps "我自己说"
→ KK stops generating response cards
→ Mic stays open for parent speech
→ KK does not speak for the user
→ UI shows "您可以自己说，我会继续帮您翻译"
```

---

## 7. Main Screen Layout

### 7.1 Layout priority

The main screen should be vertically structured:

```text
[Status Bar: Listening / Translating / Checking / Speaking]

[Small English Transcript]
[Large Chinese Translation]

[Agent Hint or Guardian Warning]

[2-3 Chinese Response Cards]

[Bottom Controls]
- 我自己说
- 请稍等
- 重复
- 结束
```

### 7.2 Screen regions

#### A. Status bar

Purpose:

- show system state
- reduce anxiety
- prevent user confusion

States:

```text
KK 正在听
KK 正在翻译
KK 正在帮您确认
KK 正在说话
请您确认后再发送
网络不稳定，正在重连
```

#### B. English transcript area

Purpose:

- debug and transparency
- show that the system is hearing the pharmacist
- secondary information

Rules:

- smaller than Chinese translation
- grey or visually secondary
- can update live
- does not need to be the main reading area

#### C. Chinese translation area

Purpose:

- primary understanding channel

Rules:

- largest text on the screen
- high contrast
- stable after final transcription
- append-only during conversation
- do not rewrite already-rendered Chinese text
- show only faithful translation
- do not mix KK advice into this area

#### D. Agent hint area

Purpose:

- show KK's reasoning or risk reminder

Examples:

```text
KK 提醒：这个问题可能和用药安全有关，建议请药剂师确认。
KK 提醒：这个问题涉及个人信息，请先确认是否要告诉对方。
KK 正在帮您检查过敏和用药记录。
```

Rules:

- visually separate from faithful translation
- must not look like pharmacist speech
- should be short

#### E. Response card area

Purpose:

- provide simple choices for the elderly user

Rules:

- show 2-3 cards
- default target is 3 cards
- each card must be Chinese-first
- each card should have short text
- each card should include a clear tap action
- each card must require confirmation before TTS

#### F. Bottom controls

Required buttons:

```text
我自己说
请稍等
重复
结束
```

Rules:

- buttons must be large
- no icon-only actions
- use text labels
- keep controls in the same location

---

## 8. Component Specifications

## 8.1 Status Bar

### Purpose

Shows what KK is doing now.

### States

| State | Chinese label | Behaviour |
|---|---|---|
| idle | 准备好了 | Waiting for user to start |
| listening | KK 正在听 | Mic is active |
| transcribing | 正在识别语音 | Audio is being transcribed |
| translating | 正在翻译 | Text translation sidecar is running |
| checking | KK 正在帮您确认 | Agent or MCP tool is running |
| needs_confirmation | 请您确认 | Waiting for user confirmation |
| speaking | KK 正在说话 | TTS is playing, mic should be muted |
| blocked | KK 已为您拦截 | Guardian blocked unsafe action |
| error | 出现问题，请稍等 | Fallback state |
| reconnecting | 网络不稳定，正在重连 | WebSocket reconnecting |

### Engineering notes

- Status must be driven by runtime events.
- Do not fake status purely on frontend timers.
- `speaking` must trigger mic mute.
- `needs_confirmation` must block automatic TTS.

---

## 8.2 Two-Layer Subtitle

### Purpose

Shows both original transcript and faithful translation.

### Layout

```text
English transcript: small and secondary
Chinese translation: large and primary
```

### Rules

1. English transcript can update live.
2. Chinese translation should update after final utterance.
3. Chinese translation must be stable and append-only.
4. KK advice must not be inserted into the translation area.
5. If translation fails, show English transcript and a fallback message.

### Fallback message

```text
中文翻译暂时不可用。请稍等，KK 正在重新连接。
```

---

## 8.3 Response Cards

### Purpose

Help the elderly user respond without typing.

### Card content

Each card must include:

```yaml
response_card:
  zh_text: string
  en_text: string
  risk_level: normal | caution | privacy | medical | urgent
  action_type: speak | show_to_pharmacist | save_memory | notify_family | no_action
  requires_confirmation: true
```

### Visual hierarchy

Each card should show:

```text
[Chinese response]
[Small English back-translation]
[Action label: 点击后确认]
```

### Example

```text
请帮我确认这个药会不会和我现在吃的降血压药冲突。
Could you please check whether this medicine conflicts with my current blood pressure medicine?
```

### Confirmation flow

Card tap should not immediately speak.

Flow:

```text
Tap card
→ Show confirmation sheet
→ User taps "确认并说给药剂师"
→ TTS speaks English response
```

### Confirmation sheet text

```text
KK 将会替您说出下面这句话。请确认是否继续。
```

Buttons:

```text
确认并说给药剂师
取消
我自己说
```

---

## 8.4 Guardian Warning Card

### Purpose

Show privacy, medical, or security blocks.

### Types

| Type | Example |
|---|---|
| privacy | 这个问题涉及个人信息 |
| payment | 这个问题涉及付款信息 |
| medical | 这个问题涉及用药安全 |
| identity | 这个问题涉及身份证件信息 |
| family | 是否要通知家人 |

### Guardian card rules

1. Use calm language.
2. Do not scare the user.
3. Explain the reason in one sentence.
4. Provide safe options.
5. Require confirmation before sharing.

### Example: payment request

```text
这个问题涉及付款信息。KK 不会直接说出您的银行卡或信用卡信息。
```

Options:

```text
请问是否可以用其他安全付款方式？
我自己处理
请稍等，我要问家人
```

---

## 8.5 Family Summary Review

### Purpose

Let the user review the visit summary before saving or notifying family.

### Summary structure

```text
今天药局沟通重点

1. 提到的药：
2. 药剂师建议：
3. 需要家人跟进：
4. KK 已提醒的问题：
```

Buttons:

```text
发送给家人
只保存，不发送
修改
取消
```

### Rules

- Never notify family without confirmation.
- Show exactly what will be sent.
- Sensitive content should be short and relevant.
- If sending fails, show retry option.

---

## 8.6 Error and Fallback States

### Translation failure

```text
中文翻译暂时不可用。KK 会继续显示英文原文，并尽快恢复中文。
```

### Memory failure

```text
KK 暂时无法读取您的用药记录。请直接让药剂师帮您确认。
```

### Drug lookup failure

```text
KK 无法确认这个药的信息。请药剂师写下药名和用法。
```

### Network failure

```text
网络不稳定，KK 正在重新连接。请稍等。
```

### TTS failure

```text
KK 暂时无法播放语音。您可以把这句话给药剂师看。
```

---

## 9. Interaction Design Rules

### 9.1 No auto-send

The system must not auto-speak, auto-save, or auto-send.

### 9.2 No hidden critical actions

Any action involving health, identity, payment, address, or family must be visible and confirmable.

### 9.3 One primary action at a time

Each state should have one obvious primary action.

Examples:

- Start conversation
- Confirm and speak
- Send to family
- Try again

### 9.4 Avoid destructive gestures

Do not rely on swipe gestures, long press, double tap, or drag interactions.

### 9.5 Prevent accidental taps

Critical actions require a confirmation step.

Examples:

- speaking for user
- sharing allergies
- sending family summary
- saving medical visit summary

### 9.6 Give feedback after every tap

Every tap should produce visible feedback.

Examples:

```text
已选择
正在确认
已发送
已取消
```

---

## 10. Accessibility Requirements

### 10.1 Typography

Recommended minimum sizes:

| Element | Size |
|---|---:|
| Chinese translation | 28-36 px |
| Response card Chinese text | 22-28 px |
| Primary button | 20-24 px |
| Status text | 18-22 px |
| English transcript | 14-16 px |

Rules:

- Use simple sans-serif fonts.
- Avoid thin font weights.
- Avoid dense paragraphs.
- Avoid all caps English.
- Keep line length short.

### 10.2 Touch targets

Recommended target size:

| Element | Minimum |
|---|---:|
| Primary button | 48 × 48 px |
| Response card | full-width card |
| Bottom control | 48 × 48 px |
| Emergency stop | 56 × 56 px |

Rules:

- Add enough spacing between buttons.
- Avoid placing critical actions too close together.
- Use full-width cards where possible.

### 10.3 Colour and contrast

Rules:

- Use high contrast for text.
- Do not rely on colour alone.
- Pair colour with text labels.
- Use calm colours for normal state.
- Use clear but not alarming colour for warning state.
- Avoid low-contrast grey for important text.

### 10.4 Motion and animation

Rules:

- Avoid unnecessary animation.
- Keep transitions short.
- Do not animate large text repeatedly.
- Do not use flickering effects.
- Show stable content for final translation.

### 10.5 Cognitive accessibility

Rules:

- Use simple Chinese.
- Show one decision at a time.
- Avoid technical terms.
- Avoid long instructions.
- Use repeated patterns.
- Keep buttons in consistent locations.
- Use confirmation before high-risk actions.
- Show clear next step.

---

## 11. Content Design

### 11.1 Voice and tone

The tone should be:

- calm
- respectful
- simple
- supportive
- not childish
- not overly emotional

### 11.2 Chinese writing rules

Use:

```text
请问...
请帮我确认...
我想先...
是否可以...
```

Avoid:

```text
您必须...
您应该...
这个一定...
我建议您服用...
```

### 11.3 Medical safety wording

Use safe communication support:

```text
请帮我确认这个药是否适合我。
请问这个药会不会和我现在的药冲突？
请问这个药有什么副作用？
请问我需要注意什么？
```

Avoid medical advice:

```text
你可以吃这个药。
你不要吃这个药。
这个药很安全。
这个药很危险。
```

### 11.4 Privacy wording

Use:

```text
这个问题涉及个人信息。请确认是否要告诉对方。
KK 不会自动说出您的个人信息。
```

Avoid:

```text
危险！不要说！
对方可能不安全！
```

The UI should protect the user without creating panic.

---

## 12. Safety UX

Safety must be part of the user experience.

### 12.1 Safety events that must change UI state

| Event | UI response |
|---|---|
| Pharmacist asks for credit card | Show payment privacy block |
| Pharmacist asks for passport | Show identity confirmation |
| Pharmacist asks for address | Ask why needed and require confirmation |
| Pharmacist asks about allergies | Show allergy confirmation |
| New medicine mentioned | Show medical caution cards |
| Drug interaction possible | Show pharmacist-confirmation card |
| Family notification proposed | Show summary review |
| Memory write proposed | Show save confirmation |
| Agent uncertain | Show clarification card |

### 12.2 Privacy block example

```text
这个问题涉及付款信息。KK 不会直接说出您的银行卡或信用卡信息。
```

Response options:

```text
请问是否可以用其他安全付款方式？
我需要先问家人
我自己处理
```

### 12.3 Allergy confirmation example

```text
我记录中有青霉素过敏。是否要告诉药剂师？
```

Options:

```text
告诉药剂师
先不要说
我自己说
```

---

## 13. Audio UX

Audio is part of UX, not only engineering.

### 13.1 Half-duplex rule

When KK is speaking, the microphone must be muted.

Reason:

- Prevent KK from hearing its own TTS.
- Prevent self-looping transcription.
- Avoid confusing the user.

### 13.2 Audio state display

When TTS is playing, show:

```text
KK 正在说话，麦克风已暂停
```

After TTS ends, show:

```text
KK 正在听
```

### 13.3 User control

Required controls:

```text
停止说话
我自己说
重复上一句
```

### 13.4 Filler audio

Use filler only when needed.

Allowed:

```text
KK 正在帮您确认，请稍等。
```

Avoid:

```text
我正在进行复杂的医疗安全分析。
```

---

## 14. Engineering Handoff Requirements

### 14.1 Required frontend events

The frontend must handle:

```ts
type UIEvent =
  | "session.ready"
  | "audio.listening"
  | "audio.speaking"
  | "audio.muted"
  | "transcript.partial"
  | "transcript.final"
  | "translation.pending"
  | "translation.final"
  | "route.decision"
  | "guardian.warning"
  | "cards.render"
  | "card.selected"
  | "card.confirmed"
  | "summary.render"
  | "notification.sent"
  | "fallback.show"
  | "error.show";
```

### 14.2 Required frontend state

```ts
type ConversationUIState = {
  sessionStatus:
    | "idle"
    | "listening"
    | "transcribing"
    | "translating"
    | "checking"
    | "needs_confirmation"
    | "speaking"
    | "blocked"
    | "error"
    | "reconnecting";

  englishTranscript: string;
  chineseTranslation: string;
  agentHint: string | null;
  responseCards: ResponseCard[];
  selectedCardId: string | null;
  guardianWarning: GuardianWarning | null;
  isMicMuted: boolean;
  isTtsPlaying: boolean;
};
```

### 14.3 Required response card type

```ts
type ResponseCard = {
  cardId: string;
  cardType:
    | "ask_question"
    | "confirm_info"
    | "refuse_sensitive_request"
    | "ask_to_write_down"
    | "family_action"
    | "self_speak";

  zhText: string;
  enText: string;
  riskLevel: "normal" | "caution" | "privacy" | "medical" | "urgent";
  requiresParentConfirmation: boolean;
  requiresGuardianApproval: boolean;

  action: {
    type: "speak" | "show_to_pharmacist" | "save_memory" | "notify_family" | "no_action";
  };
};
```

### 14.4 Required Guardian warning type

```ts
type GuardianWarning = {
  warningId: string;
  type: "privacy" | "payment" | "identity" | "medical" | "family" | "unknown";
  zhTitle: string;
  zhMessage: string;
  safeOptions: ResponseCard[];
};
```

---

## 15. Screen-Level Acceptance Criteria

### 15.1 Start screen

Pass criteria:

- User can start pharmacy mode with one tap.
- User understands the app will listen and translate.
- User sees a simple privacy note.
- No complex setup is required.

### 15.2 Conversation screen

Pass criteria:

- User can see system status.
- User can see Chinese translation clearly.
- User can see English transcript as secondary information.
- User can choose from 2-3 Chinese response cards.
- User can confirm before KK speaks.
- User can choose "我自己说".
- User can end the session.

### 15.3 Guardian warning

Pass criteria:

- Privacy or medical risk is clearly shown.
- Unsafe auto-response is blocked.
- User gets safe alternatives.
- User must confirm before sensitive sharing.

### 15.4 Summary screen

Pass criteria:

- User sees visit summary in simple Chinese.
- User can choose to send to family or only save.
- User can cancel.
- User can retry if notification fails.

---

## 16. UX Evaluation Plan

The UI/UX should be tested with task-based evaluation.

### 16.1 Core UX tasks

1. Start a pharmacy conversation.
2. Understand a translated pharmacist sentence.
3. Select one of three Chinese response cards.
4. Confirm that KK should speak for the user.
5. Use "我自己说".
6. Respond to a privacy warning.
7. Review and send family summary.
8. Recover from translation failure.

### 16.2 Success metrics

| Metric | Target |
|---|---:|
| User can start conversation without help | 100% in demo test |
| User can identify Chinese translation area | 100% |
| User can select and confirm a card | 100% |
| User can find "我自己说" | 100% |
| User does not confuse translation with KK advice | 90%+ |
| User understands Guardian warning | 90%+ |
| User can cancel sensitive sharing | 100% |
| User can recover from fallback state | 90%+ |

### 16.3 Demo usability checklist

Before final demo, verify:

- Chinese text is readable from arm's length.
- Response cards are not crowded.
- No important action is icon-only.
- No critical action happens without confirmation.
- Translation and agent advice are visually separate.
- Mic mute state is visible during TTS.
- Guardian warning appears in the privacy test.
- Family summary requires confirmation.
- Error states are understandable.
- The whole hero flow can be completed without typing.

---

## 17. Visual Design Direction

The visual style should be calm, clean, and trustworthy.

### 17.1 Visual personality

Kith&Kin should feel like:

- a calm helper
- a careful interpreter
- a family-aware assistant
- a safe companion

It should not feel like:

- a medical authority
- a chatbot game
- a complex dashboard
- a hospital admin system
- a flashy AI toy

### 17.2 UI density

Use low-density layout.

Rules:

- Fewer words per screen.
- Large spacing.
- Clear section boundaries.
- No crowded menus.
- No dense table during live conversation.

### 17.3 Icon usage

Icons may be used only with text labels.

Do not use icon-only buttons.

---

## 18. Build Priority

### Phase 1: UX skeleton

Build:

- start screen
- conversation screen
- status bar
- English transcript area
- Chinese translation area
- response card area
- bottom controls

Goal:

```text
The user can understand the intended flow without backend integration.
```

### Phase 2: Functional UI

Build:

- event-driven status updates
- response card rendering
- card confirmation modal
- Guardian warning card
- fallback states
- summary review screen
- mic mute indicator

Goal:

```text
The UI can connect to backend runtime events.
```

### Phase 3: Safety UX

Build:

- privacy block flow
- allergy confirmation flow
- medical caution flow
- family notification confirmation
- no-medical-advice card patterns

Goal:

```text
The UI makes Guardian decisions visible and confirmable.
```

### Phase 4: Accessibility pass

Improve:

- font sizes
- contrast
- spacing
- tap target sizes
- simple Chinese wording
- consistent button locations
- fallback readability

Goal:

```text
The interface is usable by elderly users under time pressure.
```

### Phase 5: Visual polish

Improve:

- colour system
- icons
- card styling
- transitions
- logo placement
- demo polish
- presentation quality

Goal:

```text
The product looks trustworthy and ready for the final demo.
```

---

## 19. Non-Goals

The MVP UI will not include:

- full account management
- full medical record editing
- complex settings page
- chat history search
- payment UI
- insurance UI
- GP consultation UI
- family dashboard
- medication management dashboard
- multi-language settings beyond the demo language pair
- icon-only navigation
- swipe-based core actions

---

## 20. Final UX Rule

The UI must support this core promise:

```text
The elderly user should always know what was said, what KK suggests, what will be shared, and when they are still in control.
```

If a design choice makes the user less certain, less safe, or less in control, it should not be used.
