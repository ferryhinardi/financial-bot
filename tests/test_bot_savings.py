import io
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bot
from excel_manager import ExcelManager


FIXTURE_WORKBOOK = Path(__file__).resolve().parents[1] / "Financial_Tracker.xlsx"


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies = []
        self.photos = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))

    async def reply_photo(self, photo=None, **kwargs):
        self.photos.append((photo, kwargs))


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


def make_context(manager):
    return SimpleNamespace(
        args=[],
        user_data={},
        bot_data={"excel_manager": manager},
    )


class SavingsCmdTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.milestones_path = Path(self.temp_dir.name) / "savings_milestones.json"
        self.manager = ExcelManager(self.workbook_path, milestones_path=self.milestones_path)
        self.original_excel = bot.excel
        self.original_is_user_allowed = bot.is_user_allowed
        bot.excel = self.manager
        bot.is_user_allowed = lambda _: True

    def tearDown(self):
        bot.excel = self.original_excel
        bot.is_user_allowed = self.original_is_user_allowed
        self.temp_dir.cleanup()

    async def test_savings_cmd_sends_text_message(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        await bot.savings_cmd(update, context)

        self.assertTrue(message.replies, "Expected at least one text reply")
        self.assertIn("Savings Overview", message.replies[0][0])

    async def test_savings_cmd_sends_chart(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        fake_chart_bytes = b"fake_png_bytes"
        with patch("bot.ChartGenerator") as MockChart:
            MockChart.return_value.savings_progress_chart.return_value = fake_chart_bytes
            await bot.savings_cmd(update, context)

        self.assertTrue(message.photos, "Expected chart photo to be sent")
        photo_arg, _ = message.photos[0]
        self.assertIsInstance(photo_arg, io.BytesIO)

    async def test_savings_cmd_shows_progress_bar_when_goal_set(self):
        self.manager.add_savings(
            amount=5_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
            goal=10_000_000,
        )

        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        with patch("bot.ChartGenerator"):
            await bot.savings_cmd(update, context)

        self.assertIn("\u2588", message.replies[0][0])

    async def test_savings_cmd_shows_eta_when_deposits_exist(self):
        self.manager.add_savings(
            amount=2_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
            goal=10_000_000,
        )

        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        with patch("bot.ChartGenerator"):
            await bot.savings_cmd(update, context)

        self.assertIn("ETA", message.replies[0][0])

    async def test_savings_cmd_shows_milestones_when_hit(self):
        self.manager.add_savings(
            amount=5_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
            goal=10_000_000,
        )

        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        with patch("bot.ChartGenerator"):
            await bot.savings_cmd(update, context)

        self.assertIn("Milestone", message.replies[0][0])

    async def test_savings_cmd_shows_total_savings(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        with patch("bot.ChartGenerator"):
            await bot.savings_cmd(update, context)

        self.assertIn("Total Savings", message.replies[0][0])

    async def test_savings_cmd_chart_error_does_not_crash(self):
        message = FakeMessage()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )
        context = make_context(self.manager)

        with patch("bot.ChartGenerator") as MockChart:
            MockChart.return_value.savings_progress_chart.side_effect = Exception("chart error")
            await bot.savings_cmd(update, context)

        self.assertTrue(message.replies)
        self.assertFalse(message.photos)


class SaveAccountMilestoneTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.milestones_path = Path(self.temp_dir.name) / "savings_milestones.json"
        self.manager = ExcelManager(self.workbook_path, milestones_path=self.milestones_path)
        self.original_excel = bot.excel
        self.original_is_user_allowed = bot.is_user_allowed
        bot.excel = self.manager
        bot.is_user_allowed = lambda _: True

    def tearDown(self):
        bot.excel = self.original_excel
        bot.is_user_allowed = self.original_is_user_allowed
        self.temp_dir.cleanup()

    async def test_save_deposit_records_successfully(self):
        query = FakeQuery("sacct_Emergency Fund")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 500_000,
                "save_type": "Deposit",
            },
            bot_data={"excel_manager": self.manager},
        )

        await bot.save_account(update, context)

        self.assertTrue(query.edits, "Expected edit_message_text to be called")
        self.assertIn("Savings recorded", query.edits[-1][0])

    async def test_save_deposit_triggers_milestone_celebration(self):
        self.manager.add_savings(
            amount=2_500_000,
            account="Emergency Fund",
            transaction_type="Deposit",
            goal=10_000_000,
        )

        query = FakeQuery("sacct_Emergency Fund")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 100_000,
                "save_type": "Deposit",
            },
            bot_data={"excel_manager": self.manager},
        )

        mock_milestone = {
            "account": "Emergency Fund",
            "milestone_pct": 25,
            "message": "\U0001f389 Hebat! Kamu sudah mencapai 25% dari targetmu!",
        }
        with patch.object(self.manager, "check_milestone", return_value=mock_milestone):
            await bot.save_account(update, context)

        self.assertTrue(query.message.replies, "Expected celebration message to be sent")
        self.assertIn("25%", query.message.replies[0][0])

    async def test_save_withdrawal_skips_milestone_check(self):
        self.manager.add_savings(
            amount=1_000_000,
            account="Emergency Fund",
            transaction_type="Deposit",
        )

        query = FakeQuery("sacct_Emergency Fund")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 100_000,
                "save_type": "Withdrawal",
            },
            bot_data={"excel_manager": self.manager},
        )

        with patch.object(self.manager, "check_milestone") as mock_check:
            await bot.save_account(update, context)

        mock_check.assert_not_called()

    async def test_save_no_milestone_no_celebration(self):
        query = FakeQuery("sacct_Vacation")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 100_000,
                "save_type": "Deposit",
            },
            bot_data={"excel_manager": self.manager},
        )

        with patch.object(self.manager, "check_milestone", return_value=None):
            await bot.save_account(update, context)

        self.assertFalse(query.message.replies, "Expected no celebration when no milestone")

    async def test_save_milestone_check_error_does_not_crash(self):
        query = FakeQuery("sacct_Emergency Fund")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 100_000,
                "save_type": "Deposit",
            },
            bot_data={"excel_manager": self.manager},
        )

        with patch.object(self.manager, "check_milestone", side_effect=Exception("db error")):
            await bot.save_account(update, context)

        self.assertTrue(query.edits)
        self.assertIn("Savings recorded", query.edits[-1][0])

    async def test_save_invalid_account_returns_error(self):
        query = FakeQuery("sacct_NonExistentAccount")
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(
            user_data={
                "save_amount": 100_000,
                "save_type": "Deposit",
            },
            bot_data={"excel_manager": self.manager},
        )

        await bot.save_account(update, context)

        self.assertTrue(query.edits, "Expected error message via edit_message_text")
        self.assertIn("Could not record savings entry", query.edits[0][0])


if __name__ == "__main__":
    unittest.main()
