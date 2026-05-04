"""Fork health suite: security guardrails, token gating, and usage tracking."""

from pathlib import Path

from nanobot.channels.websocket import WebSocketChannel
from nanobot.config.schema import BudgetConfig
from nanobot.providers.budget import BudgetTracker
from nanobot.security import network


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _Request:
    def __init__(self, *, path: str, headers: dict[str, str] | None = None):
        self.path = path
        self.headers = _Headers(headers or {})


def test_security_ssrf_blocks_private_addresses() -> None:
    ok, message = network.validate_resolved_url("http://127.0.0.1/admin")
    assert ok is False
    assert "private address" in message


def test_security_ssrf_whitelist_can_allow_internal_ranges() -> None:
    network.configure_ssrf_whitelist(["100.64.0.0/10"])
    try:
        ok, message = network.validate_resolved_url("http://100.64.0.25/resource")
        assert ok is True
        assert message == ""
    finally:
        network.configure_ssrf_whitelist([])


def test_websocket_api_token_is_required_and_checked() -> None:
    channel = WebSocketChannel(
        {
            "enabled": True,
            "allowFrom": ["*"],
            "tokenTtlS": 120,
            "websocketRequiresToken": True,
        },
        bus=object(),
    )
    token = "nbwt_unit_test"
    channel._api_tokens[token] = 10e9

    no_auth = _Request(path="/api/sessions", headers={})
    assert channel._check_api_token(no_auth) is False

    with_auth = _Request(
        path="/api/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    assert channel._check_api_token(with_auth) is True


def test_budget_tracker_enforces_and_persists_usage(tmp_path: Path) -> None:
    tracker = BudgetTracker(
        config=BudgetConfig(
            max_input_tokens_per_request=500,
            max_output_tokens_per_request=300,
        ),
        provider_name="openai",
        model="gpt-test",
    )
    tracker.state_path = tmp_path / "budgets.json"

    decision = tracker.check(estimated_input_tokens=120, requested_output_tokens=80)
    assert decision.allowed is True

    tracker.record_usage(input_tokens=120, output_tokens=80)
    state = tracker._load()
    daily = next(iter(state["daily"].values()))
    assert daily["tokens"] == 200
    assert daily["requests"] == 1
