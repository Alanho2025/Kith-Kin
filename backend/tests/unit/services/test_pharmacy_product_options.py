from app.services.pharmacy_product_options import PharmacyProductOptionTracker


def test_tracker_builds_neutral_options_from_pharmacist_template() -> None:
    tracker = PharmacyProductOptionTracker()
    session_id = "session-template-1"

    first = tracker.update(
        session_id,
        (
            "I can show you three options. This one is paracetamol, "
            "this one is ibuprofen, and this one is a cold and flu tablet."
        ),
    )

    assert first is not None
    assert [option["name"] for option in first["options"]] == [
        "paracetamol",
        "ibuprofen",
        "cold and flu tablet",
    ]
    assert all(option["price"] is None for option in first["options"])

    second = tracker.update(
        session_id,
        (
            "Paracetamol is usually used for pain or fever. "
            "Ibuprofen may not be suitable for some people with stomach problems, "
            "kidney problems, or certain medicines. "
            "The cold and flu tablet may not be suitable if you have high blood pressure."
        ),
    )

    assert second is not None
    assert second["options"][0]["pharmacist_stated_use"] == "usually used for pain or fever"
    assert second["options"][1]["pharmacist_stated_cautions"] == (
        "may not be suitable for some people with stomach problems, "
        "kidney problems, or certain medicines"
    )
    assert second["options"][2]["pharmacist_stated_cautions"] == (
        "may not be suitable if you have high blood pressure"
    )

    third = tracker.update(session_id, "The prices are 6 dollars, 9 dollars, and 12 dollars.")

    assert third is not None
    assert [option["price"] for option in third["options"]] == [
        "6 dollars",
        "9 dollars",
        "12 dollars",
    ]


def test_tracker_ignores_unrelated_small_talk() -> None:
    tracker = PharmacyProductOptionTracker()

    assert tracker.update("session-template-2", "Hi, good morning. How are you today?") is None


def test_tracker_builds_neutral_options_from_e16_pharmacist_options() -> None:
    tracker = PharmacyProductOptionTracker()
    session_id = "session-e16-options"

    first = tracker.update(
        session_id,
        (
            "For your headache I have three options: Panadol which is paracetamol, "
            "Nurofen which is ibuprofen, and a cheaper store-brand paracetamol."
        ),
    )

    assert first is not None
    assert [option["name"] for option in first["options"]] == [
        "Panadol",
        "Nurofen",
        "store-brand paracetamol",
    ]
    assert first["options"][0]["pharmacist_stated_use"] == "paracetamol"
    assert first["options"][1]["pharmacist_stated_use"] == "ibuprofen"
    assert first["options"][2]["pharmacist_stated_use"] is None
    assert "best" not in str(first).lower()
    assert "safer" not in str(first).lower()
    assert "recommend" not in str(first).lower()

    second = tracker.update(
        session_id,
        (
            "Panadol directions are two tablets every six hours if suitable. "
            "Nurofen may irritate the stomach. "
            "The store-brand paracetamol price is 5 dollars."
        ),
    )

    assert second is not None
    assert second["options"][0]["pharmacist_stated_directions"] == (
        "two tablets every six hours if suitable"
    )
    assert second["options"][1]["pharmacist_stated_cautions"] == "may irritate the stomach"
    assert second["options"][2]["price"] == "5 dollars"
