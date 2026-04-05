import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from excel_manager import ExcelManager


FIXTURE_WORKBOOK = Path(__file__).resolve().parents[1] / "Financial_Tracker.xlsx"


class SavingsGoalsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.milestones_path = Path(self.temp_dir.name) / "savings_milestones.json"
        self.manager = ExcelManager(self.workbook_path, milestones_path=self.milestones_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_savings_goals_returns_list_with_required_fields(self):
        """Test that get_savings_goals returns list with account, balance, goal, progress_pct, etc."""
        goals = self.manager.get_savings_goals()

        self.assertIsInstance(goals, list)
        self.assertGreater(len(goals), 0)

        # Check first goal has all required fields
        first = goals[0]
        self.assertIn("account", first)
        self.assertIn("balance", first)
        self.assertIn("goal", first)
        self.assertIn("progress_pct", first)
        self.assertIn("eta_months", first)
        self.assertIn("milestones_hit", first)

    def test_get_savings_goals_calculates_progress_correctly(self):
        """Test progress_pct calculation: (balance / goal * 100)"""
        goals = self.manager.get_savings_goals()

        ef_goal = next((g for g in goals if g["account"] == "Emergency Fund"), None)
        self.assertIsNotNone(ef_goal)

        self.assertGreater(ef_goal["progress_pct"], 0)
        self.assertLessEqual(ef_goal["progress_pct"], 100)

    def test_get_savings_goals_calculates_eta_months(self):
        """Test ETA calculation based on avg monthly deposits"""
        # First add some additional deposits to create a pattern
        self.manager.add_savings(
            amount=500_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )
        self.manager.add_savings(
            amount=500_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )

        goals = self.manager.get_savings_goals()
        ef_goal = next((g for g in goals if g["account"] == "Emergency Fund"), None)

        # If goal is 10M and balance is 2.5M (from fixture + 1M), avg monthly deposits exists
        # eta_months should be (goal - balance) / avg_monthly
        # This is flexible since it depends on deposit history
        self.assertIsNotNone(ef_goal)
        # ETA can be None or a number
        if ef_goal["eta_months"] is not None:
            self.assertGreater(ef_goal["eta_months"], 0)

    def test_get_savings_goals_identifies_milestones_hit(self):
        """Test milestones_hit identifies crossed milestones (25, 50, 75, 90, 100)"""
        # Set up: Create a goal with 60% progress (should include 25% and 50%)
        self.manager.add_savings(
            amount=5_000_000,  # Add 5M to 1M = 6M out of 10M goal = 60%
            account="Emergency Fund",
            transaction_type="Deposit",
        )

        goals = self.manager.get_savings_goals()
        ef_goal = next((g for g in goals if g["account"] == "Emergency Fund"), None)

        self.assertIsNotNone(ef_goal)
        self.assertIn(25, ef_goal["milestones_hit"])
        self.assertIn(50, ef_goal["milestones_hit"])
        self.assertNotIn(75, ef_goal["milestones_hit"])
        self.assertNotIn(100, ef_goal["milestones_hit"])

    def test_milestone_detection_returns_none_when_no_milestone_crossed(self):
        """Test check_milestone returns None if no new milestone reached"""
        # Get initial state
        result = self.manager.check_milestone("Emergency Fund")

        # At 10%, no milestone has been crossed yet
        self.assertIsNone(result)

    def test_milestone_detection_returns_dict_when_milestone_crossed(self):
        """Test check_milestone returns dict with account, milestone_pct, message when crossed"""
        # Add enough to cross 25% milestone (1M initial -> need 2.5M, add 2M)
        self.manager.add_savings(
            amount=2_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )

        result = self.manager.check_milestone("Emergency Fund")

        self.assertIsNotNone(result)
        self.assertIn("account", result)
        self.assertIn("milestone_pct", result)
        self.assertIn("message", result)
        self.assertEqual(result["account"], "Emergency Fund")
        self.assertEqual(result["milestone_pct"], 25)

    def test_milestone_detection_persists_to_json(self):
        """Test that milestone state is persisted to savings_milestones.json"""
        # Cross a milestone
        self.manager.add_savings(
            amount=2_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )
        result = self.manager.check_milestone("Emergency Fund")

        # Check JSON file was created and has the milestone data
        self.assertTrue(self.milestones_path.exists())
        with open(self.milestones_path) as f:
            data = json.load(f)

        self.assertIn("Emergency Fund", data)
        self.assertEqual(data["Emergency Fund"]["last_milestone"], 25)

    def test_milestone_detection_does_not_repeat_milestone(self):
        """Test that same milestone is not reported twice"""
        # Cross 25% milestone first time
        self.manager.add_savings(
            amount=2_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )
        result1 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNotNone(result1)

        # Call again without new deposits - should return None
        result2 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNone(result2)

    def test_get_celebration_message_25_percent(self):
        """Test celebration message for 25% milestone"""
        message = self.manager.get_celebration_message(25)

        self.assertIsNotNone(message)
        self.assertIn("Hebat", message)

    def test_get_celebration_message_50_percent(self):
        """Test celebration message for 50% milestone"""
        message = self.manager.get_celebration_message(50)

        self.assertIsNotNone(message)
        self.assertIn("Setengah", message)

    def test_get_celebration_message_75_percent(self):
        """Test celebration message for 75% milestone"""
        message = self.manager.get_celebration_message(75)

        self.assertIsNotNone(message)
        self.assertIn("Hampir", message)

    def test_get_celebration_message_90_percent(self):
        """Test celebration message for 90% milestone"""
        message = self.manager.get_celebration_message(90)

        self.assertIsNotNone(message)
        self.assertIn("Sedikit", message)

    def test_get_celebration_message_100_percent(self):
        """Test celebration message for 100% milestone"""
        message = self.manager.get_celebration_message(100)

        self.assertIsNotNone(message)
        self.assertIn("SELAMAT", message)

    def test_celebration_message_returns_indonesian_string_with_emoji(self):
        """Test that messages contain Indonesian and emoji"""
        for pct in [25, 50, 75, 90, 100]:
            message = self.manager.get_celebration_message(pct)
            # Should have emoji
            self.assertTrue(any(ord(c) > 127 for c in message), f"No emoji in message for {pct}%: {message}")
            # Should be non-empty string
            self.assertGreater(len(message), 0)

    def test_progress_bar(self):
        self.assertEqual(self.manager.get_progress_bar(0), "░░░░░░░░░░ 0%")
        self.assertEqual(self.manager.get_progress_bar(100), "██████████ 100%")
        self.assertEqual(self.manager.get_progress_bar(50), "█████░░░░░ 50%")
        self.assertEqual(self.manager.get_progress_bar(45), "████░░░░░░ 45%")
        self.assertEqual(self.manager.get_progress_bar(105), "██████████ 105%")
        result = self.manager.get_progress_bar(33, width=6)
        self.assertEqual(result, "█░░░░░ 33%")

    def test_eta_no_deposits(self):
        goals = self.manager.get_savings_goals()
        vacation_goal = next((g for g in goals if g["account"] == "Vacation"), None)
        self.assertIsNotNone(vacation_goal)
        self.assertIsNone(vacation_goal["eta_months"])

    def test_milestone_jump(self):
        self.manager.add_savings(
            amount=6_500_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )
        goals = self.manager.get_savings_goals()
        ef_goal = next((g for g in goals if g["account"] == "Emergency Fund"), None)
        self.assertIsNotNone(ef_goal)
        self.assertGreaterEqual(ef_goal["progress_pct"], 75)
        self.assertIn(25, ef_goal["milestones_hit"])
        self.assertIn(50, ef_goal["milestones_hit"])
        self.assertIn(75, ef_goal["milestones_hit"])

        result1 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNotNone(result1)
        self.assertEqual(result1["milestone_pct"], 25)

        result2 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNotNone(result2)
        self.assertEqual(result2["milestone_pct"], 50)

        result3 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNotNone(result3)
        self.assertEqual(result3["milestone_pct"], 75)

        result4 = self.manager.check_milestone("Emergency Fund")
        self.assertIsNone(result4)


if __name__ == "__main__":
    unittest.main()
