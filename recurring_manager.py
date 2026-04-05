import calendar
import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import local_now

# Fields that can be updated via update_recurring()
UPDATABLE_FIELDS = {"name", "amount", "category", "payment_method", "day_of_month", "active"}


class RecurringManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        if not os.path.exists(self.data_path):
            with self.lock:
                if not os.path.exists(self.data_path):
                    self._save({"bills": []})

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_path):
            return {"bills": []}
        with open(self.data_path) as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]) -> None:
        with open(self.data_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _effective_day(day_of_month: int, year: int, month: int) -> int:
        """Return the effective day for a bill in a given month.

        If day_of_month > last day of month (e.g., day 31 in February),
        use the last day of that month instead.
        """
        last_day = calendar.monthrange(year, month)[1]
        return min(day_of_month, last_day)

    def add_recurring(
        self,
        name: str,
        amount: float,
        category: str,
        payment_method: str,
        day_of_month: int,
    ) -> str:
        with self.lock:
            data = self._load()
            bill_id = str(uuid.uuid4())
            bill = {
                "id": bill_id,
                "name": name,
                "amount": amount,
                "category": category,
                "payment_method": payment_method,
                "day_of_month": day_of_month,
                "active": True,
                "last_paid": None,
            }
            data["bills"].append(bill)
            self._save(data)
        return bill_id

    def remove_recurring(self, bill_id: str) -> bool:
        with self.lock:
            data = self._load()
            original_count = len(data["bills"])
            data["bills"] = [b for b in data["bills"] if b["id"] != bill_id]
            self._save(data)
        return len(data["bills"]) < original_count

    def update_recurring(self, bill_id: str, **kwargs: Any) -> bool:
        """Update any fields of a recurring bill.

        Allowed fields: name, amount, category, payment_method, day_of_month, active.
        Returns True if the bill was found and updated, False otherwise.
        """
        invalid_fields = set(kwargs.keys()) - UPDATABLE_FIELDS
        if invalid_fields:
            raise ValueError(f"Cannot update field(s): {invalid_fields}. Allowed: {UPDATABLE_FIELDS}")

        with self.lock:
            data = self._load()
            found = False
            for bill in data["bills"]:
                if bill["id"] == bill_id:
                    for field, value in kwargs.items():
                        bill[field] = value
                    found = True
                    break
            if found:
                self._save(data)
        return found

    def list_recurring(self) -> List[Dict[str, Any]]:
        with self.lock:
            data = self._load()
        return data["bills"]

    def get_bill_by_id(self, bill_id: str) -> Optional[Dict[str, Any]]:
        bills = self.list_recurring()
        for bill in bills:
            if bill["id"] == bill_id:
                return bill
        return None

    def get_due_today(self) -> List[Dict[str, Any]]:
        today = local_now()
        today_day = today.day
        today_month = today.strftime("%Y-%m")

        with self.lock:
            data = self._load()

        due_bills = []
        for bill in data["bills"]:
            if not bill["active"]:
                continue
            effective_day = self._effective_day(bill["day_of_month"], today.year, today.month)
            if effective_day == today_day:
                if bill["last_paid"] != today_month:
                    due_bills.append(bill)

        return due_bills

    def get_overdue(self) -> List[Dict[str, Any]]:
        """Return active bills that should have been paid this month but weren't.

        A bill is overdue if:
        - active == True
        - effective day_of_month < today.day  (due date has already passed this month)
        - last_paid != current YYYY-MM  (not yet paid this month)
        """
        today = local_now()
        today_day = today.day
        current_month = today.strftime("%Y-%m")

        with self.lock:
            data = self._load()

        overdue = []
        for bill in data["bills"]:
            if not bill["active"]:
                continue
            effective_day = self._effective_day(bill["day_of_month"], today.year, today.month)
            # Past due: effective day is strictly before today AND not paid this month
            if effective_day < today_day and bill["last_paid"] != current_month:
                overdue.append(bill)

        return overdue

    def get_upcoming(self, days: int = 7) -> List[Dict[str, Any]]:
        """Return active bills due within the next `days` calendar days.

        Handles month boundary: if today is, e.g., the 28th and days=7,
        bills due on the 1st–4th of next month will also be included.
        """
        today = local_now().date()
        upcoming_dates = {today + timedelta(days=i) for i in range(1, days + 1)}

        with self.lock:
            data = self._load()

        upcoming = []
        seen_ids: set = set()
        for bill in data["bills"]:
            if not bill["active"]:
                continue
            if bill["id"] in seen_ids:
                continue

            for target_date in upcoming_dates:
                effective_day = self._effective_day(bill["day_of_month"], target_date.year, target_date.month)
                if effective_day == target_date.day:
                    # Check not already paid for that month
                    target_month = target_date.strftime("%Y-%m")
                    if bill["last_paid"] != target_month:
                        upcoming.append(bill)
                        seen_ids.add(bill["id"])
                        break

        return upcoming

    def mark_paid(self, bill_id: str) -> bool:
        today = local_now()
        current_month = today.strftime("%Y-%m")

        with self.lock:
            data = self._load()
            found = False
            for bill in data["bills"]:
                if bill["id"] == bill_id:
                    bill["last_paid"] = current_month
                    found = True
                    break
            if found:
                self._save(data)
        return found

    def is_paid_this_month(self, bill_id: str) -> bool:
        """Return True if the bill has been paid in the current calendar month."""
        today = local_now()
        current_month = today.strftime("%Y-%m")
        bill = self.get_bill_by_id(bill_id)
        if bill is None:
            return False
        return bill["last_paid"] == current_month
