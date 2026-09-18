# Example 01 — Minimal Capability Evaluation

A small local-only Sense example.

Run from the repository root:

```bash
pip install -e .
python examples/01_minimal/evaluate.py
```

It demonstrates:

- creating a `ContextMachine`;
- defining capabilities;
- adding timestamped telemetry;
- evaluating current capability state;
- creating a snapshot;
- reading transitions.

For new code, read observations with:

```python
observation = machine.get_observation("battery.charge_level")
```

Sense evaluation does not require peaq, ROS 2, a backend, or network access.

See the canonical [Quickstart](../../QUICKSTART.md).
