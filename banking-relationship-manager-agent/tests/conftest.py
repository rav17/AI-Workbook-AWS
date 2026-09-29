import pytest


@pytest.fixture
def sample_profile_payload():
    return {
        "client_id": "CUST-1001",
        "name": "Aisha Khan",
        "segment": "premier",
        "risk_appetite": "moderate",
        "needs": ["wealth growth", "tax planning"],
    }
