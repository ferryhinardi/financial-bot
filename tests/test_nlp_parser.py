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


class TestValidateOutput(unittest.TestCase):
    def setUp(self):
        self.parser = NLPParser(nullclaw_path="/usr/local/bin/nullclaw", openai_api_key="test-key")

    def _valid(self):
        return {
            "type": "spending",
            "amount": 50000,
            "category": "Food & Groceries",
            "description": "nasi padang",
            "confidence": 0.95,
        }

    def test_validate_output_passthrough(self):
        data = self._valid()
        result = self.parser.validate_output(dict(data))
        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 50000)
        self.assertEqual(result["category"], "Food & Groceries")
        self.assertAlmostEqual(result["confidence"], 0.95)

    def test_validate_output_invalid_type_defaults_to_spending(self):
        data = self._valid()
        data["type"] = "unknown"
        result = self.parser.validate_output(data)
        self.assertEqual(result["type"], "spending")

    def test_validate_output_missing_type_defaults_to_spending(self):
        data = self._valid()
        del data["type"]
        result = self.parser.validate_output(data)
        self.assertEqual(result["type"], "spending")

    def test_validate_output_zero_amount_raises(self):
        data = self._valid()
        data["amount"] = 0
        with self.assertRaises(ValueError):
            self.parser.validate_output(data)

    def test_validate_output_negative_amount_raises(self):
        data = self._valid()
        data["amount"] = -1000
        with self.assertRaises(ValueError):
            self.parser.validate_output(data)

    def test_validate_output_missing_category_defaults_to_other(self):
        data = self._valid()
        del data["category"]
        result = self.parser.validate_output(data)
        self.assertEqual(result["category"], "Other")

    def test_validate_output_empty_category_defaults_to_other(self):
        data = self._valid()
        data["category"] = "   "
        result = self.parser.validate_output(data)
        self.assertEqual(result["category"], "Other")

    def test_validate_output_confidence_clamped_high(self):
        data = self._valid()
        data["confidence"] = 1.5
        result = self.parser.validate_output(data)
        self.assertEqual(result["confidence"], 1.0)

    def test_validate_output_confidence_clamped_low(self):
        data = self._valid()
        data["confidence"] = -0.1
        result = self.parser.validate_output(data)
        self.assertEqual(result["confidence"], 0.0)

    def test_validate_output_missing_confidence_defaults_to_half(self):
        data = self._valid()
        del data["confidence"]
        result = self.parser.validate_output(data)
        self.assertAlmostEqual(result["confidence"], 0.5)

    def test_validate_output_invalid_confidence_defaults_to_half(self):
        data = self._valid()
        data["confidence"] = "high"
        result = self.parser.validate_output(data)
        self.assertAlmostEqual(result["confidence"], 0.5)

    def test_validate_output_amount_string_normalized(self):
        data = self._valid()
        data["amount"] = "50k"
        result = self.parser.validate_output(data)
        self.assertEqual(result["amount"], 50000)

    def test_validate_output_all_valid_types_pass(self):
        for tx_type in ("spending", "income", "savings"):
            data = self._valid()
            data["type"] = tx_type
            result = self.parser.validate_output(data)
            self.assertEqual(result["type"], tx_type)


class TestParseIndonesianAmountEdgeCases(unittest.TestCase):
    def _parse(self, text):
        return NLPParser.parse_indonesian_amount(text)

    def test_50k_lower(self):
        self.assertEqual(self._parse("50k"), 50000)

    def test_50K_upper(self):
        self.assertEqual(self._parse("50K"), 50000)

    def test_8jt(self):
        self.assertEqual(self._parse("8jt"), 8000000)

    def test_8JT_upper(self):
        self.assertEqual(self._parse("8JT"), 8000000)

    def test_1_5jt_decimal(self):
        self.assertEqual(self._parse("1.5jt"), 1500000)

    def test_500rb(self):
        self.assertEqual(self._parse("500rb"), 500000)

    def test_500RB_upper(self):
        self.assertEqual(self._parse("500RB"), 500000)

    def test_2_5m(self):
        self.assertEqual(self._parse("2.5m"), 2500000)

    def test_2_5M_upper(self):
        self.assertEqual(self._parse("2.5M"), 2500000)

    def test_plain_integer(self):
        self.assertEqual(self._parse("50000"), 50000)

    def test_plain_float(self):
        self.assertEqual(self._parse("50000.0"), 50000)

    def test_8juta_full_suffix(self):
        self.assertEqual(self._parse("8juta"), 8000000)

    def test_500ribu_full_suffix(self):
        self.assertEqual(self._parse("500ribu"), 500000)

    def test_1_5k_decimal(self):
        self.assertEqual(self._parse("1.5k"), 1500)

    def test_zero(self):
        self.assertEqual(self._parse("0"), 0)

    def test_large_plain_number(self):
        self.assertEqual(self._parse("1000000"), 1000000)


class TestParseResponseEdgeCases(unittest.TestCase):
    def setUp(self):
        self.parser = NLPParser(nullclaw_path="/usr/local/bin/nullclaw", openai_api_key="test-key")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            self.parser._parse_response("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            self.parser._parse_response("   ")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            self.parser._parse_response("not json at all")

    def test_json_wrapped_in_markdown_fence(self):
        payload = {
            "type": "spending",
            "amount": 25000,
            "category": "Food & Groceries",
            "description": "makan",
            "confidence": 0.9,
        }
        json_str = f"```json\n{json.dumps(payload)}\n```"
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["type"], "spending")
        self.assertEqual(result["amount"], 25000)

    def test_json_with_preamble_text(self):
        payload = {"type": "income", "amount": 8000000, "category": "Salary", "description": "gaji", "confidence": 0.99}
        json_str = f"Here is the extracted data: {json.dumps(payload)}"
        result = self.parser._parse_response(json_str)
        self.assertEqual(result["type"], "income")
        self.assertEqual(result["amount"], 8000000)


if __name__ == "__main__":
    unittest.main()
