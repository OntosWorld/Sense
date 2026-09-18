# Example 05 — ROS 2 bridge

Sense 0.3.x supports declarative ROS 2 topic mapping.

The bridge uses the same core validation and normalization layer as MQTT, HTTP,
replay, and OEM integrations.

```text
ROS 2 message
    ↓
field extraction
    ↓
configured transforms
    ↓
canonical Sense observation
    ↓
capability evaluation
```

## Install

Install/source ROS 2 first, then:

```bash
pip install -e .
pip install -e packages/Sense-ros2
```

## Mapping

A bridge config can define:

```yaml
topics:
  - topic: /battery_state
    message_type: sensor_msgs.msg.BatteryState
    field: percentage
    target: battery.level_pct
    transform: ratio_to_percent
    ttl_ms: 5000
```

Use `Ros2SenseBridge.from_yaml_file()` in a live ROS process.

The repository example remains runnable as a local development demonstration.

Sense does not replace ROS 2 control/runtime behavior or peaq's own ROS runtime.

See [sense-ros2](../../packages/Sense-ros2/README.md).
