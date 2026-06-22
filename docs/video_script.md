# Kith&Kin — Capstone Video Script (≤3 min)

**Track:** Concierge Agents
**Tone:** Warm, personal, authentic. This is a story about family.

---

## 0:00 – 0:15 | The Problem

> Visual: Split screen — left side shows an elderly Chinese woman looking confused at a pharmacy counter; right side shows an office worker checking their watch.

**Narrator (voiceover, calm):**
> "My parents moved to Australia to be with us. But during the day, I'm at work. And when they have to go to the pharmacy alone… they can't understand what the pharmacist says, and they can't explain what they need."

> Visual: Text appears — "听不懂，说不出" (Can't understand, can't speak)

**Narrator:**
> "Translation apps help. But they don't know my dad's medical history. They don't know he's allergic to sulfa drugs. And they definitely don't remember what the pharmacist said last time."

---

## 0:15 – 0:45 | What Kith&Kin Does

> Visual: A parent opens KK on a tablet. Simple UI — large Chinese text, two buttons.

**Narrator:**
> "KK is a real-time AI companion. It listens through the Gemini Live API, faithfully translates everything the pharmacist says to oversized Chinese text on screen…"

> Visual: Screen shows English → Chinese real-time translation in big font.

**Narrator:**
> "…and when a decision is needed, KK quietly checks the parent's medical profile, searches past visit records, and offers simple response cards."

> Visual: A card appears — "我问药剂师这个药和我的降压药有没有冲突" [Ask if this conflicts with my blood pressure meds]

**Narrator:**
> "The parent taps to confirm, KK speaks it in English. No typing. No confusion. No saying something they didn't mean to say."

---

## 0:45 – 1:30 | The Hero Moment

> Visual: Split into two visits. Show clean transition.

**Narrator:**
> "Here's what makes KK an agent and not a translator."

> Visual: **Visit 1** — Parent is at the pharmacy. Pharmacist says "Try Coenzyme Q10 for the muscle pain." KK writes this to memory.

**Narrator:**
> "First visit: the pharmacist mentions trying Coenzyme Q10 for statin-related muscle pain. KK writes it to persistent memory."

> Visual: Screen shows "记忆已保存" [Memory saved]. Small notification: "通知已发送给女儿" [Notification sent to daughter].

**Narrator:**
> "After the visit, KK sends a summary to the adult child. Everyone stays in the loop."

> Visual: **Visit 2** — Same pharmacy, days or weeks later. Parent opens KK again.

**Narrator:**
> "Second visit: new session. But KK remembers."

> Visual: KK shows a proactive card — "上次药剂师建议的辅酶Q10，今天要不要一起问清楚？" [Last time the pharmacist mentioned CoQ10 — want to ask about it today?]

**Narrator:**
> "It proactively asks: 'The pharmacist mentioned Coenzyme Q10 last time. Want to ask about it today?'"

> Visual: Parent's face — a small smile of recognition. They tap "Yes."

**Narrator:**
> "That's cross-session memory. That's an agent. And that's what a translation app can never do."

---

## 1:30 – 1:50 | Safety & Privacy

> Visual: Screen shows alert — a privacy card blocks a Medicare number request.

**Narrator:**
> "Safety is built in. KK has a Guardian agent that runs on every turn — detecting prompt injection, blocking requests for credit cards or Medicare numbers, and never speaking for the parent without confirmation."

> Visual: Guardian shield icon, then a consent card with "确认" [Confirm] button.

**Narrator:**
> "Every response card requires explicit tap-to-confirm. The parent stays in control."

---

## 1:50 – 2:30 | How It's Built

> Visual: Quick cuts — code in Antigravity IDE, architecture diagram, terminal running tests.

**Narrator:**
> "Under the hood, KK is built with three course concepts from this capstone."

> Visual: Animated architecture flow:
>   1. ADK Multi-Agent → Router → Companion → Guardian
>   2. MCP Server → persistent memory with SQLite
>   3. Security → ephemeral tokens + consent gating + injection detection

**Narrator (over each visual):**
> "One: ADK multi-agent orchestration — Router, Companion, and Guardian agents with LLM-driven routing.
> Two: MCP Server for persistent cross-session memory — the agent decides when to search, when to write.
> Three: layered security — ephemeral tokens, prompt injection protection, and consent gating."

---

## 2:30 – 2:50 | Demo — See It Live

> Visual: Screen recording of a live pharmacy interaction. 15-20 seconds, real audio.

**Narrator:**
> "Here's a real interaction. Watch the visual track faithfully translate while KK listens for risks."

> Visual: Audio plays. Chinese text scrolls on the big-font panel. A card appears.

---

## 2:50 – 3:00 | Close

> Visual: The narrator (or a photo of their family) on screen.

**Narrator:**
> "Every immigrant child knows that fear: your parents alone at the counter, and you're at work. KK is the one who shows up when you can't."

> Visual: Fade to black. Text: "Kith&Kin — 替你在场的人" [The one who's there for you]
> URL: github.com/Alanho2025/Kith-Kin

---

## Appendix: Production Notes

| Element | Notes |
|---------|-------|
| **Audio** | Voiceover in English. Screen text in Chinese (zh-Hans). |
| **Screen recordings** | Use the KK frontend with a pre-scripted test scenario. Do NOT use live pharmacy footage. |
| **Architecture diagram** | Animated version of `docs/ARCHITECTURE.md` diagram. |
| **Time check** | Script reads at ~150 words/min. Total: ~450 words = 3 min. Read through once with timer. |
| **Music** | Soft, ambient. No dramatic tension — this is about warmth, not crisis. |
| **Antigravity shot** | 5-second cut of Antigravity IDE showing agent code — covers the Antigravity concept. |
