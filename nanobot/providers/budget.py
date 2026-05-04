"""Budget guardrails and persisted usage counters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from nanobot.config.schema import BudgetConfig


@dataclass
class BudgetDecision:
    allowed: bool
    message: str | None = None


class BudgetTracker:
    def __init__(self, config: BudgetConfig, provider_name: str, model: str):
        self.config = config
        self.provider_name = provider_name
        self.model = model
        self.state_path = Path("~/.nanobot/state/budgets.json").expanduser()

    def _today(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _load(self) -> dict:
        try:
            if not self.state_path.exists():
                return {}
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _session_key(self) -> str:
        return f"{self.provider_name}:{self.model}"

    def _price_key(self) -> str | None:
        model_key = f"{self.provider_name}/{self.model}"
        if model_key in self.config.prices_usd_per_1k:
            return model_key
        if self.provider_name in self.config.prices_usd_per_1k:
            return self.provider_name
        return None

    def check(self, estimated_input_tokens: int, requested_output_tokens: int) -> BudgetDecision:
        c = self.config
        if estimated_input_tokens > c.max_input_tokens_per_request:
            return BudgetDecision(False, f"Budget limit: request input too large ({estimated_input_tokens} > {c.max_input_tokens_per_request} tokens).")
        if requested_output_tokens > c.max_output_tokens_per_request:
            return BudgetDecision(False, f"Budget limit: requested output too large ({requested_output_tokens} > {c.max_output_tokens_per_request} tokens).")

        data = self._load()
        today = self._today()
        day = data.setdefault("daily", {}).setdefault(today, {"tokens": 0, "usd": 0.0})
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(self._session_key(), {"tokens": 0, "last_day": today})
        if sess.get("last_day") != today:
            sess["tokens"] = 0
            sess["last_day"] = today

        if int(sess.get("tokens", 0)) >= c.max_session_tokens:
            return BudgetDecision(False, f"Budget limit: session token budget reached ({sess.get('tokens')}/{c.max_session_tokens}).")
        if int(day.get("tokens", 0)) >= c.max_daily_tokens:
            return BudgetDecision(False, f"Budget limit: daily token budget reached ({day.get('tokens')}/{c.max_daily_tokens}) for {today}.")
        if c.dollar_ceiling_per_day is not None and float(day.get("usd", 0.0)) >= c.dollar_ceiling_per_day:
            return BudgetDecision(False, f"Budget limit: daily USD budget reached (${day.get('usd', 0.0):.4f}/${c.dollar_ceiling_per_day:.4f}) for {today}.")
        return BudgetDecision(True)

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        data = self._load()
        today = self._today()
        day = data.setdefault("daily", {}).setdefault(today, {"tokens": 0, "usd": 0.0})
        sessions = data.setdefault("sessions", {})
        sess = sessions.setdefault(self._session_key(), {"tokens": 0, "last_day": today})
        if sess.get("last_day") != today:
            sess["tokens"] = 0
            sess["last_day"] = today

        used = int(prompt_tokens) + int(completion_tokens)
        sess["tokens"] = int(sess.get("tokens", 0)) + used
        day["tokens"] = int(day.get("tokens", 0)) + used

        price_key = self._price_key()
        if price_key is not None:
            price = self.config.prices_usd_per_1k[price_key]
            usd = (prompt_tokens / 1000.0) * price.input_per_1k + (completion_tokens / 1000.0) * price.output_per_1k
            day["usd"] = float(day.get("usd", 0.0)) + usd

        self._save(data)
