import importlib.util
import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[4]


async def test_seed_and_cleanup_are_idempotent(tmp_path) -> None:
    seed = _load_seed()
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}"
    expected_counts = {"users": 1, "medications": 1, "allergies": 1, "visit_summaries": 2}

    first = await seed(database_url, cleanup=False)
    second = await seed(database_url, cleanup=False)

    assert first == second == expected_counts

    from app.db.models.allergy import Allergy
    from app.db.models.drug_knowledge_entity import DrugKnowledgeEntity
    from app.db.models.medication import Medication
    from app.db.models.visit_summary import VisitSummary
    from app.db.session import create_engine, create_session_factory

    engine = create_engine(database_url)
    factory = create_session_factory(engine)
    async with factory() as session:
        medications = (await session.scalars(select(Medication))).all()
        allergies = (await session.scalars(select(Allergy))).all()
        summaries = (await session.scalars(select(VisitSummary))).all()
        drug_entities = (await session.scalars(select(DrugKnowledgeEntity))).all()
    await engine.dispose()

    assert [item.name for item in medications] == ["Lisinopril"]
    assert "Blood pressure medicine" in medications[0].notes
    assert medications[0].tags == ["profile", "medications", "blood_pressure", "hypertension"]

    assert [item.substance for item in allergies] == ["Penicillin"]
    assert allergies[0].reaction == "Rash reported by family."
    assert allergies[0].tags == ["profile", "allergies", "antibiotic"]

    summary_text = json.dumps([item.value for item in summaries], ensure_ascii=False)
    assert "Lisinopril" in summary_text
    assert "active ingredient" in summary_text
    assert "intended use" in summary_text
    assert "overseas medicine" in summary_text
    assert "family_notification_requested" in summary_text
    assert len(summaries) == 2

    entity_names = {item.name for item in drug_entities}
    brands = {
        brand
        for item in drug_entities
        for brand in (item.brands_or_sources or [])
        if isinstance(brand, str)
    }
    assert {"paracetamol", "ibuprofen", "diclofenac"} <= entity_names
    assert {"Panadol", "Nurofen", "Voltaren"} <= brands

    cleanup = await seed(database_url, cleanup=True)
    assert cleanup == {"users": 0, "medications": 0, "allergies": 0, "visit_summaries": 0}


def _load_seed() -> Any:
    spec = importlib.util.spec_from_file_location(
        "seed_demo_data",
        ROOT / "scripts/seed_demo_data.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return cast(Any, module.seed)
