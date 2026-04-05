import pytest
from chart_generator import ChartGenerator


class TestChartGeneratorClass:
    """Test ChartGenerator class exists and has correct interface."""

    def test_class_exists(self):
        """Test that ChartGenerator class exists."""
        assert ChartGenerator is not None
        cg = ChartGenerator()
        assert isinstance(cg, ChartGenerator)

    def test_spending_pie_returns_bytes(self):
        """Test that spending_pie_chart returns bytes."""
        cg = ChartGenerator()
        data = {"by_category": {"Food": 500000, "Transport": 200000}, "total": 700000}
        result = cg.spending_pie_chart(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_monthly_bar_returns_bytes(self):
        """Test that monthly_bar_chart returns bytes."""
        cg = ChartGenerator()
        data = {"by_category": {"Food": 500000, "Transport": 200000}, "total": 700000}
        result = cg.monthly_bar_chart(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_budget_status_returns_bytes(self):
        """Test that budget_status_chart returns bytes."""
        cg = ChartGenerator()
        data = {
            "items": [
                {"category": "Food", "budget": 1000000, "spent": 750000, "status": "OK"},
                {"category": "Transport", "budget": 500000, "spent": 450000, "status": "OK"},
            ]
        }
        result = cg.budget_status_chart(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_savings_progress_returns_bytes(self):
        """Test that savings_progress_chart returns bytes."""
        cg = ChartGenerator()
        data = {"savings_total": 10000000}
        result = cg.savings_progress_chart(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_health_score_returns_bytes(self):
        """Test that health_score_chart returns bytes."""
        cg = ChartGenerator()
        data = {"score": 75, "label": "Good"}
        result = cg.health_score_chart(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_spending_pie_returns_png(self):
        """Test that spending_pie_chart returns valid PNG bytes."""
        cg = ChartGenerator()
        data = {"by_category": {"Food": 500000, "Transport": 200000}, "total": 700000}
        result = cg.spending_pie_chart(data)
        # PNG magic number: \x89PNG
        assert result.startswith(b"\x89PNG"), "Result should be valid PNG bytes"

    def test_monthly_bar_returns_png(self):
        """Test that monthly_bar_chart returns valid PNG bytes."""
        cg = ChartGenerator()
        data = {"by_category": {"Food": 500000, "Transport": 200000}, "total": 700000}
        result = cg.monthly_bar_chart(data)
        assert result.startswith(b"\x89PNG"), "Result should be valid PNG bytes"

    def test_budget_status_returns_png(self):
        """Test that budget_status_chart returns valid PNG bytes."""
        cg = ChartGenerator()
        data = {
            "items": [
                {"category": "Food", "budget": 1000000, "spent": 750000, "status": "OK"},
            ]
        }
        result = cg.budget_status_chart(data)
        assert result.startswith(b"\x89PNG"), "Result should be valid PNG bytes"

    def test_savings_progress_returns_png(self):
        """Test that savings_progress_chart returns valid PNG bytes."""
        cg = ChartGenerator()
        data = {"savings_total": 10000000}
        result = cg.savings_progress_chart(data)
        assert result.startswith(b"\x89PNG"), "Result should be valid PNG bytes"

    def test_health_score_returns_png(self):
        """Test that health_score_chart returns valid PNG bytes."""
        cg = ChartGenerator()
        data = {"score": 75, "label": "Good"}
        result = cg.health_score_chart(data)
        assert result.startswith(b"\x89PNG"), "Result should be valid PNG bytes"
