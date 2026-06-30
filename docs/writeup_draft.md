# Kith&Kin: The One Who Shows Up When You Can't

**Track:** Concierge Agents  
**Team:** Kith&Kin  
**Repository:** [github.com/Alanho2025/Kith-Kin](https://github.com/Alanho2025/Kith-Kin)

---

## 🧭 The Problem

Every immigrant family knows this anxious moment: your elderly parent is standing alone at an Australian pharmacy counter while you are stuck at work. They struggle to comprehend the pharmacist's English, cannot explain their drug allergies or current medications, and return home without a clear record of the visit.

While translation apps help with vocabulary, the pharmacy counter is a high-risk environment. Elderly patients do not just need word-by-word translation; they need:
1. **Faithful, hallucination-free captions** to read what the pharmacist said.
2. **Safe response options** that don't fabricate medical decisions.
3. **Active privacy protection** against disclosure of sensitive info (credit cards, Medicare, address).
4. **Contextual memory** of previous GP/pharmacy visits.
5. **Adult-child notifications** only after explicit patient consent.

**Kith&Kin** is built for this exact gap. It is a real-time AI companion that assists elderly Chinese-speaking parents during medical encounters, bridging the gap between them, the pharmacist, and their adult children.

---

## 🧠 Why an Agent?

Standard chat interfaces or simple voice translation apps fail at the pharmacy counter because they lack context, memory, and safety boundaries. A pure translation loop is prone to medical hallucinations and cannot handle privacy-sensitive moments.

Kith&Kin requires an **agentic system** because it must dynamically route and act based on conversational state:
* If the pharmacist speaks routine instructions, the system simply translates them.
* If a GP or pharmacy term implies medical risk (e.g., drug names, dosage, or allergies), the agent must warm the patient's medical profile into context, request a drug-conflict check, and present explicit confirmation options.
* If the pharmacist asks for sensitive data (credit cards, passport numbers, Medicare, or home address), the agent must immediately intercept and flag a privacy block.
* If multiple medication options are presented, the agent must organize only the pharmacist-stated facts (price, stated use, warnings) into a neutral comparison table without ranking or recommending.

These context-aware actions, RAG retrieval tools, safety checkstops, and UI-state synchronization require stateful agentic orchestration rather than a single LLM API call.

---

## 🏗️ Architecture: Audio-Visual Split & Single WS Session

![Kith&Kin architecture](architecture_diagram.svg)

Kith&Kin is implemented using a **React frontend**, a **FastAPI backend**, a single bidirectional **WebSocket runtime**, and **Google Gemini adapters** connected to an ADK agent orchestration layer and SQLite persistence.

The core of the system is a **Single Live API session** that handles three channels off the WebSocket: audio streams, JSON card payloads, and transcription text. This architecture cleanly splits the patient's interaction into two tracks:

### 1. The Visual Caption Track (Faithful, Hallucination-Free)
* **Text Translation Bypass:** To keep translations 100% faithful and free from agent fabrications, the pharmacist's raw English audio transcription (`input_transcription` from the Live API) is passed to a lightweight **Gemini Flash** text-translation model. Kith&Kin's voice agent is strictly forbidden from editing this translation text.
* **Two-Layer Subtitle UI:**
  - **Top layer:** Live English transcript (rendered in a small, grey, fading font to indicate system activity).
  - **Bottom layer:** Stable, large, high-contrast Chinese translation (rendered in an **append-only** fashion to prevent UI flicker and ease readability for elderly eyes).

### 2. The Audio-Card Track (Agent-Powered)
* **Parallel Orchestration:** While the visual translation track runs, the backend parallelizes the **Router** and **Guardian** agents to process the turn.
* **Half-Duplex Audio & Echo Muting:** To prevent acoustic feedback loops where KK's English TTS output is picked up by the parent's microphone and re-translated, the backend automatically **mutes the client's microphone during TTS playback** (`audio.muted` -> `audio.speaking` -> stream PCM frames -> restore listening).

---

## 🎓 Three Key Course Concepts

### 1. ADK Multi-Agent Orchestration (Parallel Safety)
Kith&Kin implements a parallel safety gate architecture using the Google Agent Development Kit (ADK):
* **Router Agent:** Classifies each conversational turn into distinct routes (`passive_translation`, `pharmacy_risk`, `privacy_risk`, `response_needed`, etc.).
* **Guardian Agent:** Runs in **parallel** on every single turn as a safety backstop. It scans for prompt injection, PII requests, and unsafe medical advice. If the Router attempts to pass a turn to the Companion, but the Guardian flags a safety violation, the execution path is halted, and a safety block is pushed.
* **Companion Agent:** Handles RAG queries and tool calls for allowed turns.
  - **ASR Drug-Name Sound-Alike Matching:** To handle garbled drug names in voice transcripts (e.g., "Lisinopril" transcribed as "listen to pro"), the Companion performs phonetic and semantic mapping against the pre-loaded patient profile. If a conflict is found, it generates a confirmation card: `[ Confirm with pharmacist: did you mean my BP med Lisinopril? ]`.

### 2. MCP-Style Tools & Latency Mitigation
The Companion agent interacts with the SQLite database via structured, permissioned tool boundaries:
* `memory_search(query, tags)`: Searches patient profile, allergies, and visit records.
* `check_drug_interaction(new_drug, current_meds)`: Queries a local SQLite-backed knowledge base for conflict warnings.
* `memory_write(key, value)` / `notify_family(summary)`: Gated persistence/notification tools.

**Latency Strategy for Face-to-Face Conversation:**
* **Pre-fetch:** On session start, the backend silently runs `memory_search("profile")` to warm the parent's meds and allergies into the context window, eliminating database round-trips during critical turns.
* **Lazy-load with Vocal Fillers:** Drug-conflict checking is lazy-loaded only when a drug entity is detected. To cover the database round-trip time and keep the face-to-face rhythm natural, the system plays a short TTS filler ("Let me check that for you...") to mask the latency.

### 3. Human-in-the-Loop Gating & PII Interception
* **Explicit Consent Tickets:** Proposing a card has zero side effects. The backend generates a temporary ticket for the proposed card. The client must select and explicitly click "Confirm & Speak" (`card.confirm`), sending a token back to the backend. The backend validates this token before starting the TTS synthesis stream or updating the SQLite memory.
* **PII Interception:** The Guardian agent inspects all pharmacist prompts. If the pharmacist asks for credit card details, passports, Medicare, or home addresses, the Guardian intercepts the turn and forces a privacy alert card: `[ Privacy Request: KK blocked sharing this info. Tap to decline ]`.

---

## 🛍️ Product Experience & Neutrality

* **Elderly-Friendly Workspace:** The UI features oversized high-contrast buttons, a large caption area, and a simplified layout.
* **Neutral Product Comparison:** For product queries (e.g., comparing Panadol and Nurofen), Kith&Kin does not recommend or rank medicines. It parses and presents only pharmacist-stated facts (prices, ingredients, cautions) in a tabular format. The pharmacist remains the absolute medical authority.
* **Adult-Child Feed:** Post-visit summaries and family notifications are structured and require confirmation before write/dispatch, keeping children informed without sacrificing parental autonomy.

---

## 🧪 Rigorous Evaluation

The repository contains **24 executable evaluation cases** in `evals/cases.json`, testing:
1. **Safety boundaries:** Redacting PII, blocking credit card requests, and intercepting prompt injections.
2. **Contextual retrieval:** Warming profiles, RAG extraction, and phonetic drug sound-alike matching.
3. **Idempotency:** Replaying card confirmations and validating token usage.
4. **E2E Integration:** Playwright E2E browser tests verify the entire pharmacy counter flow—from initial identity cards to product options tables, checkout/payment selections (card/cash), and final summary generation.

The eval runner verifies not just LLM answers, but the exact event sequence and tool execution traces, ensuring complete system safety.

---

## 🚀 Project Journey & Handoff

The project transitioned from a concept into a robust, contract-driven implementation. By building runtime contracts for events, card tokens, and tools, we aligned the FastAPI backend, React frontend, and ADK orchestration layer. 

A primary takeaway was that building reliable AI agents is not about writing more LLM code; it is about designing a reliable state machine. In Kith&Kin, every visible UI state maps to a verifiable backend event, and safety is enforced deterministically at the contract boundary.
