from __future__ import annotations

import sys
import types

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
