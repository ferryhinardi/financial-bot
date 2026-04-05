import pytest
from health_score import HealthScoreGenerator


@pytest.fixture
def sample_data():
    """Sample dashboard data from get_dashboard()."""
    return {
        "income": 8000000,
        "spending": 5000000,
        "savings_total": 10000000,
        "investment_total": 5000000,
        "debt_total": 0,
        "net_worth": 15000000,
        "budget_remaining": 500000,
        "month": "2026-04",
    }


@pytest.fixture
def generator():
    """HealthScoreGenerator instance."""
    return HealthScoreGenerator()


def test_generate_scorecard_returns_png(generator, sample_data):
    """Test that generate_scorecard returns valid PNG bytes."""
    result = generator.generate_scorecard(sample_data)

    # Should return bytes
    assert isinstance(result, bytes)

    # Should be valid PNG (magic number: 89 50 4E 47)
    assert result.startswith(b"\x89PNG")

    # Should have reasonable size (at least 1KB)
    assert len(result) > 1000


def test_generate_scorecard_with_all_indicators(generator, sample_data):
    """Test that scorecard includes all 8 indicators."""
    result = generator.generate_scorecard(sample_data)
    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG")


def test_generate_scorecard_with_minimal_data(generator):
    """Test that scorecard works with minimal data."""
    minimal = {
        "income": 5000000,
        "spending": 3000000,
        "savings_total": 2000000,
        "investment_total": 0,
        "debt_total": 0,
        "net_worth": 2000000,
        "budget_remaining": 100000,
        "month": "2026-04",
    }
    result = generator.generate_scorecard(minimal)
    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG")
