"""Repository for general drug knowledge and interaction rules."""

from typing import Any

from sqlalchemy import select

from app.db.models.drug_interaction_rule import DrugInteractionRule
from app.db.models.drug_knowledge_entity import DrugKnowledgeEntity
from app.db.session import AsyncSessionFactory


class DrugKnowledgeRepository:
    """Repository boundary for querying general drug facts and interaction warnings."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def find_entity(self, name: str) -> DrugKnowledgeEntity | None:
        """Find a drug or substance entity by generic name, brand name, or source."""
        q = name.strip().lower().rstrip(".")
        async with self._session_factory() as session:
            stmt = select(DrugKnowledgeEntity).where(DrugKnowledgeEntity.name == q)
            res = await session.execute(stmt)
            entity = res.scalar_one_or_none()
            if entity:
                return entity

            # Scan other brands/sources
            stmt = select(DrugKnowledgeEntity)
            res = await session.execute(stmt)
            for ent in res.scalars().all():
                for item in ent.brands_or_sources:
                    item_norm = item.strip().lower().rstrip(".")
                    if q in item_norm or item_norm in q:
                        return ent
        return None

    async def check_interaction(
        self,
        entity_a: DrugKnowledgeEntity,
        entity_b: DrugKnowledgeEntity,
    ) -> dict[str, Any] | None:
        """Check for a known interaction rule between two entities.

        Returns dictionary of risk metadata or None.
        """
        class_a = entity_a.class_name
        class_b = entity_b.class_name

        async with self._session_factory() as session:
            stmt = select(DrugInteractionRule)
            res = await session.execute(stmt)
            rules = res.scalars().all()

        for rule in rules:
            mech_lower = rule.mechanism.lower()
            rec_lower = rule.recommendation.lower()

            relevant = False
            for keyword_a in _class_keywords(class_a):
                for keyword_b in _class_keywords(class_b):
                    if (keyword_a in mech_lower or keyword_a in rec_lower) and \
                       (keyword_b in mech_lower or keyword_b in rec_lower):
                        relevant = True
                        break
                if relevant:
                    break

            if relevant:
                return {
                    "risk": rule.risk,
                    "mechanism": rule.mechanism,
                    "recommendation": rule.recommendation,
                    "source": rule.source,
                    "drug_a": entity_a.name,
                    "drug_b": entity_b.name,
                }
        return None


def _class_keywords(drug_class: str) -> list[str]:
    """Generate search keywords for a drug class, identical to drug_knowledge.py."""
    keywords = [drug_class.lower()]
    synonyms = {
        "ACE Inhibitor": [
            "ace inhibitor", "ace inhibitors", "perindopril", "ramipril", "lisinopril"
        ],
        "Angiotensin II Receptor Blocker (ARB)": [
            "arb", "angiotensin", "candesartan", "telmisartan", "irbesartan"
        ],
        "Calcium Channel Blocker (Dihydropyridine)": [
            "calcium channel blocker", "amlodipine"
        ],
        "Statin (HMG-CoA Reductase Inhibitor)": [
            "statin", "statins", "atorvastatin", "rosuvastatin"
        ],
        "NSAID": [
            "nsaid", "nsaids", "anti-inflammatory", "ibuprofen", "diclofenac", "naproxen"
        ],
        "Antiplatelet (low dose 100mg)": [
            "aspirin", "antiplatelet"
        ],
        "Vitamin K Antagonist (Anticoagulant)": [
            "warfarin", "anticoagulant", "anticoagulants"
        ],
        "Direct Oral Anticoagulant (Factor Xa Inhibitor)": [
            "anticoagulant", "anticoagulants", "apixaban", "rivaroxaban", "eliquis", "xarelto"
        ],
        "SSRI Antidepressant": [
            "ssri", "antidepressant", "sertraline", "escitalopram", "zoloft", "lexapro"
        ],
        "Biguanide": [
            "metformin", "diabetes"
        ],
        "Proton Pump Inhibitor (PPI)": [
            "ppi", "pantoprazole", "esomeprazole", "omeprazole"
        ],
        "Decongestant (sympathomimetic)": [
            "decongestant", "pseudoephedrine", "phenylephrine", "sudafed", "codral"
        ],
        # Substance classes
        "CYP3A4 Inhibitor (Dietary)": [
            "grapefruit", "grapefruit juice", "cyp3a4", "seville oranges"
        ],
        "CNS Depressant / Hepatotoxin (Dietary)": [
            "alcohol", "beer", "wine", "spirits", "ethanol", "lactic acidosis"
        ],
        "CYP2C9 / OATP Inhibitor (Dietary)": [
            "cranberry", "cranberry juice", "cyp2c9", "warfarin"
        ],
        "CYP3A4 / P-glycoprotein Inducer (Herbal)": [
            "st john", "st. john", "hypericum", "cyp3a4", "p-glycoprotein"
        ],
    }
    for cls, syns in synonyms.items():
        if drug_class.lower() == cls.lower():
            keywords.extend(syns)
    return keywords
