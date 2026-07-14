from __future__ import annotations

from contextlib import AbstractContextManager
import subprocess
import threading
import time
from typing import Any


def gpu_inventory() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return {"tier": "unknown", "gpus": [], "memory_evidence": "unavailable"}
    gpus: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            gpus.append({"name": parts[0], "memory_total_mib": int(parts[1]), "driver_version": parts[2]})
    first_total = gpus[0]["memory_total_mib"] if gpus else 0
    tier = f"{round(first_total / 1024)}gb" if first_total else "unknown"
    return {"tier": tier, "gpus": gpus, "memory_evidence": "nvidia-smi" if gpus else "unavailable"}


class NvidiaMemorySampler(AbstractContextManager["NvidiaMemorySampler"]):
    def __init__(self, interval_seconds: float = 0.25) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[int] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _sample() -> int | None:
        try:
            completed = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            values = [int(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
            return sum(values) if values else None
        except (FileNotFoundError, ValueError, subprocess.SubprocessError):
            return None

    def _run(self) -> None:
        while not self._stop.is_set():
            sample = self._sample()
            if sample is not None:
                self.samples.append(sample)
            self._stop.wait(self.interval_seconds)

    def __enter__(self) -> "NvidiaMemorySampler":
        first = self._sample()
        if first is not None:
            self.samples.append(first)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        final = self._sample()
        if final is not None:
            self.samples.append(final)

    def evidence(self) -> dict[str, Any]:
        if not self.samples:
            return {"source": "unavailable", "samples": 0}
        return {
            "source": "nvidia-smi",
            "samples": len(self.samples),
            "start_used_mib": self.samples[0],
            "end_used_mib": self.samples[-1],
            "peak_used_mib": max(self.samples),
        }
