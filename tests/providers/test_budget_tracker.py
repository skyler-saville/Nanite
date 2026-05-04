from pathlib import Path

from nanobot.config.schema import BudgetConfig
from nanobot.providers.budget import BudgetTracker


def test_budget_tracker_request_limit_blocks(tmp_path: Path):
    tracker = BudgetTracker(
        config=BudgetConfig(max_input_tokens_per_request=10, max_output_tokens_per_request=5),
        provider_name="openai",
        model="gpt-test",
    )
    tracker.state_path = tmp_path / "budgets.json"
    decision = tracker.check(estimated_input_tokens=11, requested_output_tokens=3)
    assert not decision.allowed
    assert "input too large" in (decision.message or "")


def test_budget_tracker_records_usage(tmp_path: Path):
    tracker = BudgetTracker(config=BudgetConfig(), provider_name="openai", model="gpt-test")
    tracker.state_path = tmp_path / "budgets.json"
    tracker.record_usage(100, 50)
    data = tracker._load()
    day = next(iter(data["daily"].values()))
    assert day["tokens"] == 150
