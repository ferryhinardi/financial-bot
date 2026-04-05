import json
import os
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

from config import local_now
from recurring_manager import RecurringManager


class RecurringManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temp_dir.name) / "test_recurring.json"
        self.manager = RecurringManager(str(self.data_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_list(self):
        """Test adding a recurring bill and listing it."""
        bill_id = self.manager.add_recurring(
            name="Internet Bill",
            amount=500000,
            category="Bills & Utilities",
            payment_method="Bank Transfer",
            day_of_month=15,
        )

        self.assertIsNotNone(bill_id)

        bills = self.manager.list_recurring()
        self.assertEqual(len(bills), 1)
        bill = bills[0]
        self.assertEqual(bill["name"], "Internet Bill")
        self.assertEqual(bill["amount"], 500000)
        self.assertEqual(bill["category"], "Bills & Utilities")
        self.assertEqual(bill["payment_method"], "Bank Transfer")
        self.assertEqual(bill["day_of_month"], 15)
        self.assertTrue(bill["active"])
        self.assertIsNone(bill["last_paid"])

    def test_remove_recurring(self):
        """Test removing a recurring bill."""
        bill_id = self.manager.add_recurring(
            name="Electricity",
            amount=300000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=10,
        )

        bills = self.manager.list_recurring()
        self.assertEqual(len(bills), 1)

        self.manager.remove_recurring(bill_id)

        bills = self.manager.list_recurring()
        self.assertEqual(len(bills), 0)

    def test_get_due_today(self):
        """Test getting bills due today."""
        today = local_now()
        day_today = today.day

        # Add a bill due today
        bill_id_today = self.manager.add_recurring(
            name="Today Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=day_today,
        )

        # Add a bill due tomorrow
        day_tomorrow = (day_today % 28) + 1  # Simple wrapping for days
        self.manager.add_recurring(
            name="Tomorrow Bill",
            amount=200000,
            category="Housing",
            payment_method="Cash",
            day_of_month=day_tomorrow,
        )

        due_today = self.manager.get_due_today()
        self.assertEqual(len(due_today), 1)
        self.assertEqual(due_today[0]["name"], "Today Bill")

    def test_mark_paid(self):
        """Test marking a bill as paid."""
        today = local_now()
        day_today = today.day

        bill_id = self.manager.add_recurring(
            name="Phone Bill",
            amount=150000,
            category="Bills & Utilities",
            payment_method="Bank Transfer",
            day_of_month=day_today,
        )

        # Before marking paid, should appear in due_today
        due_today = self.manager.get_due_today()
        self.assertEqual(len(due_today), 1)

        # Mark as paid
        self.manager.mark_paid(bill_id)

        # After marking paid, should NOT appear in due_today
        due_today = self.manager.get_due_today()
        self.assertEqual(len(due_today), 0)

        # Verify last_paid is set
        bills = self.manager.list_recurring()
        self.assertEqual(len(bills), 1)
        bill = bills[0]
        expected_last_paid = today.strftime("%Y-%m")
        self.assertEqual(bill["last_paid"], expected_last_paid)

    def test_persistence(self):
        """Test that data persists across instances."""
        bill_id = self.manager.add_recurring(
            name="Water Bill",
            amount=250000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=20,
        )

        # Create new manager instance with same path
        manager2 = RecurringManager(str(self.data_path))
        bills = manager2.list_recurring()

        self.assertEqual(len(bills), 1)
        self.assertEqual(bills[0]["name"], "Water Bill")
        self.assertEqual(bills[0]["id"], bill_id)

    def test_json_file_format(self):
        """Test that JSON file is properly formatted."""
        self.manager.add_recurring(
            name="Rent",
            amount=2000000,
            category="Housing",
            payment_method="Bank Transfer",
            day_of_month=1,
        )

        # Read raw JSON file
        with open(self.data_path) as f:
            data = json.load(f)

        self.assertIsInstance(data, dict)
        self.assertIn("bills", data)
        self.assertEqual(len(data["bills"]), 1)

        bill = data["bills"][0]
        self.assertIn("id", bill)
        self.assertIn("name", bill)
        self.assertIn("amount", bill)
        self.assertIn("category", bill)
        self.assertIn("payment_method", bill)
        self.assertIn("day_of_month", bill)
        self.assertIn("active", bill)
        self.assertIn("last_paid", bill)

    def test_thread_safety(self):
        """Test thread-safe concurrent access."""
        results = []

        def add_bill(i):
            bill_id = self.manager.add_recurring(
                name=f"Bill {i}",
                amount=100000 + i * 10000,
                category="Bills & Utilities",
                payment_method="Cash",
                day_of_month=(i % 28) + 1,
            )
            results.append(bill_id)

        threads = [threading.Thread(target=add_bill, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        bills = self.manager.list_recurring()
        self.assertEqual(len(bills), 5)
        self.assertEqual(len(results), 5)

    def test_get_bill_by_id(self):
        """Test retrieving a bill by ID."""
        bill_id = self.manager.add_recurring(
            name="Gas Bill",
            amount=200000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=5,
        )

        bill = self.manager.get_bill_by_id(bill_id)
        self.assertIsNotNone(bill)
        assert bill is not None
        self.assertEqual(bill["name"], "Gas Bill")
        self.assertEqual(bill["id"], bill_id)

    def test_get_bill_by_id_not_found(self):
        """Test retrieving a non-existent bill."""
        bill = self.manager.get_bill_by_id("nonexistent-id")
        self.assertIsNone(bill)


if __name__ == "__main__":
    unittest.main()
