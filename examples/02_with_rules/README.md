# Example 02 — Declarative Rules

Demonstrates Sense rule primitives and logical composition.

Run:

```bash
pip install -e .
python examples/02_with_rules/evaluate.py
```

Rules include:

```python
equals("mode.current", "auto")
gte("battery.level_pct", 20)
lt("motor.temperature_c", 80)
exists("localization.pose")
fresh("localization.pose", max_age_ms=1000)
in_("mode.current", ["auto", "assisted"])
```

Composition:

```python
ALL(rule_a, rule_b)
ANY(rule_a, rule_b)
NOT(rule_a)
NONE_OF(rule_a, rule_b)
ONLY_ONE(rule_a, rule_b)
```

Inspect a capability result through:

```python
result = machine.evaluate("inspection.ready")

print(result.status)
print(result.unknown_paths)

for reason in result.reasons:
    print(
        reason.code,
        reason.severity,
        reason.path,
        reason.expected,
        reason.observed,
        reason.is_stale,
    )
```

`UNKNOWN` means required evidence is missing, stale, invalid, or could not be evaluated safely. It is not equivalent to `UNAVAILABLE`.

See [Capability Guide](../../docs/Capability-Guide.md).
