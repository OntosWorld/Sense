from __future__ import annotations

import sys
import types

from sense_peaq import AGUNG, apply_official_network_defaults
from sense_peaq.cli import main


class _FakePeaqClient:
    address = "0x1234567890abcdef1234567890abcdef12345678"

    @classmethod
    def from_env(cls):
        return cls()

    def submit_event(self, **kwargs):
        assert kwargs["machine_id"] == 42
        return ("0xabc", b"\x01\x02")


def test_verify_live_cli_runs_preflight_and_submission(monkeypatch, capsys) -> None:
    fake_sdk = types.ModuleType("peaq_os_sdk")
    fake_sdk.PeaqosClient = _FakePeaqClient

    fake_constants = types.ModuleType("peaq_os_sdk.constants")
    fake_constants.EVENT_TYPE_ACTIVITY = 1

    monkeypatch.setitem(sys.modules, "peaq_os_sdk", fake_sdk)
    monkeypatch.setitem(sys.modules, "peaq_os_sdk.constants", fake_constants)
    monkeypatch.setenv("PEAQOS_RPC_URL", "https://example.invalid")
    monkeypatch.setenv("TOKENOMICS_DEPLOYMENT_ID", "test-deployment")

    assert main(["verify-live", "--machine-id", "42", "--yes"]) == 0

    output = capsys.readouterr().out
    assert "peaq client loaded" in output
    assert "Sense preflight: PASSED" in output
    assert "Live peaq verification: PASSED" in output
    assert "Transaction hash: 0xabc" in output
    assert "Data hash: 0x0102" in output


def test_agung_defaults_fill_only_missing_public_configuration() -> None:
    environment = {
        "PEAQOS_RPC_URL": "https://peaq-agung.api.onfinality.io/public",
        "EVENT_REGISTRY_ADDRESS": "0xexplicit",
    }

    profile = apply_official_network_defaults(environment)

    assert profile is AGUNG
    assert environment["TOKENOMICS_DEPLOYMENT_ID"] == "agung-2026-08-28"
    assert (
        environment["IDENTITY_REGISTRY_ADDRESS"]
        == AGUNG.environment["IDENTITY_REGISTRY_ADDRESS"]
    )
    assert environment["EVENT_REGISTRY_ADDRESS"] == "0xexplicit"


def test_unknown_network_does_not_receive_defaults() -> None:
    environment = {"PEAQOS_RPC_URL": "https://example.invalid"}

    assert apply_official_network_defaults(environment) is None
    assert "EVENT_REGISTRY_ADDRESS" not in environment
