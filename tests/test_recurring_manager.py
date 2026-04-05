import calendar
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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

    def test_update_recurring(self):
        bill_id = self.manager.add_recurring(
            name="Old Name",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=10,
        )

        result = self.manager.update_recurring(bill_id, name="New Name", amount=200000)
        self.assertTrue(result)

        bill = self.manager.get_bill_by_id(bill_id)
        assert bill is not None
        self.assertEqual(bill["name"], "New Name")
        self.assertEqual(bill["amount"], 200000)
        self.assertEqual(bill["day_of_month"], 10)

    def test_update_recurring_not_found(self):
        result = self.manager.update_recurring("nonexistent-id", name="X")
        self.assertFalse(result)

    def test_update_recurring_invalid_field(self):
        bill_id = self.manager.add_recurring(
            name="Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=5,
        )
        with self.assertRaises(ValueError):
            self.manager.update_recurring(bill_id, last_paid="2026-04")

    def test_update_recurring_deactivate(self):
        bill_id = self.manager.add_recurring(
            name="Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=5,
        )
        self.manager.update_recurring(bill_id, active=False)
        bill = self.manager.get_bill_by_id(bill_id)
        assert bill is not None
        self.assertFalse(bill["active"])

    def test_get_overdue(self):
        today = local_now()
        if today.day <= 1:
            self.skipTest("Cannot test overdue on day 1 of month")

        past_day = today.day - 1

        overdue_id = self.manager.add_recurring(
            name="Overdue Bill",
            amount=300000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=past_day,
        )

        today_id = self.manager.add_recurring(
            name="Due Today",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=today.day,
        )

        overdue = self.manager.get_overdue()
        overdue_ids = [b["id"] for b in overdue]
        self.assertIn(overdue_id, overdue_ids)
        self.assertNotIn(today_id, overdue_ids)

    def test_get_overdue_paid_not_returned(self):
        today = local_now()
        if today.day <= 1:
            self.skipTest("Cannot test overdue on day 1 of month")

        past_day = today.day - 1
        bill_id = self.manager.add_recurring(
            name="Paid Bill",
            amount=300000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=past_day,
        )
        self.manager.mark_paid(bill_id)

        overdue = self.manager.get_overdue()
        self.assertNotIn(bill_id, [b["id"] for b in overdue])

    def test_get_overdue_inactive_not_returned(self):
        today = local_now()
        if today.day <= 1:
            self.skipTest("Cannot test overdue on day 1 of month")

        past_day = today.day - 1
        bill_id = self.manager.add_recurring(
            name="Inactive Bill",
            amount=300000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=past_day,
        )
        self.manager.update_recurring(bill_id, active=False)

        overdue = self.manager.get_overdue()
        self.assertNotIn(bill_id, [b["id"] for b in overdue])

    def test_day_31_handling_get_due_today(self):
        from datetime import date as _date

        fake_date = _date(2026, 2, 28)
        fake_dt = datetime(2026, 2, 28, 12, 0, 0)

        with patch("recurring_manager.local_now", return_value=fake_dt):
            manager = RecurringManager(str(self.data_path))

            bill_id = manager.add_recurring(
                name="Day 31 Bill",
                amount=200000,
                category="Bills & Utilities",
                payment_method="Cash",
                day_of_month=31,
            )

            due = manager.get_due_today()
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0]["id"], bill_id)

    def test_day_31_handling_get_overdue(self):
        fake_dt = datetime(2026, 3, 31, 12, 0, 0)

        with patch("recurring_manager.local_now", return_value=fake_dt):
            manager = RecurringManager(str(self.data_path))

            overdue_id = manager.add_recurring(
                name="Day 30 Overdue",
                amount=200000,
                category="Bills & Utilities",
                payment_method="Cash",
                day_of_month=30,
            )
            not_overdue_id = manager.add_recurring(
                name="Due Last Day (31)",
                amount=100000,
                category="Bills & Utilities",
                payment_method="Cash",
                day_of_month=31,
            )

            overdue = manager.get_overdue()
            overdue_ids = [b["id"] for b in overdue]
            self.assertIn(overdue_id, overdue_ids)
            self.assertNotIn(not_overdue_id, overdue_ids)

    def test_get_upcoming(self):
        today = local_now()
        tomorrow_day = (today + __import__("datetime").timedelta(days=1)).day
        in_3_days_day = (today + __import__("datetime").timedelta(days=3)).day

        bill_tomorrow_id = self.manager.add_recurring(
            name="Tomorrow Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=tomorrow_day,
        )
        bill_in_3_id = self.manager.add_recurring(
            name="3-Day Bill",
            amount=200000,
            category="Bills & Utilities",
            payment_method="Cash",
            day_of_month=in_3_days_day,
        )

        upcoming = self.manager.get_upcoming(days=7)
        upcoming_ids = [b["id"] for b in upcoming]
        self.assertIn(bill_tomorrow_id, upcoming_ids)
        self.assertIn(bill_in_3_id, upcoming_ids)

    def test_get_upcoming_excludes_paid(self):
        today = local_now()
        tomorrow = today + __import__("datetime").timedelta(days=1)
        tomorrow_day = tomorrow.day
        tomorrow_month = tomorrow.strftime("%Y-%m")

        bill_id = self.manager.add_recurring(
            name="Paid Upcoming Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=tomorrow_day,
        )

        with self.lock_and_set_last_paid(bill_id, tomorrow_month):
            upcoming = self.manager.get_upcoming(days=3)
            self.assertNotIn(bill_id, [b["id"] for b in upcoming])

    def lock_and_set_last_paid(self, bill_id, month_str):
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            with self.manager.lock:
                data = self.manager._load()
                for b in data["bills"]:
                    if b["id"] == bill_id:
                        b["last_paid"] = month_str
                self.manager._save(data)
            yield

        return _ctx()

    def test_is_paid_this_month_true(self):
        bill_id = self.manager.add_recurring(
            name="Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=5,
        )
        self.manager.mark_paid(bill_id)
        self.assertTrue(self.manager.is_paid_this_month(bill_id))

    def test_is_paid_this_month_false(self):
        bill_id = self.manager.add_recurring(
            name="Unpaid Bill",
            amount=100000,
            category="Housing",
            payment_method="Cash",
            day_of_month=5,
        )
        self.assertFalse(self.manager.is_paid_this_month(bill_id))

    def test_is_paid_this_month_nonexistent(self):
        self.assertFalse(self.manager.is_paid_this_month("nonexistent-id"))


if __name__ == "__main__":
    unittest.main()
