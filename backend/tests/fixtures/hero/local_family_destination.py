import pytest


@pytest.fixture
def local_family_destination() -> str:
    """Mock family destination label representing the target contact."""
    return "Adult child"
