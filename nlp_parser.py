import json
import os
import re
import subprocess

INSTALL_INSTRUCTIONS = """
ARCH=$(uname -m); if [ "$ARCH" = "aarch64" ]; then
  wget https://github.com/nullclaw/nullclaw/releases/latest/download/nullclaw-linux-arm64 -O /usr/local/bin/nullclaw
else
  wget https://github.com/nullclaw/nullclaw/releases/latest/download/nullclaw-linux-amd64 -O /usr/local/bin/nullclaw
fi
chmod +x /usr/local/bin/nullclaw
"""

NLP_PROMPT_TEMPLATE = (
    "You are a financial data extractor for an Indonesian financial tracker app.\n"
    'Extract transaction data from this message: "{text}"\n\n'
    "Return ONLY valid JSON (no explanation):\n"
    '{{"type": "spending|income|savings", "amount": <integer IDR>, "category": "<category>", '
    '"description": "<brief description>", "confidence": <0.0-1.0>}}\n\n'
    "Categories for spending: Food & Groceries, Transportation, Housing, Entertainment, "
    "Healthcare, Education, Shopping, Bills & Utilities\n"
    "Categories for income: Salary, Freelance, Investment, Side Business, Family Support, Gift, Other\n\n"
    "Indonesian amount formats: 50k=50000, 8jt=8000000, 1.5jt=1500000, 500rb=500000"
)

_PROMPT_TEMPLATE = NLP_PROMPT_TEMPLATE

VALID_TYPES = {"spending", "income", "savings"}

SPENDING_CATEGORIES = {
    "Food & Groceries",
    "Transportation",
    "Housing",
    "Entertainment",
    "Healthcare",
    "Education",
    "Shopping",
    "Bills & Utilities",
}

INCOME_CATEGORIES = {
    "Salary",
    "Freelance",
    "Investment",
    "Side Business",
    "Family Support",
    "Gift",
    "Other",
}

ALL_CATEGORIES = SPENDING_CATEGORIES | INCOME_CATEGORIES


def _normalize_amount(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    return NLPParser.parse_indonesian_amount(s)


class NLPParser:
    def __init__(self, nullclaw_path=None, openai_api_key=None):
        self.nullclaw_path = nullclaw_path or os.environ.get("NULLCLAW_PATH")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    @staticmethod
    def parse_indonesian_amount(text: str) -> int:
        s = str(text).strip()
        # Regex matches optional decimal number + optional Indonesian multiplier suffix.
        # The dot in "1.5jt" is a decimal separator, not a thousands separator.
        pattern = re.match(
            r"^([\d]+(?:[.,][\d]+)?)\s*(k|jt|juta|rb|ribu|m|million)?$",
            s,
            re.IGNORECASE,
        )
        if not pattern:
            cleaned = re.sub(r"[,.](?=\d{3}(?:[,.]|$))", "", s)
            cleaned = cleaned.replace(",", ".")
            return int(float(cleaned))

        num_str = pattern.group(1).replace(",", ".")
        suffix = (pattern.group(2) or "").lower()
        num = float(num_str)

        if suffix == "k":
            return int(num * 1_000)
        if suffix in ("jt", "juta"):
            return int(num * 1_000_000)
        if suffix in ("rb", "ribu"):
            return int(num * 1_000)
        if suffix in ("m", "million"):
            return int(num * 1_000_000)
        return int(num)

    def _parse_response(self, json_str: str) -> dict:
        if not json_str or not json_str.strip():
            raise ValueError("Empty response from nullclaw")

        raw = json_str.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1)
        else:
            brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if brace_match:
                raw = brace_match.group(0)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from nullclaw: {exc}. Raw output: {json_str!r}") from exc

        data["amount"] = _normalize_amount(data.get("amount", 0))
        return data

    def validate_output(self, result: dict) -> dict:
        tx_type = result.get("type", "")
        if tx_type not in VALID_TYPES:
            result["type"] = "spending"

        try:
            amount = _normalize_amount(result.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0
        if amount <= 0:
            raise ValueError(f"Invalid or zero amount: {result.get('amount')!r}")
        result["amount"] = amount

        category = result.get("category", "")
        if not isinstance(category, str) or not category.strip():
            result["category"] = "Other"
        else:
            result["category"] = category.strip()

        description = result.get("description", "")
        if not isinstance(description, str):
            result["description"] = str(description)
        else:
            result["description"] = description

        try:
            confidence = float(result.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5
        result["confidence"] = max(0.0, min(1.0, confidence))

        return result

    def parse_financial_message(self, text: str) -> dict:
        if not self.nullclaw_path:
            raise RuntimeError(
                f"nullclaw binary not found. Set NULLCLAW_PATH env var or install:\n{INSTALL_INSTRUCTIONS}"
            )

        prompt = NLP_PROMPT_TEMPLATE.format(text=text)

        try:
            result = subprocess.run(
                [self.nullclaw_path, prompt],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "OPENAI_API_KEY": self.openai_api_key or ""},
            )
        except FileNotFoundError:
            raise RuntimeError(f"nullclaw binary not found at '{self.nullclaw_path}'. Install:\n{INSTALL_INSTRUCTIONS}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("nullclaw timed out after 30 seconds")

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            raise RuntimeError(f"nullclaw exited with code {result.returncode}. stderr: {stderr!r}")

        stdout = result.stdout
        if not stdout or not stdout.strip():
            raise RuntimeError("nullclaw returned empty output")

        try:
            parsed = self._parse_response(stdout)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        return self.validate_output(parsed)
