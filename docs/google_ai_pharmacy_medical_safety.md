# Google AI Pharmacy Medical Safety Notes

Last reviewed: 2026-06-29

This document captures the Google AI / Gemini constraints that matter for Kith&Kin's pharmacy-counter workflow. It is a working reference for prompt design, response-card generation, translation behavior, and later runtime changes.

Kith&Kin's intended role is a language and consent bridge between an elderly Chinese-speaking user and a licensed pharmacist. It must not become the medical decision-maker.

## Official Google Sources

- [Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms), effective 2026-03-23.
- [Google Generative AI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy), last modified 2024-12-17.
- [Gemini API Safety Settings](https://ai.google.dev/gemini-api/docs/safety-settings), last updated 2026-06-01.
- [Gemini API Safety and Factuality Guidance](https://ai.google.dev/gemini-api/docs/safety-guidance), last updated 2026-06-05.

## Hard Boundaries From Google Policy

Google's Gemini API terms prohibit using the services in clinical practice, to provide medical advice, or in a way that requires medical device regulatory clearance or approval. For Kith&Kin, this means the AI cannot answer whether a medicine is safe, recommend using a medicine, recommend avoiding a medicine, choose a dose, change treatment, or make a clinical judgment.

Google's prohibited-use policy also restricts automated decisions that materially affect people in high-risk domains such as healthcare unless there is human supervision. In this project, the licensed pharmacist is the supervising human for medication questions. The parent must also explicitly confirm before KK speaks any health-related information.

Google also prohibits bypassing safety protections. Kith&Kin prompts must not ask Gemini to ignore safety rules, suppress warnings, or behave as if it is a clinician. If Google blocks a prompt or response, the product should fail closed and return to translation or a safe fallback.

Google warns developers that LLM output can be inaccurate or unexpected, and that application owners are responsible for understanding user harms, testing safety, filtering unsafe inputs/outputs, and monitoring issues. In a pharmacy setting, medication misunderstanding is a high-severity harm, so prompts must be narrower than a normal chatbot prompt.

## Pharmacy-Scenario Interpretation

The safe product shape is:

- Translate the pharmacist's words faithfully.
- Help the elderly user ask the pharmacist a clear question.
- Use known profile facts only as context for a pharmacist-confirmation question.
- Require parent confirmation before speaking or sharing health facts.
- Treat the pharmacist, not Gemini, as the authority for medication suitability, interactions, dose, side effects, and alternatives.

The unsafe product shape is:

- AI decides whether the user should take, stop, avoid, buy, substitute, or change a medication.
- AI says a drug is safe, unsafe, appropriate, inappropriate, compatible, or incompatible as its own conclusion.
- AI answers dosage instructions from model knowledge.
- AI diagnoses symptoms or recommends treatment.
- AI makes medication decisions automatically from memory, drug data, or prior visits.
- AI sends sensitive health, identity, payment, address, or family information without explicit confirmation and backend approval.

## Prompt Rules For Companion Cards

Response-card prompts must instruct the model to generate direct utterances that the parent can approve and KK can speak to the pharmacist. Cards are not instructions about what the app should do; they are the actual words to be spoken.

Required card style:

- First-person or direct-to-pharmacist wording.
- Short, concrete, and easy to speak aloud.
- Ask the pharmacist to check, confirm, explain, repeat, slow down, or write down information.
- Avoid third-person meta wording such as "Ask pharmacist to..." or "Please have the pharmacist..."
- Avoid model-addressed medical questions such as "Should I take..." because Gemini may interpret them as asking the model for medical advice.
- Avoid final medical claims. Use "could you please check" rather than "is this safe" when possible.

Allowed examples:

- "Could you please write down the medicine name and directions for me?"
- "Could you please check this medicine against my current medication list?"
- "Could you please explain the dose again slowly?"
- "Could you please confirm whether I should ask my GP before using this?"
- "I have a recorded penicillin allergy. Could you please check whether this medicine is suitable for someone with that allergy?"

Disallowed examples:

- "Should I take ibuprofen?"
- "Can I take this with my blood pressure medicine?"
- "This medicine is safe for me."
- "I should stop my current medicine."
- "Give me a lower dose."
- "Ask pharmacist to confirm my allergies."
- "Tell the user this drug does not conflict."

## Translation Rules

Faithful translation is allowed and necessary, but it must remain translation only:

- Translate what the pharmacist said without adding advice, reassurance, warnings, or recommendations.
- Preserve uncertainty, questions, and pharmacist instructions as spoken.
- Do not add model-generated medical context to the translation panel.
- If translation is blocked or unavailable, show the original English and a neutral fallback rather than guessing.

## Gemini Live / TTS Risk Note

Current architecture sends confirmed English card text into Gemini Live as text for audio output. Because the text is sent to a generative model, a card such as "Should I take Coenzyme Q10?" can look like a medical-advice prompt to Google safety systems even if the application intends it as text-to-speech.

Prompt changes should therefore avoid medicine-decision questions that are phrased as if Gemini is being asked to answer. Prefer relay-safe utterances addressed to the pharmacist, and consider a later runtime change that separates TTS from generative answering.

## Data Handling Notes

The Gemini API terms distinguish unpaid and paid services. For unpaid services, Google may use submitted content and responses to improve products and warns not to submit sensitive, confidential, or personal information. For paid services, Google says prompts and responses are not used to improve products, but logs may be retained for limited safety and security purposes.

For Kith&Kin:

- Minimize patient data sent to Google.
- Do not send full medical history when a shorter confirmed fact is enough.
- Avoid payment, identity, address, Medicare, passport, and similar data in model prompts.
- Keep memory retrieval and drug-check reasoning backend-owned where possible.

## Practical Acceptance Criteria For Future Prompt Edits

Before accepting a Companion prompt/card change:

- Every generated card must be speakable directly to a pharmacist.
- No card may tell the parent to take, avoid, stop, substitute, or change a medicine.
- No card may claim a medicine is safe, unsafe, compatible, or incompatible.
- Interaction/allergy/dose questions must ask the pharmacist to check or explain.
- Known patient facts may be stated only if they come from authorised memory and still lead to pharmacist confirmation.
- The model must return card drafts only; backend still owns IDs, approval, expiry, confirmation, and action execution.
- If Google safety blocks generation or speech, the UX must continue faithful translation and show a safe fallback.
