"""
Kith&Kin — Drug Knowledge Base
===============================
Australian pharmacy context, built from:
- PBS Top 10 Prescribed Medications 2024–25 (Australian Prescriber)
- MSD Manual Professional: Drug Categories of Concern in Older Adults
- NPS MedicineWise / Therapeutic Guidelines (Australia)
- Better Health Channel (Victoria)

Design principle for Kaggle demo:
  3–5 curated scenarios with genuine interaction data,
  NOT a fake 5-line dict. Each entry cites a real mechanism.
  In production, this would connect to a standard drug database (e.g. AMH, DailyMed).

Usage:
  from drug_knowledge import drug_lookup, check_interaction
"""


# ============================================================
# SECTION 1: Drug Profiles (generic + Australian brand names)
# ============================================================

DRUG_PROFILES = {
    # --- Cardiovascular: Hypertension ---
    "perindopril": {
        "class": "ACE Inhibitor",
        "brands_au": ["Coversyl", "Perindo"],
        "indications": ["Hypertension", "Heart failure", "Post-MI"],
        "common_in_elderly": True,
        "warnings": [
            "May cause persistent dry cough",
            "Risk of hyperkalemia with potassium supplements or salt substitutes",
            "Can cause acute kidney injury if dehydrated",
        ],
    },
    "lisinopril": {
        "class": "ACE Inhibitor",
        "brands_au": ["Zestril", "Prinivil", "Lisinopril Sandoz"],
        "indications": ["Hypertension", "Heart failure", "Post-MI"],
        "common_in_elderly": True,
        "warnings": [
            "May cause persistent dry cough",
            "Risk of hyperkalemia with potassium supplements or salt substitutes",
            "Can cause acute kidney injury if dehydrated",
        ],
    },
    "amlodipine": {
        "class": "Calcium Channel Blocker (Dihydropyridine)",
        "brands_au": ["Norvasc", "Perivasc", "Amlodipine Sandoz"],
        "indications": ["Hypertension", "Angina"],
        "common_in_elderly": True,
        "warnings": [
            "May cause ankle swelling (peripheral oedema)",
            "Grapefruit juice increases blood levels — avoid",
        ],
    },
    "candesartan": {
        "class": "Angiotensin II Receptor Blocker (ARB)",
        "brands_au": ["Atacand"],
        "indications": ["Hypertension", "Heart failure"],
        "common_in_elderly": True,
        "warnings": [
            "Similar kidney risks to ACE inhibitors when dehydrated",
            "Generally better tolerated than ACE inhibitors (no cough)",
        ],
    },
    "ramipril": {
        "class": "ACE Inhibitor",
        "brands_au": ["Tritace", "Ramipril Sandoz"],
        "indications": ["Hypertension", "Heart failure", "Post-MI", "Diabetic nephropathy"],
        "common_in_elderly": True,
        "warnings": [
            "Same class warnings as perindopril",
        ],
    },
    "telmisartan": {
        "class": "Angiotensin II Receptor Blocker (ARB)",
        "brands_au": ["Micardis", "Pritor"],
        "indications": ["Hypertension", "Cardiovascular risk reduction"],
        "common_in_elderly": True,
    },
    # --- Cardiovascular: Cholesterol ---
    "rosuvastatin": {
        "class": "Statin (HMG-CoA Reductase Inhibitor)",
        "brands_au": ["Crestor", "Rosuvastatin Sandoz"],
        "indications": ["Hypercholesterolaemia", "Cardiovascular risk reduction"],
        "common_in_elderly": True,
        "warnings": [
            "Risk of muscle pain / rhabdomyolysis (rare but serious)",
            "Grapefruit juice may increase blood levels — limit intake",
            "Dose may need reduction with severe kidney impairment",
        ],
    },
    "atorvastatin": {
        "class": "Statin (HMG-CoA Reductase Inhibitor)",
        "brands_au": ["Lipitor", "Atorvastatin Sandoz"],
        "indications": ["Hypercholesterolaemia", "Cardiovascular risk reduction"],
        "common_in_elderly": True,
        "warnings": [
            "Same class warnings as rosuvastatin",
            "Metabolised by CYP3A4 — many drug interactions possible",
        ],
    },
    # --- Diabetes ---
    "metformin": {
        "class": "Biguanide",
        "brands_au": ["Diabex", "Diaformin", "Glucophage"],
        "indications": ["Type 2 Diabetes Mellitus"],
        "common_in_elderly": True,
        "warnings": [
            "Risk of lactic acidosis with severe kidney impairment (eGFR <30)",
            "Usually withheld before contrast dye procedures or surgery",
            "May cause gastrointestinal upset (diarrhoea, nausea) — slow titration helps",
        ],
    },
    # --- Anticoagulation ---
    "warfarin": {
        "class": "Vitamin K Antagonist (Anticoagulant)",
        "brands_au": ["Coumadin", "Marevan"],
        "indications": ["Atrial fibrillation", "DVT/PE treatment", "Mechanical heart valve"],
        "common_in_elderly": True,
        "warnings": [
            "NARROW THERAPEUTIC INDEX — requires regular INR monitoring",
            "Numerous drug, food, and supplement interactions",
            "NSAIDs roughly DOUBLE bleeding risk when combined",
            "Alcohol and cranberry juice can affect INR",
            "Elderly more sensitive to anticoagulant effect",
        ],
    },
    "apixaban": {
        "class": "Direct Oral Anticoagulant (Factor Xa Inhibitor)",
        "brands_au": ["Eliquis"],
        "indications": ["Atrial fibrillation (non-valvular)", "DVT/PE treatment and prevention"],
        "common_in_elderly": True,
        "warnings": [
            "Fewer interactions than warfarin, but still increased bleeding risk with NSAIDs and antiplatelets",
            "Dose reduction needed with renal impairment",
        ],
    },
    "rivaroxaban": {
        "class": "Direct Oral Anticoagulant (Factor Xa Inhibitor)",
        "brands_au": ["Xarelto"],
        "indications": ["Atrial fibrillation", "DVT/PE"],
        "common_in_elderly": True,
        "warnings": [
            "Similar profile to apixaban",
        ],
    },
    # --- Mental Health ---
    "sertraline": {
        "class": "SSRI Antidepressant",
        "brands_au": ["Zoloft", "Sertraline Sandoz"],
        "indications": ["Major depression", "Anxiety disorders", "PTSD", "OCD"],
        "common_in_elderly": True,
        "warnings": [
            "Increased bleeding risk with NSAIDs or warfarin (SSRIs inhibit platelet serotonin uptake)",
            "Risk of hyponatraemia in elderly (low sodium)",
            "Withdrawal syndrome if stopped abruptly",
        ],
    },
    "escitalopram": {
        "class": "SSRI Antidepressant",
        "brands_au": ["Lexapro", "Escitalopram Sandoz"],
        "indications": ["Major depression", "Generalised anxiety disorder"],
        "common_in_elderly": True,
        "warnings": [
            "Same class warnings as sertraline",
        ],
    },
    # --- Gastrointestinal ---
    "pantoprazole": {
        "class": "Proton Pump Inhibitor (PPI)",
        "brands_au": ["Somac", "Pantoprazole Sandoz"],
        "indications": ["GORD / reflux", "Peptic ulcer", "Prevention of NSAID-induced ulcers"],
        "common_in_elderly": True,
        "warnings": [
            "Long-term use associated with increased fracture risk, B12 deficiency, C. difficile infection",
            "Can reduce absorption of some drugs requiring stomach acid (e.g. iron, some antifungals)",
        ],
    },
    "esomeprazole": {
        "class": "Proton Pump Inhibitor (PPI)",
        "brands_au": ["Nexium", "Esomeprazole Sandoz"],
        "indications": ["GORD / reflux", "Peptic ulcer", "H. pylori eradication (triple therapy)"],
        "common_in_elderly": True,
    },
}

# ============================================================
# SECTION 2: Common Australian OTC Medications
# ============================================================

OTC_DRUGS = {
    "paracetamol": {
        "brands_au": ["Panadol", "Panamax", "Herron Paracetamol"],
        "class": "Analgesic / Antipyretic",
        "typical_use": "Mild to moderate pain, fever",
        "elderly_note": "Generally safe at recommended doses (max 4g/day). Preferred first-line analgesic for elderly.",
    },
    "ibuprofen": {
        "brands_au": ["Nurofen", "Advil", "Brufen"],
        "class": "NSAID",
        "typical_use": "Pain, inflammation, fever",
        "elderly_note": "NSAID — use with caution in elderly. See NSAID interaction profile below.",
    },
    "diclofenac": {
        "brands_au": ["Voltaren", "Voltaren Rapid"],
        "class": "NSAID",
        "typical_use": "Pain, inflammation (including arthritis)",
        "elderly_note": "NSAID — same cautions as ibuprofen. Topical gel form (Voltaren Gel) has lower systemic risk.",
    },
    "naproxen": {
        "brands_au": ["Naprogesic", "Naprosyn"],
        "class": "NSAID",
        "typical_use": "Pain, inflammation, period pain",
        "elderly_note": "NSAID — same cautions. May have slightly lower cardiovascular risk than some other NSAIDs.",
    },
    "aspirin_low_dose": {
        "brands_au": ["Cartia", "Astrix", "Cardiprin"],
        "class": "Antiplatelet (low dose 100mg)",
        "typical_use": "Cardiovascular prevention (prescribed, not truly OTC)",
        "elderly_note": "Often prescribed. When combined with NSAIDs or warfarin, bleeding risk increases significantly.",
    },
    "pseudoephedrine": {
        "brands_au": ["Sudafed", "Codral Original (behind counter)"],
        "class": "Decongestant (sympathomimetic)",
        "typical_use": "Nasal congestion, sinus",
        "elderly_note": "Can raise blood pressure — caution with hypertension. May counteract BP medications.",
    },
    "phenylephrine": {
        "brands_au": ["Sudafed PE", "Many cold & flu combo products"],
        "class": "Decongestant (sympathomimetic)",
        "typical_use": "Nasal congestion",
        "elderly_note": "Also a decongestant. Caution with hypertension.",
    },
}


# ============================================================
# SECTION 2b: Non-Drug Substances (food, supplements, herbal)
# These can also interact with medications and must be checkable.
# ============================================================

SUBSTANCES = {
    "grapefruit": {
        "class": "CYP3A4 Inhibitor (Dietary)",
        "sources": ["grapefruit juice", "Seville oranges", "pomelo"],
        "elderly_note": (
            "Grapefruit inhibits CYP3A4 enzyme in the gut wall, increasing blood "
            "levels of many drugs metabolised by this pathway. The effect can last "
            "24+ hours after consumption. Particularly significant for atorvastatin, "
            "simvastatin, some calcium channel blockers, and certain sedatives."
        ),
    },
    "alcohol": {
        "class": "CNS Depressant / Hepatotoxin (Dietary)",
        "sources": ["beer", "wine", "spirits"],
        "elderly_note": (
            "Alcohol interacts with many medications: increases bleeding risk with "
            "warfarin, increases lactic acidosis risk with metformin, potentiates "
            "sedation with benzodiazepines/opioids, and can cause liver damage when "
            "combined with paracetamol at high doses."
        ),
    },
    "cranberry": {
        "class": "CYP2C9 / OATP Inhibitor (Dietary)",
        "sources": ["cranberry juice", "cranberry supplements"],
        "elderly_note": (
            "Cranberry juice may potentiate warfarin's anticoagulant effect, "
            "potentially increasing INR. Mechanisms include CYP2C9 inhibition and "
            "OATP transporter interaction. Occasional small amounts are likely safe, "
            "but regular or large quantities warrant INR monitoring."
        ),
    },
    "st_johns_wort": {
        "class": "CYP3A4 / P-glycoprotein Inducer (Herbal)",
        "sources": ["St John's Wort", "Hypericum perforatum"],
        "elderly_note": (
            "St John's Wort strongly induces CYP3A4 and P-glycoprotein, reducing "
            "blood levels of warfarin, statins, calcium channel blockers, oral "
            "contraceptives, and many other drugs. Can also cause serotonin syndrome "
            "when combined with SSRIs. Advise against self-medication with this herb."
        ),
    },
}

# ============================================================
# SECTION 3: Drug Interaction Matrix
# Key: (drug_a_class, drug_b_class) → risk_level, description
# ============================================================


class Interaction:
    def __init__(self, risk: str, mechanism: str, recommendation: str, source: str):
        self.risk = risk  # "HIGH", "MODERATE", "LOW", "MONITOR"
        self.mechanism = mechanism
        self.recommendation = recommendation
        self.source = source


# Build class maps for matching
def _build_class_map():
    m = {}
    for name, info in DRUG_PROFILES.items():
        cls = info["class"]
        if cls not in m:
            m[cls] = []
        m[cls].append(name)
        # Also map brand names
        for brand in info.get("brands_au", []):
            m[brand.lower()] = m.get(cls, []) + [name]
    for name, info in OTC_DRUGS.items():
        cls = info["class"]
        if cls not in m:
            m[cls] = []
        m[cls].append(name)
    return m


# Interaction rules — class-level matching with specific exceptions
INTERACTIONS = [
    # ===== NSAIDs vs Cardiovascular =====
    # NSAIDs + ACE Inhibitors / ARBs: reduced BP control, kidney risk
    Interaction(
        risk="MODERATE",
        mechanism=(
            "NSAIDs reduce kidney prostaglandin production, which can blunt the "
            "blood-pressure-lowering effect of ACE inhibitors and ARBs. "
            "Combined use also increases the risk of acute kidney injury, "
            "especially in elderly or dehydrated patients."
        ),
        recommendation=(
            "If NSAID use is unavoidable, use the lowest effective dose for the "
            "shortest possible duration. Monitor blood pressure and kidney function "
            "(serum creatinine) more frequently. Consider paracetamol as a safer "
            "alternative for simple pain relief."
        ),
        source="MSD Manual: Drug Categories of Concern in Older Adults; NPS MedicineWise",
    ),
    # NSAIDs + Diuretics
    Interaction(
        risk="MODERATE",
        mechanism=(
            "NSAIDs can reduce the effectiveness of diuretics (fluid tablets) and "
            "increase the risk of kidney impairment, particularly in elderly patients."
        ),
        recommendation=(
            "Monitor for signs of fluid retention (swollen ankles, weight gain, "
            "shortness of breath). Check kidney function if using for more than a few days."
        ),
        source="Australian Medicines Handbook; MSD Manual",
    ),
    # NSAIDs + Warfarin — HIGH risk
    Interaction(
        risk="HIGH",
        mechanism=(
            "NSAIDs roughly DOUBLE the risk of gastrointestinal bleeding when "
            "combined with warfarin (OR ≈1.98). This occurs through: (1) direct "
            "injury to stomach lining, (2) antiplatelet effect of NSAIDs, and "
            "(3) displacement of warfarin from plasma proteins, increasing free "
            "warfarin concentration."
        ),
        recommendation=(
            "This combination should be AVOIDED if possible. Use paracetamol "
            "instead. If NSAID is absolutely necessary, a proton pump inhibitor "
            "(e.g. pantoprazole) should be co-prescribed for stomach protection, "
            "and INR must be monitored more frequently. The same warning applies "
            "to apixaban (Eliquis) and rivaroxaban (Xarelto)."
        ),
        source="MSD Manual; Thrombosis Research (meta-analysis); NPS MedicineWise",
    ),
    # NSAIDs + Aspirin (antiplatelet)
    Interaction(
        risk="HIGH",
        mechanism=(
            "Combining NSAIDs with low-dose aspirin (Cartia/Astrix) significantly "
            "increases gastrointestinal bleeding risk through additive effects on "
            "stomach mucosa and platelet function. Ibuprofen may also interfere "
            "with aspirin's cardioprotective antiplatelet effect."
        ),
        recommendation=(
            "Avoid regular combined use. If both are needed, space ibuprofen at "
            "least 2 hours after aspirin, and consider stomach protection (PPI)."
        ),
        source="NPS MedicineWise; TGA (Australia)",
    ),
    # NSAIDs + SSRIs (sertraline, escitalopram)
    Interaction(
        risk="MODERATE",
        mechanism=(
            "SSRIs impair platelet function by depleting platelet serotonin. "
            "When combined with NSAIDs, this produces an additive antiplatelet "
            "effect, roughly doubling GI bleeding risk. This is particularly "
            "relevant for elderly patients who are on both antidepressants "
            "and occasional OTC pain relief."
        ),
        recommendation=(
            "Consider paracetamol for pain. If NSAID + SSRI combination is "
            "needed, co-prescribe a PPI for stomach protection. Advise patient "
            "to watch for signs of GI bleeding (black stools, abdominal pain)."
        ),
        source="MSD Manual; Australian Prescriber",
    ),
    # ===== Statins vs interactions =====
    # Statins + Grapefruit
    Interaction(
        risk="LOW",
        mechanism=(
            "Grapefruit (and Seville oranges) inhibit CYP3A4 enzyme in the gut, "
            "which metabolises atorvastatin and simvastatin. This can increase "
            "blood levels and the risk of muscle side effects. Rosuvastatin is "
            "less affected (minimal CYP3A4 metabolism)."
        ),
        recommendation=(
            "Limit grapefruit juice to small occasional amounts, or avoid entirely "
            "with atorvastatin. Rosuvastatin is a safer choice for grapefruit lovers."
        ),
        source="NPS MedicineWise; Australian Prescriber",
    ),
    # Statins + Macrolide antibiotics (e.g. clarithromycin, erythromycin)
    Interaction(
        risk="MODERATE",
        mechanism=(
            "Macrolide antibiotics strongly inhibit CYP3A4, increasing statin "
            "(especially atorvastatin/simvastatin) levels 3-10×. Risk of "
            "rhabdomyolysis (muscle breakdown)."
        ),
        recommendation=(
            "Temporarily withhold atorvastatin/simvastatin during short-course "
            "macrolide antibiotics. Rosuvastatin is less affected and may be "
            "safer. Tell the pharmacist if you are on a statin before taking "
            "any new antibiotic."
        ),
        source="Australian Medicines Handbook; TGA",
    ),
    # ===== Metformin interactions =====
    # Metformin + Contrast Dye / Surgery
    Interaction(
        risk="MODERATE",
        mechanism=(
            "Iodinated contrast dye (used in CT scans, angiograms) can temporarily "
            "reduce kidney function. If metformin is continued, the reduced kidney "
            "clearance can lead to metformin accumulation and lactic acidosis — "
            "a rare but serious complication."
        ),
        recommendation=(
            "Metformin should usually be withheld 48 hours before and 48 hours "
            "after contrast procedures. Check with the doctor or radiologist. "
            "Also temporarily withheld before major surgery."
        ),
        source="RANZCR Guidelines (Australia); MSD Manual",
    ),
    # Metformin + Alcohol
    Interaction(
        risk="LOW",
        mechanism=(
            "Excessive alcohol intake while on metformin can increase the risk "
            "of lactic acidosis, particularly if alcohol causes dehydration or "
            "liver stress."
        ),
        recommendation=(
            "Moderate alcohol is generally fine. Avoid binge drinking. "
            "If unwell and not eating/drinking normally, temporarily stop metformin "
            "and seek medical advice."
        ),
        source="Diabetes Australia; NPS MedicineWise",
    ),
    # ===== Decongestants vs Hypertension =====
    # Pseudoephedrine / Phenylephrine + BP meds
    Interaction(
        risk="MODERATE",
        mechanism=(
            "Pseudoephedrine and phenylephrine are sympathomimetics — they "
            "constrict blood vessels and can raise blood pressure. In patients "
            "taking antihypertensives (perindopril, amlodipine, candesartan, etc.), "
            "this can partially counteract the BP-lowering treatment."
        ),
        recommendation=(
            "Short-term use (1-3 days) at recommended doses is generally acceptable "
            "with monitoring. Avoid if blood pressure is poorly controlled. Consider "
            "saline nasal spray or steam inhalation as alternatives. Pharmacist-only "
            "pseudoephedrine products require consultation."
        ),
        source="NPS MedicineWise; TGA scheduling (Australia)",
    ),
    # ===== PPI interactions =====
    # PPIs + Clopidogrel
    Interaction(
        risk="MODERATE",
        mechanism=(
            "Some PPIs (especially omeprazole and esomeprazole) inhibit CYP2C19, "
            "the enzyme that activates clopidogrel. This may reduce clopidogrel's "
            "antiplatelet effect. Pantoprazole has the least interaction."
        ),
        recommendation=(
            "If a PPI is needed with clopidogrel, pantoprazole (Somac) is the "
            "preferred choice. Discuss with doctor or pharmacist."
        ),
        source="TGA (Australia); NPS MedicineWise",
    ),
]


# ============================================================
# SECTION 4: Lookup Functions
# ============================================================


def _normalise(name: str) -> str:
    """Normalise drug name for fuzzy matching: lowercase, strip."""
    return name.lower().strip().rstrip(".")


def drug_lookup(query: str) -> dict | None:
    """
    Look up a drug by generic name or Australian brand name.
    Returns profile dict or None.
    """
    q = _normalise(query)

    # Direct generic match
    if q in DRUG_PROFILES:
        return {"type": "prescription", "name": q, **DRUG_PROFILES[q]}

    # OTC match
    if q in OTC_DRUGS:
        return {"type": "otc", "name": q, **OTC_DRUGS[q]}

    # Brand name search (prescription)
    for generic, info in DRUG_PROFILES.items():
        for brand in info.get("brands_au", []):
            if _normalise(brand) == q:
                return {"type": "prescription", "name": generic, **info}

    # Brand name search (OTC)
    for generic, info in OTC_DRUGS.items():
        for brand in info.get("brands_au", []):
            if _normalise(brand) == q:
                return {"type": "otc", "name": generic, **info}

    return None


def substance_lookup(query: str) -> dict | None:
    """
    Look up a non-drug substance (food, herb, supplement) by name.
    Returns profile dict or None.
    """
    q = _normalise(query)
    if q in SUBSTANCES:
        return {"type": "substance", "name": q, **SUBSTANCES[q]}
    # Search sources
    for name, info in SUBSTANCES.items():
        for source in info.get("sources", []):
            if _normalise(source) == q:
                return {"type": "substance", "name": name, **info}
    return None


def _any_lookup(query: str) -> dict | None:
    """Unified lookup: try drug first, then substance."""
    result = drug_lookup(query)
    if result:
        return result
    return substance_lookup(query)


def check_interaction(entity_a: str, entity_b: str) -> dict | None:
    """
    Check for known interactions between two entities (drugs or substances).
    Accepts drug generic names, brand names, or substance names (e.g. 'grapefruit').
    Returns interaction dict with risk/mechanism/recommendation, or None.
    """
    profile_a = _any_lookup(entity_a)
    profile_b = _any_lookup(entity_b)

    if not profile_a or not profile_b:
        return None

    # Get the drug class for matching
    def get_class_label(profile, raw_name):
        return profile["class"]

    class_a = get_class_label(profile_a, entity_a)
    class_b = get_class_label(profile_b, entity_b)

    # Try specific drug-level matching first
    name_a = profile_a["name"]
    name_b = profile_b["name"]

    for interaction in INTERACTIONS:
        # We could implement more sophisticated class matching here,
        # but for the demo, a simplified approach: search the mechanism
        # and recommendation text for drug class keywords.
        # In production, use a proper drug interaction database (e.g. DDInter, OpenFDA).
        pass

    # Class-level matching via a simpler approach:
    for interaction in INTERACTIONS:
        mech_lower = interaction.mechanism.lower()
        rec_lower = interaction.recommendation.lower()

        # Build a simple relevance score based on drug class mentions
        relevant = False
        # Check if both drug classes appear in the interaction description
        for keyword_a in _class_keywords(class_a):
            for keyword_b in _class_keywords(class_b):
                if (keyword_a in mech_lower or keyword_a in rec_lower) and (
                    keyword_b in mech_lower or keyword_b in rec_lower
                ):
                    relevant = True
                    break
            if relevant:
                break

        if relevant:
            return {
                "risk": interaction.risk,
                "mechanism": interaction.mechanism,
                "recommendation": interaction.recommendation,
                "source": interaction.source,
                "drug_a": entity_a,
                "drug_b": entity_b,
            }

    # Fallback: if both drugs are known but no interaction found,
    # return a "no known interaction" note
    return None


def _class_keywords(drug_class: str) -> list:
    """Generate search keywords for a drug class."""
    keywords = [drug_class.lower()]
    # Add synonyms
    synonyms = {
        "ACE Inhibitor": ["ace inhibitor", "ace inhibitors", "perindopril", "ramipril"],
        "Angiotensin II Receptor Blocker (ARB)": [
            "arb",
            "angiotensin",
            "candesartan",
            "telmisartan",
            "irbesartan",
        ],
        "Calcium Channel Blocker (Dihydropyridine)": ["calcium channel blocker", "amlodipine"],
        "Statin (HMG-CoA Reductase Inhibitor)": [
            "statin",
            "statins",
            "atorvastatin",
            "rosuvastatin",
        ],
        "NSAID": ["nsaid", "nsaids", "anti-inflammatory", "ibuprofen", "diclofenac", "naproxen"],
        "Antiplatelet (low dose 100mg)": ["aspirin", "antiplatelet"],
        "Vitamin K Antagonist (Anticoagulant)": ["warfarin", "anticoagulant", "anticoagulants"],
        "Direct Oral Anticoagulant (Factor Xa Inhibitor)": [
            "anticoagulant",
            "anticoagulants",
            "apixaban",
            "rivaroxaban",
            "eliquis",
            "xarelto",
        ],
        "SSRI Antidepressant": [
            "ssri",
            "antidepressant",
            "sertraline",
            "escitalopram",
            "zoloft",
            "lexapro",
        ],
        "Biguanide": ["metformin", "diabetes"],
        "Proton Pump Inhibitor (PPI)": ["ppi", "pantoprazole", "esomeprazole", "omeprazole"],
        "Decongestant (sympathomimetic)": [
            "decongestant",
            "pseudoephedrine",
            "phenylephrine",
            "sudafed",
            "codral",
        ],
        # Substance classes
        "CYP3A4 Inhibitor (Dietary)": [
            "grapefruit",
            "grapefruit juice",
            "cyp3a4",
            "seville oranges",
        ],
        "CNS Depressant / Hepatotoxin (Dietary)": [
            "alcohol",
            "beer",
            "wine",
            "spirits",
            "ethanol",
            "lactic acidosis",
        ],
        "CYP2C9 / OATP Inhibitor (Dietary)": ["cranberry", "cranberry juice", "cyp2c9", "warfarin"],
        "CYP3A4 / P-glycoprotein Inducer (Herbal)": [
            "st john",
            "st. john",
            "hypericum",
            "cyp3a4",
            "p-glycoprotein",
        ],
    }
    for cls, syns in synonyms.items():
        if drug_class.lower() == cls.lower():
            keywords.extend(syns)
    return keywords


# ============================================================
# SECTION 5: Scenario Index — for demo evaluation
# ============================================================

# Pre-built scenarios that demonstrate agent capabilities.
# These map to the eval cases the PRD outlines.

SCENARIOS = [
    {
        "id": "scenario_01",
        "title": "NSAID + ACE Inhibitor: OTC ibuprofen with perindopril",
        "patient_profile": {
            "name": "张阿姨",
            "age": 68,
            "medications": ["perindopril 5mg daily", "atorvastatin 20mg daily"],
            "allergies": ["sulfonamide antibiotics"],
            "conditions": ["Hypertension", "Hypercholesterolaemia"],
        },
        "scenario": "Parent asks about buying Nurofen (ibuprofen) for knee pain.",
        "expected_agent_action": (
            "Companion Agent should: (1) retrieve perindopril from memory, "
            "(2) look up ibuprofen in drug knowledge, (3) detect MODERATE interaction "
            "(NSAID+ACEi reducing BP control, kidney risk), "
            "(4) generate response card recommending paracetamol (Panadol) instead, "
            "and advising to consult pharmacist if ibuprofen is needed."
        ),
        "correct_response_hint": "建议用 Panadol（扑热息痛）代替 Nurofen。Nurofen 可能减弱降压药效果，增加肾脏负担。如必须使用，请咨询药剂师。",
    },
    {
        "id": "scenario_02",
        "title": "NSAID + Warfarin: HIGH risk bleeding",
        "patient_profile": {
            "name": "李叔叔",
            "age": 74,
            "medications": [
                "warfarin 3mg daily (INR target 2.0-3.0)",
                "metformin 1000mg twice daily",
                "rosuvastatin 10mg daily",
            ],
            "allergies": [],
            "conditions": ["Atrial fibrillation", "Type 2 diabetes", "Hypercholesterolaemia"],
        },
        "scenario": "Parent has back pain, asks pharmacist for Voltaren (diclofenac).",
        "expected_agent_action": (
            "Companion Agent should: (1) retrieve warfarin from memory, "
            "(2) detect HIGH risk interaction (NSAID+warfarin doubles GI bleeding risk), "
            "(3) generate HIGH-alert response card STRONGLY recommending against this combination, "
            "(4) suggest paracetamol as alternative and flag that a PPI (e.g. pantoprazole) "
            "would be needed if NSAID was absolutely required."
        ),
        "correct_response_hint": "🔴 高风险：您正在服用华法林（抗凝药）。Voltaren 与华法林合用会使出血风险翻倍。强烈建议改用 Panadol 止痛。如需使用 Voltaren，必须先咨询医生，并可能需要胃保护药。",
    },
    {
        "id": "scenario_03",
        "title": "Cold & Flu decongestant + Hypertension",
        "patient_profile": {
            "name": "王奶奶",
            "age": 71,
            "medications": ["amlodipine 5mg daily", "candesartan 16mg daily"],
            "allergies": ["penicillin"],
            "conditions": ["Hypertension"],
        },
        "scenario": "Parent has a cold, wants to buy Codral (contains pseudoephedrine).",
        "expected_agent_action": (
            "Companion Agent should: (1) retrieve amlodipine+candesartan (BP meds) from memory, "
            "(2) detect MODERATE interaction (decongestant raises BP, counteracting treatment), "
            "(3) recommend saline nasal spray or steam inhalation, or short-term use with monitoring."
        ),
        "correct_response_hint": "注意：Codral 含伪麻黄碱，可能升高血压，与您的降压药作用相反。短期使用（1-3天）通常可接受，但建议先用盐水喷鼻或蒸汽吸入。如血压控制不佳，请避免使用。",
    },
    {
        "id": "scenario_04",
        "title": "Statin + Grapefruit: dietary interaction",
        "patient_profile": {
            "name": "赵伯伯",
            "age": 69,
            "medications": ["atorvastatin 40mg daily", "metformin 500mg twice daily"],
            "allergies": [],
            "conditions": ["Hypercholesterolaemia", "Type 2 diabetes"],
        },
        "scenario": "Parent asks if it's safe to eat grapefruit while on cholesterol medication.",
        "expected_agent_action": (
            "Companion Agent should: (1) retrieve atorvastatin from memory, "
            "(2) detect grapefruit-statin interaction (CYP3A4 inhibition), "
            "(3) advise limiting grapefruit or switching to rosuvastatin."
        ),
        "correct_response_hint": "葡萄柚会影响 Lipitor（阿托伐他汀）的代谢，可能增加肌肉副作用风险。建议避免或少量食用。如喜欢葡萄柚，可咨询医生换用 Crestor（瑞舒伐他汀），受影响较小。",
    },
    {
        "id": "scenario_05",
        "title": "Cross-session memory: pharmacist's suggestion recall",
        "patient_profile": {
            "name": "张阿姨",
            "age": 68,
            "medications": ["perindopril 5mg daily", "atorvastatin 20mg daily"],
            "allergies": ["sulfonamide antibiotics"],
            "conditions": ["Hypertension", "Hypercholesterolaemia"],
        },
        "scenario": (
            "HERO SCENE — Second visit. "
            "At the LAST visit, pharmacist mentioned a new supplement called "
            "'Coenzyme Q10' that might help with statin-related muscle aches. "
            "This was recorded to memory via KK. "
            "Parent returns today for a routine prescription refill. "
            "KK should proactively retrieve this from memory and ask: "
            "'Last time the pharmacist mentioned Coenzyme Q10 for your muscle aches — "
            "would you like to ask about it today?'"
        ),
        "expected_agent_action": (
            "Companion Agent must: (1) call memory.search on session start, "
            "(2) detect unresolved suggestion from last visit, "
            "(3) proactively surface this BEFORE responding to the refill request, "
            "(4) generate a response card offering to follow up on the suggestion. "
            "This is the 'hero shot' proving cross-session memory + agent initiative."
        ),
        "correct_response_hint": "上次药剂师提到的辅酶Q10补充剂，您今天要一起问一下吗？这个可能对您服用他汀引起的肌肉酸痛有帮助。",
    },
]


# ============================================================
# SECTION 6: Quick self-test (run: python drug_knowledge.py)
# ============================================================

if __name__ == "__main__":
    print("=== Drug Knowledge Base Self-Test ===\n")

    # Test 1: Generic lookup
    result = drug_lookup("perindopril")
    print(f"[PASS] perindopril → {result['class']}" if result else "[FAIL] perindopril not found")

    # Test 2: Brand name lookup
    result = drug_lookup("Norvasc")
    print(
        f"[PASS] Norvasc → {result['name']} ({result['class']})"
        if result
        else "[FAIL] Norvasc not found"
    )

    # Test 3: OTC lookup
    result = drug_lookup("Nurofen")
    print(
        f"[PASS] Nurofen → {result['name']} ({result['class']})"
        if result
        else "[FAIL] Nurofen not found"
    )

    # Test 4: Australian brand
    result = drug_lookup("Coversyl")
    print(f"[PASS] Coversyl → {result['name']}" if result else "[FAIL] Coversyl not found")

    # Test 5: Substance lookup
    result = substance_lookup("grapefruit")
    print(
        f"[PASS] grapefruit → substance ({result['class']})"
        if result
        else "[FAIL] grapefruit not found"
    )

    # Test 6: Drug × Substance interaction (the Scenario 04 gap)
    result = check_interaction("atorvastatin", "grapefruit")
    if result:
        print(f"[PASS] atorvastatin × grapefruit → {result['risk']} RISK")
        print(f"       mechanism: {result['mechanism'][:80]}...")
    else:
        print("[FAIL] atorvastatin × grapefruit NOT detected")

    # Test 7: All 5 scenarios
    print(f"\n[INFO] {len(SCENARIOS)} demo scenarios loaded")
    for s in SCENARIOS:
        print(f"  • {s['id']}: {s['title']}")

    print("\n=== Test Complete ===")
