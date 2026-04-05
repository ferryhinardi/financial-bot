import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import local_now


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
            if bill["day_of_month"] == today_day:
                if bill["last_paid"] != today_month:
                    due_bills.append(bill)

        return due_bills

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
