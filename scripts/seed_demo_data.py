"""Seed or clean deterministic demo pharmacy memory data."""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.models.allergy import Allergy  # noqa: E402
from app.db.models.medication import Medication  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.visit_summary import VisitSummary  # noqa: E402
from app.db.models.drug_knowledge_entity import DrugKnowledgeEntity  # noqa: E402
from app.db.models.drug_interaction_rule import DrugInteractionRule  # noqa: E402
from app.db.session import create_engine, create_session_factory, initialize_database  # noqa: E402

DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
DEMO_SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
DEMO_MEDICATION_ID = UUID("00000000-0000-4000-8000-000000000201")
DEMO_ALLERGY_ID = UUID("00000000-0000-4000-8000-000000000202")
DEMO_VISIT_ID = UUID("00000000-0000-4000-8000-000000000203")
DEMO_VISIT_IDEMPOTENCY_KEY = UUID("00000000-0000-4000-8000-000000000204")
NOW = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)


async def seed(database_url: str, *, cleanup: bool) -> dict[str, int]:
    """Apply or remove deterministic demo rows."""
    from uuid import uuid5, NAMESPACE_DNS
    engine = create_engine(database_url)
    await initialize_database(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        if cleanup:
            await session.execute(delete(VisitSummary).where(VisitSummary.user_id == DEMO_USER_ID))
            await session.execute(delete(Allergy).where(Allergy.user_id == DEMO_USER_ID))
            await session.execute(delete(Medication).where(Medication.user_id == DEMO_USER_ID))
            await session.execute(delete(User).where(User.id == DEMO_USER_ID))
            await session.execute(delete(DrugKnowledgeEntity))
            await session.execute(delete(DrugInteractionRule))
            await session.commit()
            await engine.dispose()
            return {"users": 0, "medications": 0, "allergies": 0, "visit_summaries": 0}
        await session.merge(
            User(
                id=DEMO_USER_ID,
                display_name="Demo parent",
                preferred_language="zh_cn",
                family_contact_label="Adult child",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.merge(
            Medication(
                id=DEMO_MEDICATION_ID,
                user_id=DEMO_USER_ID,
                name="Lisinopril",
                dose="10 mg once daily",
                notes="Blood pressure medicine to confirm with pharmacist before new medicines.",
                tags=["profile", "medications", "blood_pressure"],
                updated_at=NOW,
            )
        )
        await session.merge(
            Allergy(
                id=DEMO_ALLERGY_ID,
                user_id=DEMO_USER_ID,
                substance="Penicillin",
                reaction="Rash reported by family.",
                tags=["profile", "allergies", "antibiotic"],
                updated_at=NOW,
            )
        )
        await session.merge(
            VisitSummary(
                id=DEMO_VISIT_ID,
                user_id=DEMO_USER_ID,
                session_id=DEMO_SESSION_ID,
                key="visit_summary:demo_prior_pharmacy",
                value={
                    "mentioned_drugs": ["Lisinopril"],
                    "pharmacist_advice_summary": "Asked pharmacist to check compatibility before buying cold medicine.",
                    "unresolved_questions": ["Confirm any new medicine with pharmacist."],
                    "follow_up_needed": False,
                    "family_notification_requested": False,
                },
                tags=["visit_summary", "pharmacy", "demo"],
                idempotency_key=DEMO_VISIT_IDEMPOTENCY_KEY,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        
        # Seed drug knowledge entities
        from app.data.drug_knowledge import DRUG_PROFILES, OTC_DRUGS, SUBSTANCES, INTERACTIONS
        for name, info in DRUG_PROFILES.items():
            await session.merge(
                DrugKnowledgeEntity(
                    id=uuid5(NAMESPACE_DNS, f"drug:{name}"),
                    name=name,
                    entity_type="prescription",
                    class_name=info["class"],
                    brands_or_sources=info.get("brands_au", []),
                    indications_or_use=info.get("indications", []),
                    warnings_or_notes=info.get("warnings", []),
                    common_in_elderly=info.get("common_in_elderly", False),
                )
            )
        for name, info in OTC_DRUGS.items():
            await session.merge(
                DrugKnowledgeEntity(
                    id=uuid5(NAMESPACE_DNS, f"otc:{name}"),
                    name=name,
                    entity_type="otc",
                    class_name=info["class"],
                    brands_or_sources=info.get("brands_au", []),
                    indications_or_use=[info.get("typical_use")] if info.get("typical_use") else [],
                    warnings_or_notes=[info.get("elderly_note")] if info.get("elderly_note") else [],
                    common_in_elderly=True,
                )
            )
        for name, info in SUBSTANCES.items():
            await session.merge(
                DrugKnowledgeEntity(
                    id=uuid5(NAMESPACE_DNS, f"substance:{name}"),
                    name=name,
                    entity_type="substance",
                    class_name=info["class"],
                    brands_or_sources=info.get("sources", []),
                    indications_or_use=[],
                    warnings_or_notes=[info.get("elderly_note")] if info.get("elderly_note") else [],
                    common_in_elderly=False,
                )
            )
            
        # Seed interaction rules
        for i, rule in enumerate(INTERACTIONS):
            await session.merge(
                DrugInteractionRule(
                    id=uuid5(NAMESPACE_DNS, f"interaction:{i}:{rule.risk}"),
                    risk=rule.risk,
                    mechanism=rule.mechanism,
                    recommendation=rule.recommendation,
                    source=rule.source,
                )
            )
        await session.commit()
    await engine.dispose()
    return {"users": 1, "medications": 1, "allergies": 1, "visit_summaries": 1}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///backend/kithkin_test.db",
        help="Async SQLAlchemy SQLite URL to seed.",
    )
    parser.add_argument("--cleanup", action="store_true", help="Remove deterministic demo rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    counts = asyncio.run(seed(args.database_url, cleanup=args.cleanup))
    print("demo_seed_counts " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
