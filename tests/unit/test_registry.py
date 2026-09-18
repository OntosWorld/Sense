"""Capability registry behavior."""

from __future__ import annotations

from sense_ai import CapabilityRegistry, CapabilityStatus, ContextMachine


def test_registry_loads_declarative_capability() -> None:
    registry = CapabilityRegistry.from_dict(
        {
            "capabilities": [
                {
                    "name": "warehouse.pick",
                    "version": "1.2.0",
                    "requires": [
                        {"op": "equals", "path": "gripper.ready", "value": True},
                        {"op": "fresh", "path": "pose", "max_age_ms": 1000},
                    ],
                }
            ]
        }
    )
    machine = ContextMachine()
    registry.install(machine)
    machine.observe("gripper.ready", True)
    machine.observe("pose", {"x": 1.0})

    assert machine.evaluate("warehouse.pick").status == CapabilityStatus.AVAILABLE


def test_registry_selects_latest_semver() -> None:
    registry = CapabilityRegistry.from_dict(
        {
            "capabilities": [
                {"name": "nav.ready", "version": "1.0.0"},
                {"name": "nav.ready", "version": "1.2.0"},
                {"name": "nav.ready", "version": "1.1.5"},
            ]
        }
    )

    assert registry.get("nav.ready").version == "1.2.0"
    assert registry.versions("nav.ready") == ("1.0.0", "1.1.5", "1.2.0")
