# Pharmacy Counter E2E Product Goal

Last updated: 2026-06-29

This document defines the target end-to-end pharmacy-counter experience for Kith&Kin. It is a product goal, not an implementation plan. Prompt, UX, runtime, and evaluation work should use this flow together with [Google AI Pharmacy Medical Safety Notes](./google_ai_pharmacy_medical_safety.md).

## Product Goal

Kith&Kin helps an elderly Chinese-speaking parent communicate with a licensed pharmacist at a pharmacy counter. The product should make the parent feel able to explain what they need, understand the pharmacist's options, safely disclose relevant health facts after confirmation, and complete a purchase decision.

Kith&Kin is a translation and consent bridge. It does not diagnose, prescribe, recommend a medicine, compare medicines from its own medical judgment, or decide which product the parent should buy.

## Primary User Story

An elderly parent visits a pharmacy alone. They may not know the English name of a medicine, may remember a medicine used previously overseas, and may need help asking for a similar local option. They also need help answering safety questions about allergies, current medications, and known conditions.

The pharmacist remains the medical authority. Kith&Kin listens, translates, retrieves authorised profile context when needed, and creates parent-confirmed response cards that help the parent ask the pharmacist clear questions.

## Target E2E Flow

1. The parent arrives at the pharmacy counter and starts a session.
2. The pharmacist and parent may have short small talk.
3. Kith&Kin faithfully translates the small talk without generating medication cards.
4. The pharmacist asks what they can help with.
5. The parent says they want a specific medicine, a medicine they used before, or a similar local medicine.
6. Kith&Kin translates the parent's request to the pharmacist. It does not recommend a product.
7. The pharmacist asks safety questions such as allergies, current medications, chronic conditions, age-related concerns, pregnancy status, or recent symptoms.
8. Kith&Kin checks authorised database/profile context for relevant facts.
9. Kith&Kin shows confirmation cards before sharing health facts. Example: "I have a recorded penicillin allergy. Could you please check whether this medicine is suitable for someone with that allergy?"
10. The parent confirms one card.
11. Kith&Kin speaks the confirmed card to the pharmacist.
12. The pharmacist proposes up to three product options and explains use cases, differences, cautions, and prices.
13. Kith&Kin faithfully translates the pharmacist's explanation.
14. Kith&Kin may organize only pharmacist-provided information into a neutral comparison view: product name, price, pharmacist-stated purpose, pharmacist-stated directions, and pharmacist-stated cautions.
15. Kith&Kin generates safe follow-up cards that ask the pharmacist to clarify similarity, suitability, directions, and warnings.
16. The parent confirms one or more follow-up questions.
17. The pharmacist answers.
18. Kith&Kin translates the answer and updates the neutral comparison with only pharmacist-stated facts.
19. The parent chooses what to buy based on the pharmacist's explanation and their own preference.
20. Kith&Kin translates the purchase intent.
21. The pharmacist gives final price/payment instructions.
22. Kith&Kin translates the price and payment instructions.
23. The parent confirms purchase and the conversation ends.
24. Kith&Kin generates a visit summary: medicine names mentioned, pharmacist-stated advice, unresolved questions, and family follow-up if confirmed.

## What Kith&Kin May Do

- Translate pharmacist speech faithfully into Chinese.
- Translate parent speech or confirmed card text into English.
- Ask the pharmacist to repeat, slow down, write down names, or explain directions.
- Retrieve authorised profile facts such as known allergies, current medications, and prior pharmacy notes.
- Ask the parent to confirm before sharing health facts.
- Help the parent ask the pharmacist to compare options.
- Structure pharmacist-provided information into a neutral table or summary.
- Save a visit summary only after confirmation.
- Notify family only after confirmation.

## What Kith&Kin Must Not Do

- Recommend which medicine to buy.
- Say which product is safest, best, most suitable, or most similar based on AI judgment.
- Generate its own pros and cons for medicines.
- Decide whether a medicine interacts with current medication.
- Say a product is compatible or incompatible.
- Tell the parent to take, avoid, stop, substitute, or change a medicine.
- Provide dose instructions from model knowledge.
- Invent or infer missing allergies, medications, diagnoses, or prior medicine equivalence.
- Share sensitive health, identity, payment, address, or family information without explicit confirmation.

## Safe Handling Of Three Product Options

When the pharmacist gives three choices, Kith&Kin must treat the pharmacist's words as the source of truth.

Allowed:

- "The pharmacist said Option A is for X, Option B is for Y, and Option C costs Z."
- "Could you please explain which option is closest to the medicine I used before?"
- "Could you please check these options against my current medication list?"
- "Could you please write down the one you recommend and how to use it?"

Not allowed:

- "Option A is best for you."
- "Option B is most similar to your medicine from China."
- "Option C has fewer side effects."
- "You should buy Option A."
- "This one is safe with your blood pressure medicine."

If similarity to a prior overseas medicine matters, Kith&Kin should ask the pharmacist to verify active ingredients or intended use. It should not infer equivalence from names, memory, or model knowledge.

## Response Card Product Requirements

Cards must be direct utterances that can be spoken to the pharmacist after parent confirmation.

Good card shape:

- "Could you please check this medicine against my current medication list?"
- "Could you please explain the difference between these three options?"
- "Could you please write down the medicine name and directions?"
- "I have a recorded allergy. Could you please check whether this option is suitable?"
- "Could you please confirm which option is closest to the medicine I used before?"

Bad card shape:

- "Ask pharmacist to confirm my allergies."
- "Which one should I take?"
- "This medicine is safe for me."
- "I should buy this one."
- "Tell me the pros and cons of these medicines."

## Success Criteria

- The parent can complete the pharmacy interaction without typing English.
- The pharmacist can understand the parent's request and confirmed health context.
- The parent sees large, faithful Chinese translations of pharmacist speech.
- Every outward health disclosure requires explicit parent confirmation.
- Product-option comparison contains only pharmacist-stated facts.
- Any medical judgment is asked of the pharmacist, not answered by Kith&Kin.
- The final visit summary separates pharmacist-stated advice from unresolved follow-up questions.

## Open Product Questions

- Should Kith&Kin display a neutral comparison table during the visit, or only after the pharmacist finishes explaining all options?
- Should confirmed health facts be spoken one at a time, or batched after the parent approves a short checklist?
- Should purchase confirmation use a normal translation path or a dedicated purchase-intent card?
- Should the product support photos of medicine boxes from the parent, or keep the first version voice-only?
