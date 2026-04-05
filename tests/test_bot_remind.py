import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import bot
from recurring_manager import RecurringManager


FIXTURE_WORKBOOK = Path(__file__).resolve().parents[1] / "Financial_Tracker.xlsx"


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class FakeQuery:
    def __init__(self, data, user_id=123):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = FakeMessage()
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


def _make_update_with_message(text="", user_id=123):
    msg = FakeMessage(text)
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=msg,
        message=msg,
        callback_query=None,
    )


def _make_context(user_data=None):
    return SimpleNamespace(
        user_data=user_data if user_data is not None else {},
        bot_data={},
        args=[],
    )


class RemindCmdTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.recurring_path = Path(self.temp_dir.name) / "recurring_bills.json"
        self.original_recurring_path = bot.RECURRING_PATH
        self.original_is_user_allowed = bot.is_user_allowed
        bot.RECURRING_PATH = str(self.recurring_path)
        bot.is_user_allowed = lambda _uid: True

    def tearDown(self):
        bot.RECURRING_PATH = self.original_recurring_path
        bot.is_user_allowed = self.original_is_user_allowed
        self.temp_dir.cleanup()

    async def test_remind_cmd_empty(self):
        update = _make_update_with_message()
        context = _make_context()
        await bot.remind_cmd(update, context)
        self.assertTrue(update.message.replies)
        text, _ = update.message.replies[0]
        self.assertIn("Tidak ada tagihan rutin", text)

    async def test_remind_cmd_with_bills(self):
        rm = RecurringManager(str(self.recurring_path))
        rm.add_recurring("Listrik PLN", 150000, "Bills & Utilities", "Cash", 5)
        update = _make_update_with_message()
        context = _make_context()
        await bot.remind_cmd(update, context)
        self.assertTrue(update.message.replies)
        text, _ = update.message.replies[0]
        self.assertIn("Listrik PLN", text)

    async def test_remind_name_step(self):
        update = _make_update_with_message("Listrik PLN")
        context = _make_context()
        result = await bot.remind_name(update, context)
        self.assertEqual(result, bot.REMIND_AMOUNT)
        self.assertEqual(context.user_data["remind_name"], "Listrik PLN")

    async def test_remind_name_empty(self):
        update = _make_update_with_message("")
        context = _make_context()
        result = await bot.remind_name(update, context)
        self.assertEqual(result, bot.REMIND_NAME)

    async def test_remind_amount_step(self):
        update = _make_update_with_message("150000")
        context = _make_context()
        result = await bot.remind_amount(update, context)
        self.assertEqual(result, bot.REMIND_DAY)
        self.assertEqual(context.user_data["remind_amount"], 150000.0)

    async def test_remind_amount_invalid(self):
        update = _make_update_with_message("tidak valid")
        context = _make_context()
        result = await bot.remind_amount(update, context)
        self.assertEqual(result, bot.REMIND_AMOUNT)

    async def test_remind_day_step(self):
        update = _make_update_with_message("5")
        context = _make_context({"remind_name": "Listrik", "remind_amount": 150000})
        result = await bot.remind_day(update, context)
        self.assertEqual(result, bot.REMIND_CATEGORY)
        self.assertEqual(context.user_data["remind_day"], 5)

    async def test_remind_day_invalid(self):
        update = _make_update_with_message("99")
        context = _make_context()
        result = await bot.remind_day(update, context)
        self.assertEqual(result, bot.REMIND_DAY)

    async def test_remind_confirm_yes(self):
        query = FakeQuery("remind_confirm_yes")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context(
            {
                "remind_name": "Listrik PLN",
                "remind_amount": 150000.0,
                "remind_day": 5,
                "remind_category": "Bills & Utilities",
            }
        )
        from telegram.ext import ConversationHandler

        result = await bot.remind_confirm(update, context)
        self.assertEqual(result, ConversationHandler.END)
        self.assertTrue(query.edits)
        self.assertIn("berhasil disimpan", query.edits[0][0])

        rm = RecurringManager(str(self.recurring_path))
        bills = rm.list_recurring()
        self.assertEqual(len(bills), 1)
        self.assertEqual(bills[0]["name"], "Listrik PLN")
        self.assertEqual(bills[0]["amount"], 150000.0)

    async def test_remind_confirm_no(self):
        query = FakeQuery("remind_confirm_no")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context(
            {
                "remind_name": "Listrik PLN",
                "remind_amount": 150000.0,
                "remind_day": 5,
                "remind_category": "Bills & Utilities",
            }
        )
        from telegram.ext import ConversationHandler

        result = await bot.remind_confirm(update, context)
        self.assertEqual(result, ConversationHandler.END)
        self.assertIn("Dibatalkan", query.edits[0][0])

        rm = RecurringManager(str(self.recurring_path))
        self.assertEqual(len(rm.list_recurring()), 0)


class HandleBillActionTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        from excel_manager import ExcelManager

        self.manager = ExcelManager(self.workbook_path)

        self.recurring_path = Path(self.temp_dir.name) / "recurring_bills.json"
        self.original_recurring_path = bot.RECURRING_PATH
        self.original_excel = bot.excel
        self.original_is_user_allowed = bot.is_user_allowed
        bot.RECURRING_PATH = str(self.recurring_path)
        bot.excel = self.manager
        bot.is_user_allowed = lambda _uid: True

    def tearDown(self):
        bot.RECURRING_PATH = self.original_recurring_path
        bot.excel = self.original_excel
        bot.is_user_allowed = self.original_is_user_allowed
        self.temp_dir.cleanup()

    async def test_pay_bill_action(self):
        rm = RecurringManager(str(self.recurring_path))
        bill_id = rm.add_recurring("Listrik PLN", 150000, "Bills & Utilities", "Cash", 5)

        query = FakeQuery(f"pay_bill:{bill_id}")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context()
        context.bot_data = {"excel_manager": self.manager}

        await bot.handle_bill_action(update, context)

        self.assertTrue(query.edits)
        self.assertIn("sudah dibayar", query.edits[0][0])

        from config import local_now

        current_month = local_now().strftime("%Y-%m")
        updated_bill = rm.get_bill_by_id(bill_id)
        self.assertEqual(updated_bill["last_paid"], current_month)

    async def test_skip_bill_action(self):
        rm = RecurringManager(str(self.recurring_path))
        bill_id = rm.add_recurring("Internet Indihome", 350000, "Bills & Utilities", "Cash", 10)

        query = FakeQuery(f"skip_bill:{bill_id}")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context()

        await bot.handle_bill_action(update, context)

        self.assertTrue(query.edits)
        self.assertIn("dilewati", query.edits[0][0])

        from config import local_now

        current_month = local_now().strftime("%Y-%m")
        updated_bill = rm.get_bill_by_id(bill_id)
        self.assertEqual(updated_bill["last_paid"], current_month)

    async def test_pay_bill_not_found(self):
        query = FakeQuery("pay_bill:nonexistent-id")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context()

        await bot.handle_bill_action(update, context)
        self.assertIn("tidak ditemukan", query.edits[0][0])

    async def test_skip_bill_not_found(self):
        query = FakeQuery("skip_bill:nonexistent-id")
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            callback_query=query,
            message=query.message,
        )
        context = _make_context()

        await bot.handle_bill_action(update, context)
        self.assertIn("tidak ditemukan", query.edits[0][0])


class SendDailyRemindersTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.recurring_path = Path(self.temp_dir.name) / "recurring_bills.json"
        self.original_recurring_path = bot.RECURRING_PATH
        bot.RECURRING_PATH = str(self.recurring_path)

    def tearDown(self):
        bot.RECURRING_PATH = self.original_recurring_path
        self.temp_dir.cleanup()

    async def test_send_daily_reminders_no_bills(self):
        sent_messages = []

        async def fake_send(chat_id, text, **kwargs):
            sent_messages.append((chat_id, text))

        fake_bot = MagicMock()
        fake_bot.send_message = AsyncMock(side_effect=fake_send)
        context = SimpleNamespace(bot=fake_bot)

        from config import Settings

        fake_settings = Settings(
            bot_token=None,
            excel_path=bot.settings.excel_path,
            allowed_user_ids=(999,),
            timezone="Asia/Jakarta",
        )
        with patch("bot.settings", fake_settings):
            await bot.send_daily_reminders(context)

        self.assertEqual(len(sent_messages), 0)

    async def test_send_daily_reminders_with_due_bill(self):
        sent_messages = []

        async def fake_send(chat_id, text, **kwargs):
            sent_messages.append((chat_id, text))

        from config import local_now, Settings

        today_day = local_now().day

        rm = RecurringManager(str(self.recurring_path))
        rm.add_recurring("Listrik PLN", 150000, "Bills & Utilities", "Cash", today_day)

        fake_bot = MagicMock()
        fake_bot.send_message = AsyncMock(side_effect=fake_send)
        context = SimpleNamespace(bot=fake_bot)

        fake_settings = Settings(
            bot_token=None,
            excel_path=bot.settings.excel_path,
            allowed_user_ids=(999,),
            timezone="Asia/Jakarta",
        )
        with patch("bot.settings", fake_settings):
            await bot.send_daily_reminders(context)

        self.assertEqual(len(sent_messages), 1)
        self.assertIn("Listrik PLN", sent_messages[0][1])


if __name__ == "__main__":
    unittest.main()
