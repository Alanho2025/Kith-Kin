import pytest

from app.schemas.agent_outputs import RouteDecision, parse_structured_output


def test_invalid_structured_output_fails_closed() -> None:
    with pytest.raises(ValueError, match="AGENT_OUTPUT_INVALID"):
        parse_structured_output(RouteDecision, "this is not json")


def test_free_form_extra_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="AGENT_OUTPUT_INVALID"):
        parse_structured_output(
            RouteDecision,
            {
                "route_type": "passive_translation",
                "confidence": 0.9,
                "reason_code": "routine_translation",
                "chain_of_thought": "hidden",
            },
        )
