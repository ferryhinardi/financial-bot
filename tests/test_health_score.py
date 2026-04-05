import pytest
from health_score import HealthScoreGenerator


@pytest.fixture
def sample_data():
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
    return HealthScoreGenerator()


def test_generate_scorecard_returns_png(generator, sample_data):
    result = generator.generate_scorecard(sample_data)
    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG")
    assert len(result) > 1000


def test_generate_scorecard_with_all_indicators(generator, sample_data):
    result = generator.generate_scorecard(sample_data)
    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG")


def test_generate_scorecard_with_minimal_data(generator):
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


def test_scorecard_score_range(generator, sample_data):
    indicators = generator._calculate_indicators(
        sample_data["income"],
        sample_data["spending"],
        sample_data["savings_total"],
        sample_data["investment_total"],
        sample_data["debt_total"],
        sample_data["net_worth"],
        sample_data["budget_remaining"],
    )
    overall_score = round(sum(ind["score"] for ind in indicators) / len(indicators))
    assert 0 <= overall_score <= 100
