"""End-to-end raw payload -> normalized context -> capability transitions."""

from __future__ import annotations

from pathlib import Path

from sense_ai import CapabilityStatus, ReplayAdapter, ReplayFrame, SenseConfig


def test_configured_raw_pipeline_reaches_expected_states() -> None:
    config_path = (
        Path(__file__).parents[2] / "examples" / "06_full_pipeline" / "sense.json"
    )
    config = SenseConfig.from_json_file(config_path)
    machine = config.build_machine(machine_ref="e2e-robot")

    frames = [
        ReplayFrame(
            {
                "battery": {"ratio": 0.80},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 0, "y": 0}},
                "payload": {"utilization": 0.30},
            }
        ),
        ReplayFrame(
            {
                "battery": {"ratio": 0.80},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 0, "y": 0}},
                "payload": {"utilization": 0.95},
            }
        ),
        ReplayFrame(
            {
                "battery": {"ratio": 0.10},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 0, "y": 0}},
                "payload": {"utilization": 0.30},
            }
        ),
    ]

    adapter = ReplayAdapter(
        machine,
        config.normalizer,
        frames,
        evaluate_after_frame=True,
    )

    states = []
    @machine.on_transition("warehouse.pick")
    def capture(transition):
        states.append(transition.current)

    results = adapter.run()

    assert all(result.ok for result in results)
    assert states == [
        CapabilityStatus.AVAILABLE,
        CapabilityStatus.DEGRADED,
        CapabilityStatus.UNAVAILABLE,
    ]
    assert machine.evaluate("warehouse.pick").status == CapabilityStatus.UNAVAILABLE
