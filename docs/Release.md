# Release 0.3.0

Sense 0.3.0 is the first release containing the complete raw-telemetry
ingestion pipeline and the ROS 2, MQTT, HTTP, and peaq adapters.

## Preconditions

Before publishing:

1. `main` CI is green.
2. The ROS 2 Jazzy runtime job is green.
3. Package versions are all `0.3.0`.
4. PyPI Trusted Publishing is configured for the GitHub environment named
   `pypi` for:
   - `sense-ai`
   - `sense-peaq`
   - `sense-ros2`
   - `sense-mqtt`
   - `sense-http`
5. Review `CHANGELOG.md`.
6. Optionally run the protected live peaq verification before public release.

## Publish

Create and publish a GitHub Release with tag:

```text
v0.3.0
```

Target:

```text
main
```

The existing `.github/workflows/release.yml` workflow will:

- verify all package versions match;
- build all five distributions independently;
- upload build artifacts;
- publish each package to PyPI through Trusted Publishing.

The workflow only publishes on the GitHub `release.published` event. A manual
workflow dispatch is build-only and cannot publish packages accidentally.

## Post-release verification

After the release workflow succeeds:

```bash
python -m venv /tmp/sense-release-check
source /tmp/sense-release-check/bin/activate

pip install sense-ai==0.3.0
pip install sense-peaq==0.3.0
pip install sense-ros2==0.3.0
pip install sense-mqtt==0.3.0
pip install sense-http==0.3.0

python - <<'PY'
import sense_ai
import sense_peaq
import sense_ros2
import sense_mqtt
import sense_http

print(sense_ai.__version__)
print(sense_peaq.__version__)
print(sense_ros2.__version__)
print(sense_mqtt.__version__)
print(sense_http.__version__)
PY
```

All versions should print `0.3.0`.
