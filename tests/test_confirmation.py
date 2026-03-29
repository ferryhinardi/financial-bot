import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import bot


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class FakeQuery:
    def __init__(self, data, user_id):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = FakeMessage()
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class StorePendingTestCase(unittest.TestCase):
    def setUp(self):
        bot._pending_confirmations.clear()

    def tearDown(self):
        bot._pending_confirmations.clear()

    def test_store_returns_uuid_key(self):
        key = bot._store_pending(123, {"type": "spending", "amount": 50000})
        self.assertTrue(len(key) > 0)
        self.assertIn(key, bot._pending_confirmations)

    def test_retrieve_returns_data_for_correct_user(self):
        data = {"type": "spending", "amount": 50000}
        key = bot._store_pending(123, data)
        result = bot._retrieve_pending(key, 123)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 50000)

    def test_retrieve_returns_none_for_wrong_user(self):
        key = bot._store_pending(123, {"type": "spending"})
        result = bot._retrieve_pending(key, 999)
        self.assertIsNone(result)

    def test_retrieve_returns_none_for_unknown_key(self):
        result = bot._retrieve_pending("nonexistent-key", 123)
        self.assertIsNone(result)

    def test_retrieve_pops_entry(self):
        key = bot._store_pending(123, {"type": "spending"})
        bot._retrieve_pending(key, 123)
        self.assertNotIn(key, bot._pending_confirmations)

    def test_expired_entry_returns_none(self):
        key = bot._store_pending(123, {"type": "spending"})
        entry = bot._pending_confirmations[key]
        entry["ts"] = time.time() - bot._PENDING_TTL_SECONDS - 1
        result = bot._retrieve_pending(key, 123)
        self.assertIsNone(result)


class BuildPreviewTextTestCase(unittest.TestCase):
    def test_spending_preview(self):
        data = {"type": "spending", "amount": 50000, "description": "Nasi Padang", "category": "Food & Groceries"}
        text = bot._build_preview_text(data)
        self.assertIn("50", text)
        self.assertIn("Nasi Padang", text)

    def test_income_preview(self):
        data = {"type": "income", "amount": 8000000, "source": "PT ABC"}
        text = bot._build_preview_text(data)
        self.assertIn("8", text)

    def test_cc_statement_preview(self):
        data = {
            "type": "cc_statement",
            "card": "BCA Visa",
            "period": "Jan 2026",
            "transactions": [
                {"date": "2026-01-02", "description": "GRAB", "amount": 50000, "category": "Transportation"},
                {"date": "2026-01-05", "description": "SHOPEE", "amount": 100000, "category": "Shopping"},
            ],
        }
        text = bot._build_preview_text(data)
        self.assertIn("BCA Visa", text)
        self.assertIn("GRAB", text)

    def test_payslip_preview(self):
        data = {"type": "payslip", "company": "PT Traveloka", "period": "Feb 2026", "net_pay": 22719200}
        text = bot._build_preview_text(data)
        self.assertIn("Traveloka", text)

    def test_duplicate_warning_appended(self):
        data = {"type": "spending", "amount": 50000, "description": "test"}
        dupes = [{"date": "2026-01-01", "amount": 50000, "description": "test"}]
        text = bot._build_preview_text(data, duplicates=dupes)
        self.assertIn("50000", text.replace(".", "").replace(",", ""))


class BuildConfirmKeyboardTestCase(unittest.TestCase):
    def test_keyboard_has_two_buttons(self):
        keyboard = bot._build_confirm_keyboard("test-key-123")
        buttons = keyboard.inline_keyboard
        self.assertEqual(len(buttons), 1)
        self.assertEqual(len(buttons[0]), 2)
        self.assertIn("cfm_save_", buttons[0][0].callback_data)
        self.assertIn("cfm_cancel_", buttons[0][1].callback_data)


class HandleExtractionConfirmTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        bot._pending_confirmations.clear()

    def tearDown(self):
        bot._pending_confirmations.clear()

    async def test_cancel_removes_pending_and_replies(self):
        key = bot._store_pending(123, {"type": "spending", "amount": 50000})
        query = FakeQuery(f"cfm_cancel_{key}", user_id=123)
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={}, bot_data={})

        await bot.handle_extraction_confirm(update, context)

        self.assertTrue(query.edits)
        cancel_text = query.edits[0][0]
        self.assertIn("Dibatalkan", cancel_text)

    async def test_expired_key_shows_error(self):
        query = FakeQuery("cfm_save_nonexistent-key", user_id=123)
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={}, bot_data={})

        await bot.handle_extraction_confirm(update, context)

        self.assertTrue(query.edits)
        error_text = query.edits[0][0]
        self.assertTrue(
            "expired" in error_text.lower() or "kadaluarsa" in error_text.lower() or "tidak" in error_text.lower()
        )


if __name__ == "__main__":
    unittest.main()
