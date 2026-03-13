from __future__ import annotations

import time

from app.api.services.refinement_queue import RefinementQueue
from app.api.services.refiner_service import RefinerResult
from app.api.services.streaming_metrics import StreamingMetrics


def test_refinement_queue_supersedes_stale_jobs(monkeypatch, tmp_path) -> None:
    published: list[tuple[str, dict]] = []

    def publish(event_type: str, payload: dict) -> None:
        published.append((event_type, payload))

    def fake_refine(self, text: str, **kwargs) -> RefinerResult:  # noqa: ANN001
        time.sleep(0.03)
        return RefinerResult(
            text=f"{text}.",
            mode="strict",
            model_id="qwen2.5-7b-instruct",
            used_runtime=True,
        )

    monkeypatch.setattr("app.api.refinement_queue.RefinerService.refine_text", fake_refine)

    queue = RefinementQueue(
        download_root=tmp_path,
        publish_event=publish,
        metrics=StreamingMetrics(),
        debounce_seconds=0.01,
    )
    try:
        queue.enqueue(
            session_id="session-1",
            segment={"id": "seg-1", "text": "first draft", "display_text": "first draft"},
            refinement_mode="strict",
            model_id="qwen2.5-7b-instruct",
            runtime_enabled=True,
            language_hint="en",
        )
        queue.enqueue(
            session_id="session-1",
            segment={"id": "seg-2", "text": "second draft", "display_text": "second draft"},
            refinement_mode="strict",
            model_id="qwen2.5-7b-instruct",
            runtime_enabled=True,
            language_hint="en",
        )

        time.sleep(0.12)
    finally:
        queue.shutdown()

    assert len(published) == 1
    assert published[0][0] == "refine_final"
    assert published[0][1]["segment"]["id"] == "seg-2"


def test_refinement_queue_skips_noop_results(monkeypatch, tmp_path) -> None:
    published: list[tuple[str, dict]] = []

    def fake_refine(self, text: str, **kwargs) -> RefinerResult:  # noqa: ANN001
        return RefinerResult(text=text, mode="strict", model_id="model", used_runtime=True)

    monkeypatch.setattr("app.api.refinement_queue.RefinerService.refine_text", fake_refine)

    queue = RefinementQueue(
        download_root=tmp_path,
        publish_event=lambda event_type, payload: published.append((event_type, payload)),
        metrics=StreamingMetrics(),
        debounce_seconds=0.01,
    )
    try:
        queue.enqueue(
            session_id="session-2",
            segment={"id": "seg-1", "text": "unchanged", "display_text": "unchanged"},
            refinement_mode="strict",
            model_id="model",
            runtime_enabled=True,
            language_hint="en",
        )
        time.sleep(0.05)
    finally:
        queue.shutdown()

    assert published == []
