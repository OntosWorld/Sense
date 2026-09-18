"""Complete Sense pipeline: raw OEM-style payloads -> live capability context."""

from __future__ import annotations

from pathlib import Path

from sense_ai import ReplayAdapter, ReplayFrame, SenseConfig

HERE = Path(__file__).parent


def main() -> None:
    config = SenseConfig.from_json_file(HERE / "sense.json")
    machine = config.build_machine(machine_ref="warehouse-robot-01")

    @machine.on_transition("warehouse.pick")
    def show_transition(transition):
        print(transition.label)
        for reason in transition.reasons:
            print(" ", reason["code"], reason.get("path"))

    frames = [
        ReplayFrame(
            {
                "battery": {"ratio": 0.82},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 1.0, "y": 2.0, "frame": "map"}},
                "payload": {"utilization": 0.40},
            }
        ),
        ReplayFrame(
            {
                "battery": {"ratio": 0.78},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 1.1, "y": 2.0, "frame": "map"}},
                "payload": {"utilization": 0.95},
            }
        ),
        ReplayFrame(
            {
                "battery": {"ratio": 0.12},
                "safety": {"estop": False},
                "localization": {"pose": {"x": 1.2, "y": 2.0, "frame": "map"}},
                "payload": {"utilization": 0.50},
            }
        ),
    ]

    ReplayAdapter(machine, config.normalizer, frames).run()

    result = machine.evaluate("warehouse.pick")
    print("current:", result.status.value)
    print("unknown paths:", result.unknown_paths)
    print(machine.snapshot().publishable_view().to_json(indent=2))


if __name__ == "__main__":
    main()
