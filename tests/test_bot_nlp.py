"""
Tests for NLP message handler and /nlp command.
Uses mocked NLPParser and minimal bot internals.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import bot
from excel_manager import ExcelManager


FIXTURE_WORKBOOK = Path(__file__).resolve().parents[1] / "Financial_Tracker.xlsx"


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


def _make_update(text="", user_id=1):
    """Build a minimal Update-like object for handler tests."""
    message = FakeMessage(text)
    user = SimpleNamespace(id=user_id)
    return SimpleNamespace(
        message=message,
        effective_message=message,
        effective_user=user,
        callback_query=None,
    )


def _make_context(args=None, excel_manager=None):
    ctx = SimpleNamespace(
        args=args or [],
        user_data={},
        bot_data={"excel_manager": excel_manager} if excel_manager else {},
    )
    return ctx


class NlpCmdTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the /nlp command handler."""

    def setUp(self):
        bot.nlp_state["enabled"] = False
        self._orig_is_authorized = bot.is_authorized
        bot.is_authorized = lambda _upd: True

    def tearDown(self):
        bot.nlp_state["enabled"] = False
        bot.is_authorized = self._orig_is_authorized

    async def test_nlp_on(self):
        update = _make_update()
        ctx = _make_context(args=["on"])
        await bot.nlp_cmd(update, ctx)
        self.assertTrue(bot.nlp_state["enabled"])
        self.assertIn("aktif", update.message.replies[0][0].lower())

    async def test_nlp_off(self):
        bot.nlp_state["enabled"] = True
        update = _make_update()
        ctx = _make_context(args=["off"])
        await bot.nlp_cmd(update, ctx)
        self.assertFalse(bot.nlp_state["enabled"])
        self.assertIn("nonaktif", update.message.replies[0][0].lower())

    async def test_nlp_status_off(self):
        update = _make_update()
        ctx = _make_context(args=[])
        await bot.nlp_cmd(update, ctx)
        reply_text = update.message.replies[0][0]
        self.assertIn("nonaktif", reply_text.lower())

    async def test_nlp_status_on(self):
        bot.nlp_state["enabled"] = True
        update = _make_update()
        ctx = _make_context(args=[])
        await bot.nlp_cmd(update, ctx)
        reply_text = update.message.replies[0][0]
        self.assertIn("aktif", reply_text.lower())

    async def test_nlp_unknown_arg(self):
        update = _make_update()
        ctx = _make_context(args=["maybe"])
        await bot.nlp_cmd(update, ctx)
        reply_text = update.message.replies[0][0]
        self.assertIn("tidak dikenal", reply_text.lower())


class NlpMessageHandlerTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the NLP free-text message handler."""

    def setUp(self):
        bot.nlp_state["enabled"] = False
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.manager = ExcelManager(self.workbook_path)
        self.original_excel = bot.excel
        bot.excel = self.manager
        self._orig_is_authorized = bot.is_authorized
        bot.is_authorized = lambda _upd: True

    def tearDown(self):
        bot.nlp_state["enabled"] = False
        bot.excel = self.original_excel
        bot.is_authorized = self._orig_is_authorized
        self.temp_dir.cleanup()

    async def test_does_nothing_when_nlp_off(self):
        """When NLP is off, handler should return without sending any message."""
        bot.nlp_state["enabled"] = False
        update = _make_update("beli makan 50k")
        ctx = _make_context(excel_manager=self.manager)
        result = await bot.nlp_message_handler(update, ctx)
        self.assertEqual(update.message.replies, [])
        self.assertIsNone(result)

    async def test_skips_commands(self):
        """Messages starting with '/' should be ignored."""
        bot.nlp_state["enabled"] = True
        update = _make_update("/help")
        ctx = _make_context(excel_manager=self.manager)
        result = await bot.nlp_message_handler(update, ctx)
        self.assertEqual(update.message.replies, [])

    async def test_skips_short_messages(self):
        """Messages with len <= 5 should be ignored."""
        bot.nlp_state["enabled"] = True
        update = _make_update("ok")
        ctx = _make_context(excel_manager=self.manager)
        result = await bot.nlp_message_handler(update, ctx)
        self.assertEqual(update.message.replies, [])

    async def test_error_when_nullclaw_not_configured(self):
        """When NULLCLAW_PATH not set, should send error and raise ApplicationHandlerStop."""
        bot.nlp_state["enabled"] = True
        update = _make_update("beli makan siang 50 ribu")
        ctx = _make_context(excel_manager=self.manager)

        from telegram.ext import ApplicationHandlerStop

        with patch.dict("os.environ", {"NULLCLAW_PATH": ""}, clear=False):
            import os

            os.environ.pop("NULLCLAW_PATH", None)
            with self.assertRaises(ApplicationHandlerStop):
                await bot.nlp_message_handler(update, ctx)

        self.assertTrue(any("NLP" in r[0] or "dikonfigurasi" in r[0] for r in update.message.replies))

    async def test_high_confidence_shows_preview_with_keyboard(self):
        """High confidence result shows preview and confirmation keyboard."""
        bot.nlp_state["enabled"] = True
        update = _make_update("beli makan siang 50 ribu")
        ctx = _make_context(excel_manager=self.manager)

        mock_result = {
            "type": "spending",
            "amount": 50000,
            "category": "Food & Groceries",
            "description": "makan siang",
            "confidence": 0.95,
        }

        from telegram.ext import ApplicationHandlerStop

        with patch.dict("os.environ", {"NULLCLAW_PATH": "/fake/nullclaw"}):
            with patch("nlp_parser.NLPParser") as MockParser:
                mock_instance = MockParser.return_value
                mock_instance.parse_financial_message.return_value = mock_result
                with self.assertRaises(ApplicationHandlerStop):
                    await bot.nlp_message_handler(update, ctx)

        self.assertTrue(len(update.message.replies) >= 2)
        preview_reply = update.message.replies[-1]
        preview_text = preview_reply[0]
        self.assertIn("mendeteksi transaksi", preview_text.lower())
        self.assertIn("50,000", preview_text)
        self.assertIn("Food & Groceries", preview_text)
        self.assertIn("reply_markup", preview_reply[1])
        keyboard = preview_reply[1]["reply_markup"]
        self.assertIsNotNone(keyboard)

    async def test_low_confidence_asks_clarification(self):
        """Low confidence result asks for clarification."""
        bot.nlp_state["enabled"] = True
        update = _make_update("something something money")
        ctx = _make_context(excel_manager=self.manager)

        mock_result = {
            "type": "spending",
            "amount": 10000,
            "category": "Other",
            "description": "unclear",
            "confidence": 0.3,
        }

        from telegram.ext import ApplicationHandlerStop

        with patch.dict("os.environ", {"NULLCLAW_PATH": "/fake/nullclaw"}):
            with patch("nlp_parser.NLPParser") as MockParser:
                mock_instance = MockParser.return_value
                mock_instance.parse_financial_message.return_value = mock_result
                with self.assertRaises(ApplicationHandlerStop):
                    await bot.nlp_message_handler(update, ctx)

        clarification_replies = [r for r in update.message.replies if "Maksudnya" in r[0]]
        self.assertTrue(len(clarification_replies) > 0)


class NlpConfirmCallbackTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the NLP confirm/cancel callback handler."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.manager = ExcelManager(self.workbook_path)
        self.original_excel = bot.excel
        bot.excel = self.manager

    def tearDown(self):
        bot.excel = self.original_excel
        self.temp_dir.cleanup()

    def _make_callback_update(self, data, user_id=1):
        query = FakeQuery(data, user_id)
        return SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=user_id),
            message=None,
        )

    async def test_confirm_spending(self):
        """Confirming an NLP spending transaction records it."""
        user_id = 1
        pending_data = {
            "nlp_source": True,
            "type": "spending",
            "amount": 50000,
            "category": "Food & Groceries",
            "description": "makan siang",
        }
        key = bot._store_pending(user_id, pending_data)

        update = self._make_callback_update(f"nlp_confirm:{key}", user_id)
        ctx = _make_context(excel_manager=self.manager)

        await bot.handle_nlp_confirm(update, ctx)

        edits = update.callback_query.edits
        self.assertTrue(len(edits) > 0)
        self.assertIn("✅", edits[0][0])
        self.assertIn("Pengeluaran", edits[0][0])

    async def test_confirm_income(self):
        """Confirming an NLP income transaction records it."""
        user_id = 1
        pending_data = {
            "nlp_source": True,
            "type": "income",
            "amount": 5000000,
            "category": "Salary",
            "description": "gaji bulanan",
        }
        key = bot._store_pending(user_id, pending_data)

        update = self._make_callback_update(f"nlp_confirm:{key}", user_id)
        ctx = _make_context(excel_manager=self.manager)

        await bot.handle_nlp_confirm(update, ctx)

        edits = update.callback_query.edits
        self.assertTrue(len(edits) > 0)
        self.assertIn("✅", edits[0][0])
        self.assertIn("Pemasukan", edits[0][0])

    async def test_confirm_savings(self):
        """Confirming an NLP savings transaction records it."""
        user_id = 1
        pending_data = {
            "nlp_source": True,
            "type": "savings",
            "amount": 1000000,
            "category": "Other",
            "description": "tabungan rutin",
        }
        key = bot._store_pending(user_id, pending_data)

        update = self._make_callback_update(f"nlp_confirm:{key}", user_id)
        ctx = _make_context(excel_manager=self.manager)

        await bot.handle_nlp_confirm(update, ctx)

        edits = update.callback_query.edits
        self.assertTrue(len(edits) > 0)
        self.assertIn("✅", edits[0][0])
        self.assertIn("Tabungan", edits[0][0])

    async def test_cancel(self):
        """Cancelling an NLP transaction removes pending data."""
        user_id = 1
        pending_data = {
            "nlp_source": True,
            "type": "spending",
            "amount": 50000,
            "category": "Food & Groceries",
            "description": "test cancel",
        }
        key = bot._store_pending(user_id, pending_data)

        update = self._make_callback_update(f"nlp_cancel:{key}", user_id)
        ctx = _make_context(excel_manager=self.manager)

        await bot.handle_nlp_confirm(update, ctx)

        edits = update.callback_query.edits
        self.assertTrue(len(edits) > 0)
        self.assertIn("❌", edits[0][0])
        self.assertIn("Dibatalkan", edits[0][0])

    async def test_confirm_expired_key(self):
        """Confirming with an expired/missing key shows error."""
        update = self._make_callback_update("nlp_confirm:invalidkey123", 1)
        ctx = _make_context(excel_manager=self.manager)

        await bot.handle_nlp_confirm(update, ctx)

        edits = update.callback_query.edits
        self.assertTrue(len(edits) > 0)
        self.assertIn("expired", edits[0][0].lower())


class NlpStateTestCase(unittest.TestCase):
    """Tests for NLP state management."""

    def setUp(self):
        bot.nlp_state["enabled"] = False

    def tearDown(self):
        bot.nlp_state["enabled"] = False

    def test_default_disabled(self):
        self.assertFalse(bot.nlp_state["enabled"])

    def test_enable(self):
        bot.nlp_state["enabled"] = True
        self.assertTrue(bot.nlp_state["enabled"])

    def test_disable_after_enable(self):
        bot.nlp_state["enabled"] = True
        bot.nlp_state["enabled"] = False
        self.assertFalse(bot.nlp_state["enabled"])


if __name__ == "__main__":
    unittest.main()
