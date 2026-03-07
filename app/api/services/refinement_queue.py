from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Timer
from typing import Any, Callable

from app.api.services.refiner_service import RefinerService


class RefinementQueue:
    def __init__(
        self,
        *,
        download_root,
        publish_event: Callable[[str, dict[str, Any]], None],
        metrics,
        debounce_seconds: float = 0.25,
    ) -> None:
        self._publish_event = publish_event
        self._metrics = metrics
        self._refiner = RefinerService(download_root)
        self._debounce_seconds = debounce_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="refiner")
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def shutdown(self) -> None:
        with self._lock:
            for job in self._jobs.values():
                timer = job.get("timer")
                if timer is not None:
                    timer.cancel()
            self._jobs.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._refiner.unload()

    def enqueue(
        self,
        *,
        session_id: str,
        segment: dict[str, Any],
        refinement_mode: str,
        refinement_profile: str = "raw",
        model_id: str | None,
        runtime_enabled: bool,
        language_hint: str,
    ) -> None:
        if refinement_mode == "off" or not segment.get("text"):
            return

        with self._lock:
            existing = self._jobs.get(session_id)
            next_revision = int(existing["revision"]) + 1 if existing else 1
            if existing is not None:
                timer = existing.get("timer")
                if timer is not None:
                    timer.cancel()
                self._metrics.record_superseded_refine()

            job = {
                "revision": next_revision,
                "segment": dict(segment),
                "refinement_mode": refinement_mode,
                "refinement_profile": refinement_profile,
                "model_id": model_id,
                "runtime_enabled": runtime_enabled,
                "language_hint": language_hint,
            }
            timer = Timer(
                self._debounce_seconds,
                self._executor.submit,
                args=(self._run_job, session_id, next_revision),
            )
            job["timer"] = timer
            self._jobs[session_id] = job
            timer.start()

    def _run_job(self, session_id: str, revision: int) -> None:
        with self._lock:
            job = self._jobs.get(session_id)
            if job is None or job["revision"] != revision:
                self._metrics.record_superseded_refine()
                return
            segment = dict(job["segment"])
            refinement_mode = str(job["refinement_mode"])
            refinement_profile = str(job.get("refinement_profile", "raw"))
            model_id = job["model_id"]
            runtime_enabled = bool(job["runtime_enabled"])
            language_hint = str(job["language_hint"])

        start = time.perf_counter()
        result = self._refiner.refine_text(
            segment.get("text", ""),
            mode=refinement_mode,
            profile=refinement_profile,
            model_id=model_id,
            runtime_enabled=runtime_enabled,
            language_hint=language_hint,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        with self._lock:
            active = self._jobs.get(session_id)
            if active is None or active["revision"] != revision:
                self._metrics.record_superseded_refine()
                return
            self._jobs.pop(session_id, None)

        if not result.text or result.text == segment.get("text"):
            return

        refined_segment = {
            **segment,
            "display_text": result.text,
            "refined_text": result.text,
            "raw_text": segment.get("text"),
            "was_refined": result.used_runtime,
        }
        self._metrics.record_refine(elapsed_ms)
        self._metrics.log_trace(
            session_id=session_id,
            segment_id=str(segment.get("id", "unknown")),
            stage="refine",
            duration_ms=elapsed_ms,
            extra=f"model={result.model_id or 'none'} mode={result.mode}",
        )
        self._publish_event(
            "refine_final",
            {
                "session_id": session_id,
                "segment_id": segment.get("id"),
                "base_revision": revision,
                "refinement_mode": result.mode,
                "refiner_model_id": result.model_id,
                "used_runtime": result.used_runtime,
                "segment": refined_segment,
            },
        )

