#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
ROS_IMAGE="${SENSE_ROS_IMAGE:-ros:jazzy-ros-base}"

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' "ERROR: Docker is required for the isolated ROS 2 runtime test." >&2
  exit 2
fi

if ! docker info >/dev/null 2>&1; then
  printf '%s\n' "ERROR: Docker is installed but its daemon is not running." >&2
  exit 2
fi

docker run --rm \
  -v "$REPO_ROOT:/workspace" \
  -w /workspace \
  "$ROS_IMAGE" \
  bash -lc '
    set -eo pipefail
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3-pip \
      python3-venv \
      ros-jazzy-std-msgs
    source /opt/ros/jazzy/setup.bash
    python3 -m venv --system-site-packages /tmp/sense-ros
    /tmp/sense-ros/bin/python -m pip install --upgrade pip
    /tmp/sense-ros/bin/pip install -e .
    /tmp/sense-ros/bin/pip install -e packages/Sense-ros2
    /tmp/sense-ros/bin/python -m pytest \
      packages/Sense-ros2/tests/test_runtime_ros2.py -v
  '
