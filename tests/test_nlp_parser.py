import json
import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from nlp_parser import NLPParser


class TestNLPParserClass(unittest.TestCase):
    def test_class_exists(self):
        parser = NLPParser(nullclaw_path="/usr/local/bin/nullclaw", openai_api_key="test-key")
        self.assertIsInstance(parser, NLPParser)

    def test_init_from_env(self):
        with patch.dict(os.environ, {"NULLCLAW_PATH": "/some/path", "OPENAI_API_KEY": "env-key"}):
            parser = NLPParser()
        self.assertEqual(parser.nullclaw_path, "/some/path")
        self.assertEqual(parser.openai_api_key, "env-key")

    def test_init_explicit_overrides_env(self):
        with patch.dict(os.environ, {"NULLCLAW_PATH": "/env/path", "OPENAI_API_KEY": "env-key"}):
            parser = NLPParser(nullclaw_path="/explicit/path", openai_api_key="explicit-key")
        self.assertEqual(parser.nullclaw_path, "/explicit/path")
        self.assertEqual(parser.openai_api_key, "explicit-key")


class TestParseResponse(unittest.TestCase):
    def setUp(self):
        self.parser = NLPParser(nullclaw_path="/usr/local/bin/nullclaw", openai_api_key="test-key")

    def test_parse_mock_response(self):
        json_str = json.dumps(
            {
                "type": "spending",
                "amount": 50000,
                "category": "Food & Groceries",
                "description": "nasi padang",
                "confidence": 0.95,
            }
        )
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 50000)
        self.assertEqual(result["category"], "Food & Groceries")
        self.assertEqual(result["description"], "nasi padang")
        self.assertAlmostEqual(result["confidence"], 0.95)

    def test_parse_amount_is_int(self):
        json_str = json.dumps(
            {
                "type": "income",
                "amount": 8000000.0,
                "category": "Salary",
                "description": "gaji bulanan",
                "confidence": 0.99,
            }
        )
        result = self.parser._parse_response(json_str)
        self.assertIsInstance(result["amount"], int)
        self.assertEqual(result["amount"], 8000000)

    def test_parse_indonesian_amount_50k(self):
        json_str = json.dumps(
            {
                "type": "spending",
                "amount": "50k",
                "category": "Food & Groceries",
                "description": "makan",
                "confidence": 0.9,
            }
        )
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["amount"], 50000)

    def test_parse_indonesian_amount_jt(self):
        json_str = json.dumps(
            {
                "type": "income",
                "amount": "8jt",
                "category": "Salary",
                "description": "gaji",
                "confidence": 0.98,
            }
        )
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["amount"], 8000000)

    def test_parse_indonesian_amount_1_5jt(self):
        json_str = json.dumps(
            {
                "type": "savings",
                "amount": "1.5jt",
                "category": "Investment",
                "description": "nabung",
                "confidence": 0.85,
            }
        )
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["amount"], 1500000)

    def test_parse_response_with_json_embedded_in_text(self):
        json_str = '{"type": "spending", "amount": 25000, "category": "Transportation", "description": "ojol", "confidence": 0.92}'
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 25000)


class TestParseFinancialMessage(unittest.TestCase):
    def setUp(self):
        self.parser = NLPParser(nullclaw_path="/usr/local/bin/nullclaw", openai_api_key="test-key")

    def test_parse_financial_message_calls_subprocess(self):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "spending",
                "amount": 50000,
                "category": "Food & Groceries",
                "description": "nasi padang",
                "confidence": 0.95,
            }
        )
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = self.parser.parse_financial_message("beli nasi padang 50rb")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertIn("nasi padang", call_args[0][0][-1])

        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 50000)
        self.assertEqual(result["category"], "Food & Groceries")
        self.assertIn("confidence", result)

    def test_parse_financial_message_result_schema(self):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "type": "income",
                "amount": 8000000,
                "category": "Salary",
                "description": "gaji",
                "confidence": 0.99,
            }
        )
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.parser.parse_financial_message("terima gaji 8 juta")

        for key in ("type", "amount", "category", "description", "confidence"):
            self.assertIn(key, result)

    def test_parse_financial_message_timeout_raises(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nullclaw", timeout=10)):
            with self.assertRaises(RuntimeError):
                self.parser.parse_financial_message("test message")

    def test_parse_financial_message_not_found_raises(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(RuntimeError) as ctx:
                self.parser.parse_financial_message("test message")
        self.assertIn("nullclaw", str(ctx.exception).lower())

    def test_parse_financial_message_no_path_raises(self):
        parser = NLPParser(nullclaw_path=None, openai_api_key="test-key")
        with self.assertRaises(RuntimeError) as ctx:
            parser.parse_financial_message("test message")
        self.assertIn("nullclaw", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
