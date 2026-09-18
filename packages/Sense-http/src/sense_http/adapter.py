"""HTTP polling adapter for normalized Sense telemetry."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sense_ai import ContextMachine
from sense_ai.adapters import TelemetryAdapter
from sense_ai.telemetry import TelemetryNormalizer


class HttpPollingAdapter(TelemetryAdapter):
    """Poll a JSON endpoint and feed normalized observations into Sense."""

    def __init__(
        self,
        machine: ContextMachine,
        normalizer: TelemetryNormalizer,
        *,
        url: str,
        interval_sec: float = 1.0,
        timeout_sec: float = 5.0,
        headers: dict[str, str] | None = None,
        client: Any = None,
    ) -> None:
        if interval_sec <= 0:
            raise ValueError("interval_sec must be > 0")
        self._machine = machine
        self._normalizer = normalizer
        self._url = url
        self._interval_sec = interval_sec
        self._timeout_sec = timeout_sec
        self._headers = dict(headers or {})
        self._client = client
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.errors: list[str] = []

    @classmethod
    def from_dict(
        cls,
        machine: ContextMachine,
        normalizer: TelemetryNormalizer,
        data: dict[str, Any],
        *,
        client: Any = None,
    ) -> HttpPollingAdapter:
        return cls(
            machine,
            normalizer,
            url=str(data["url"]),
            interval_sec=float(data.get("interval_sec", 1.0)),
            timeout_sec=float(data.get("timeout_sec", 5.0)),
            headers={
                str(key): str(value)
                for key, value in dict(data.get("headers", {})).items()
            },
            client=client,
        )

    def poll_once(self) -> Any:
        client = self._client or _new_client(self._timeout_sec)
        self._client = client
        response = client.get(
            self._url,
            headers=self._headers,
            timeout=self._timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
        now = datetime.now(timezone.utc)
        result = self._normalizer.normalize(
            payload,
            observed_at=now,
            received_at=now,
            source=f"http:{self._url}",
        )
        for observation in result.observations:
            self._machine.observe(observation)
        self.errors.extend(
            f"{issue.code}[{issue.target_path}]: {issue.message}"
            for issue in result.issues
        )
        return result

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="sense-http-poll",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._interval_sec * 2, 1.0))
            self._thread = None
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                self.errors.append(f"HTTP_POLL_ERROR: {exc}")
            self._stop.wait(self._interval_sec)


def _new_client(timeout_sec: float) -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise ImportError("httpx is required; install sense-http") from exc
    return httpx.Client(timeout=timeout_sec)
