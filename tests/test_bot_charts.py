import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

    async def reply_photo(self, **kwargs):
        self.photos.append(kwargs)


class BotChartsTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "Financial_Tracker.xlsx"
        shutil.copy2(FIXTURE_WORKBOOK, self.workbook_path)
        self.manager = ExcelManager(self.workbook_path)
        self.original_excel = bot.excel
        self.original_is_user_allowed = bot.is_user_allowed
        bot.excel = self.manager
        bot.is_user_allowed = lambda _user_id: True

    def tearDown(self):
        bot.excel = self.original_excel
        bot.is_user_allowed = self.original_is_user_allowed
        self.temp_dir.cleanup()

    def _make_update(self, message):
        return SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            effective_message=message,
            message=message,
        )

    def _make_context(self, args=None):
        return SimpleNamespace(
            args=args or [],
            user_data={},
            bot_data={"excel_manager": self.manager},
        )

    @patch("bot.ChartGenerator")
    async def test_summary_sends_chart_after_text(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.spending_pie_chart.return_value = b"fake_png_bytes"
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.summary_cmd(update, context)

        self.assertTrue(message.replies, "Should send text reply")
        self.assertTrue(message.photos, "Should send photo reply")
        mock_cg.spending_pie_chart.assert_called_once()
        args = mock_cg.spending_pie_chart.call_args[0][0]
        self.assertIn("by_category", args)
        self.assertIn("month", args)

    @patch("bot.ChartGenerator")
    async def test_budget_sends_chart_after_text(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.budget_status_chart.return_value = b"fake_png_bytes"
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.budget_cmd(update, context)

        self.assertTrue(message.replies, "Should send text reply")
        self.assertTrue(message.photos, "Should send photo reply")
        mock_cg.budget_status_chart.assert_called_once()
        budget_arg = mock_cg.budget_status_chart.call_args[0][0]
        self.assertIn("items", budget_arg)
        self.assertIn("month", budget_arg)

    @patch("bot.ChartGenerator")
    async def test_dashboard_sends_chart_after_text(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.spending_pie_chart.return_value = b"fake_png_bytes"
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.dashboard_cmd(update, context)

        self.assertTrue(message.replies, "Should send text reply")
        self.assertTrue(message.photos, "Should send photo reply")
        mock_cg.spending_pie_chart.assert_called_once()
        spending_data = mock_cg.spending_pie_chart.call_args[0][0]
        self.assertIn("by_category", spending_data)
        self.assertIn("month", spending_data)

    @patch("bot.ChartGenerator")
    async def test_summary_graceful_fallback_on_chart_error(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.spending_pie_chart.side_effect = RuntimeError("matplotlib error")
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.summary_cmd(update, context)

        self.assertTrue(message.replies, "Text reply should still be sent even if chart fails")
        self.assertEqual(len(message.photos), 0, "No photo should be sent on chart error")

    @patch("bot.ChartGenerator")
    async def test_budget_graceful_fallback_on_chart_error(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.budget_status_chart.side_effect = RuntimeError("chart error")
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.budget_cmd(update, context)

        self.assertTrue(message.replies, "Text reply should still be sent even if chart fails")
        self.assertEqual(len(message.photos), 0, "No photo should be sent on chart error")

    @patch("bot.ChartGenerator")
    async def test_dashboard_graceful_fallback_on_chart_error(self, mock_cg_class):
        mock_cg = MagicMock()
        mock_cg.spending_pie_chart.side_effect = RuntimeError("chart error")
        mock_cg_class.return_value = mock_cg

        message = FakeMessage()
        update = self._make_update(message)
        context = self._make_context()

        await bot.dashboard_cmd(update, context)

        self.assertTrue(message.replies, "Text reply should still be sent even if chart fails")
        self.assertEqual(len(message.photos), 0, "No photo should be sent on chart error")


if __name__ == "__main__":
    unittest.main()
