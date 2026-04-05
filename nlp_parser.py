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

_PROMPT_TEMPLATE = (
    "Extract financial data from this Indonesian message: {text}\n"
    'Return JSON: {{"type": "spending|income|savings", "amount": <number>, '
    '"category": "<category>", "description": "<text>", "confidence": <0.0-1.0>}}'
)


def _normalize_amount(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    m = re.match(r"^([\d.]+)(k|jt|juta)?$", s)
    if not m:
        return int(float(s))
    num = float(m.group(1))
    suffix = m.group(2)
    if suffix == "k":
        return int(num * 1_000)
    if suffix in ("jt", "juta"):
        return int(num * 1_000_000)
    return int(num)


class NLPParser:
    def __init__(self, nullclaw_path=None, openai_api_key=None):
        self.nullclaw_path = nullclaw_path or os.environ.get("NULLCLAW_PATH")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    def _parse_response(self, json_str: str) -> dict:
        data = json.loads(json_str)
        data["amount"] = _normalize_amount(data["amount"])
        return data

    def parse_financial_message(self, text: str) -> dict:
        if not self.nullclaw_path:
            raise RuntimeError(
                f"nullclaw binary not found. Set NULLCLAW_PATH env var or install:\n{INSTALL_INSTRUCTIONS}"
            )
        prompt = _PROMPT_TEMPLATE.format(text=text)
        try:
            result = subprocess.run(
                [self.nullclaw_path, prompt],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "OPENAI_API_KEY": self.openai_api_key or ""},
            )
        except FileNotFoundError:
            raise RuntimeError(f"nullclaw binary not found at '{self.nullclaw_path}'. Install:\n{INSTALL_INSTRUCTIONS}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("nullclaw timed out after 10 seconds")
        return self._parse_response(result.stdout)
