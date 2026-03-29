import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from excel_manager import ExcelManager

FIXTURE_WORKBOOK = Path(__file__).resolve().parents[1] / "Financial_Tracker.xlsx"


class FindSimilarTransactionsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.manager = ExcelManager(self.workbook_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_no_duplicates_in_empty_sheet(self):
        result = self.manager.find_similar_transactions(amount=50000, description="GRAB")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_finds_duplicate_after_adding_transaction(self):
        self.manager.add_transaction(
            amount=50000,
            category="Transportation",
            description="GRAB ride",
        )
        result = self.manager.find_similar_transactions(amount=50000, description="GRAB ride")
        self.assertGreaterEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["amount"], 50000, places=0)

    def test_no_match_for_different_amount(self):
        self.manager.add_transaction(
            amount=50000,
            category="Transportation",
            description="GRAB ride",
        )
        result = self.manager.find_similar_transactions(amount=200000, description="GRAB ride")
        self.assertEqual(len(result), 0)


class FindSimilarIncomeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.manager = ExcelManager(self.workbook_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_no_duplicates_in_empty_sheet(self):
        result = self.manager.find_similar_income(amount=8000000, source="PT ABC")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_finds_duplicate_after_adding_income(self):
        self.manager.add_income(
            amount=8000000,
            source="PT ABC Salary",
            category="Salary",
        )
        result = self.manager.find_similar_income(amount=8000000, source="PT ABC")
        self.assertGreaterEqual(len(result), 1)

    def test_no_match_for_different_amount(self):
        self.manager.add_income(
            amount=8000000,
            source="PT ABC Salary",
            category="Salary",
        )
        result = self.manager.find_similar_income(amount=3000000, source="PT ABC")
        self.assertEqual(len(result), 0)


class HasCommonSubstringTestCase(unittest.TestCase):
    def test_common_substring_found(self):
        result = ExcelManager._has_common_substring("GRAB ride home", "GRAB taxi", min_len=3)
        self.assertTrue(result)

    def test_no_common_substring(self):
        result = ExcelManager._has_common_substring("GRAB", "SHOPEE", min_len=3)
        self.assertFalse(result)

    def test_empty_strings(self):
        result = ExcelManager._has_common_substring("", "", min_len=3)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
