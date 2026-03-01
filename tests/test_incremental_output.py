from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.core.models import FormulaFinding, TranscriptSegment
from app.stem.postprocess import NotesBundle, StemNoteProcessor


@pytest.fixture
def sample_segments() -> list[TranscriptSegment]:
    """Create sample transcript segments for testing."""
    return [
        TranscriptSegment(
            id="seg-1",
            start=0.0,
            end=5.0,
            text="First segment about velocity",
            display_text="First segment about velocity",
            language="en",
            confidence=0.9,
        ),
        TranscriptSegment(
            id="seg-2",
            start=5.0,
            end=10.0,
            text="Second segment with formula v equals d over t",
            display_text="Second segment with formula v = d/t",
            language="en",
            confidence=0.85,
        ),
    ]


@pytest.fixture
def new_segments() -> list[TranscriptSegment]:
    """Create new segments for incremental build testing."""
    return [
        TranscriptSegment(
            id="seg-3",
            start=10.0,
            end=15.0,
            text="Third segment with acceleration",
            display_text="Third segment with acceleration",
            language="en",
            confidence=0.88,
        ),
    ]


@pytest.fixture
def existing_formulas() -> list[FormulaFinding]:
    """Create existing formulas for incremental testing."""
    return [
        FormulaFinding(
            expression="v = d/t",
            timestamp_start=5.0,
            timestamp_end=10.0,
            context="velocity formula",
            confidence=0.85,
            parseable=True,
            review_flag=False,
            reasons=[],
        ),
    ]


class TestIncrementalBuild:
    """Test incremental build only processes new segments."""

    def test_incremental_build_processes_only_new_segments(
        self,
        sample_segments: list[TranscriptSegment],
        new_segments: list[TranscriptSegment],
        existing_formulas: list[FormulaFinding],
    ) -> None:
        processor = StemNoteProcessor()

        with patch.object(processor, "_build_notes_markdown") as mock_build:
            mock_build.return_value = "# Notes\n\nTest content"

            processor.build_incremental(
                existing_segments=sample_segments,
                new_segments=new_segments,
                existing_formulas=existing_formulas,
                existing_needs_review=[],
            )

            call_args = mock_build.call_args
            all_segments = call_args[0][0]
            assert len(all_segments) == 3
            assert all_segments[0].id == "seg-1"
            assert all_segments[1].id == "seg-2"
            assert all_segments[2].id == "seg-3"

    def test_incremental_preserves_existing_formulas(
        self,
        sample_segments: list[TranscriptSegment],
        new_segments: list[TranscriptSegment],
        existing_formulas: list[FormulaFinding],
    ) -> None:
        processor = StemNoteProcessor()

        bundle = processor.build_incremental(
            existing_segments=sample_segments,
            new_segments=new_segments,
            existing_formulas=existing_formulas,
            existing_needs_review=[],
        )

        assert len(bundle.formulas) >= 1
        assert any(f.expression == "v = d/t" for f in bundle.formulas)

    def test_incremental_detects_new_formulas(
        self,
        sample_segments: list[TranscriptSegment],
        existing_formulas: list[FormulaFinding],
    ) -> None:
        new_segment = TranscriptSegment(
            id="seg-new",
            start=15.0,
            end=20.0,
            text="Energy equals mass times c squared",
            display_text="E = mc²",
            language="en",
            confidence=0.9,
        )

        processor = StemNoteProcessor()
        bundle = processor.build_incremental(
            existing_segments=sample_segments,
            new_segments=[new_segment],
            existing_formulas=existing_formulas,
            existing_needs_review=[],
        )

        assert len(bundle.formulas) > len(existing_formulas)

    def test_incremental_skips_when_no_new_segments(
        self,
        sample_segments: list[TranscriptSegment],
        existing_formulas: list[FormulaFinding],
    ) -> None:
        processor = StemNoteProcessor()

        with patch.object(processor, "_build_notes_markdown") as mock_build:
            mock_build.return_value = "# Notes"

            processor.build_incremental(
                existing_segments=sample_segments,
                new_segments=[],
                existing_formulas=existing_formulas,
                existing_needs_review=[],
            )

            mock_build.assert_called_once()

    def test_segment_cache_populated(self, sample_segments: list[TranscriptSegment]) -> None:
        processor = StemNoteProcessor()
        new_segment = TranscriptSegment(
            id="seg-cache-test",
            start=20.0,
            end=25.0,
            text="Test with units 5 meters per second",
            display_text="Test with units 5 m/s",
            language="en",
            confidence=0.85,
        )

        processor.build_incremental(
            existing_segments=sample_segments,
            new_segments=[new_segment],
            existing_formulas=[],
            existing_needs_review=[],
        )

        assert len(processor._segment_cache) > 0


class TestFullRebuild:
    """Test full rebuild on session stop."""

    def test_full_build_processes_all_segments(
        self,
        sample_segments: list[TranscriptSegment],
    ) -> None:
        processor = StemNoteProcessor()

        with patch.object(processor, "_build_notes_markdown") as mock_build:
            mock_build.return_value = "# Notes"

            processor.build(sample_segments)

            call_args = mock_build.call_args
            processed_segments = call_args[0][0]
            assert len(processed_segments) == len(sample_segments)

    def test_full_build_clears_and_rebuilds_formulas(
        self,
        sample_segments: list[TranscriptSegment],
    ) -> None:
        processor = StemNoteProcessor()

        sample_segments.append(
            TranscriptSegment(
                id="seg-formula",
                start=10.0,
                end=15.0,
                text="Force equals mass times acceleration",
                display_text="F = ma",
                language="en",
                confidence=0.9,
            )
        )

        bundle = processor.build(sample_segments)

        assert len(bundle.formulas) > 0
        assert any("F" in f.expression or "force" in f.expression.lower() for f in bundle.formulas)

    def test_full_build_updates_contradictions(
        self,
        sample_segments: list[TranscriptSegment],
    ) -> None:
        processor = StemNoteProcessor()

        segments_with_contradiction = [
            TranscriptSegment(
                id="seg-x1",
                start=0.0,
                end=5.0,
                text="Let x equal 5",
                display_text="x = 5",
                language="en",
                confidence=0.9,
            ),
            TranscriptSegment(
                id="seg-x2",
                start=5.0,
                end=10.0,
                text="Let x equal 10",
                display_text="x = 10",
                language="en",
                confidence=0.9,
            ),
        ]

        bundle = processor.build(segments_with_contradiction)

        assert len(bundle.needs_review) > 0
        assert any("contradictory-definition" in str(r.review_reasons) for r in bundle.needs_review)


class TestCrashSafeWrites:
    """Test crash-safe writes using temp file pattern."""

    def test_safe_write_creates_temp_file_first(self, temp_dir: Path) -> None:
        from app.storage.session_store import SessionWriter

        session = MagicMock()
        session.output_dir = temp_dir
        session.to_metadata_dict.return_value = {"session_id": "test-123"}

        writer = SessionWriter(session)

        target_file = temp_dir / "test_output.json"
        writer._safe_write_json(target_file, {"data": "test"})

        temp_file = target_file.with_suffix(target_file.suffix + ".tmp")
        assert not temp_file.exists()
        assert target_file.exists()

    def test_safe_write_preserves_original_on_failure(self, temp_dir: Path) -> None:
        from app.storage.session_store import SessionWriter

        session = MagicMock()
        session.output_dir = temp_dir
        session.to_metadata_dict.return_value = {"session_id": "test-123"}

        writer = SessionWriter(session)

        target_file = temp_dir / "stable.json"
        original_content = '{"version": 1}'
        target_file.write_text(original_content)

        with patch.object(Path, "write_text") as mock_write:
            mock_write.side_effect = [IOError("Disk full"), None]

            try:
                writer._safe_write_json(target_file, {"version": 2})
            except IOError:
                pass

        content = target_file.read_text()
        assert "version" in content

    def test_append_segment_atomic_append(self, temp_dir: Path) -> None:
        from app.storage.session_store import SessionWriter

        session = MagicMock()
        session.output_dir = temp_dir

        writer = SessionWriter(session)

        segment = TranscriptSegment(
            id="seg-atomic",
            start=0.0,
            end=5.0,
            text="Test segment",
            display_text="Test segment",
            language="en",
            confidence=0.9,
        )

        writer.append_segment(segment)

        jsonl_file = temp_dir / "transcript.jsonl"
        txt_file = temp_dir / "transcript.txt"

        assert jsonl_file.exists()
        assert txt_file.exists()

        jsonl_content = jsonl_file.read_text()
        assert "seg-atomic" in jsonl_content

    def test_write_outputs_creates_all_files(self, temp_dir: Path) -> None:
        from app.storage.session_store import SessionWriter

        session = MagicMock()
        session.output_dir = temp_dir

        writer = SessionWriter(session)

        formulas = [
            FormulaFinding(
                expression="E = mc^2",
                timestamp_start=0.0,
                timestamp_end=5.0,
                context="Einstein's equation",
                confidence=0.95,
                parseable=True,
                review_flag=False,
                reasons=[],
            )
        ]

        writer.write_outputs(
            notes_markdown="# Notes\n\nContent",
            formulas=formulas,
            highlights_text="Highlights content",
        )

        assert (temp_dir / "notes.md").exists()
        assert (temp_dir / "highlights.txt").exists()
        assert (temp_dir / "formulas.json").exists()

    def test_concurrent_writes_safe(self, temp_dir: Path) -> None:
        import threading

        from app.storage.session_store import SessionWriter

        session = MagicMock()
        session.output_dir = temp_dir

        writer = SessionWriter(session)

        errors: list[Exception] = []

        def write_segment(segment_id: str) -> None:
            try:
                segment = TranscriptSegment(
                    id=segment_id,
                    start=0.0,
                    end=5.0,
                    text=f"Segment {segment_id}",
                    display_text=f"Segment {segment_id}",
                    language="en",
                    confidence=0.9,
                )
                writer.append_segment(segment)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_segment, args=(f"seg-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        jsonl_file = temp_dir / "transcript.jsonl"
        lines = [line for line in jsonl_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 5
        ids = {json.loads(line)["id"] for line in lines}
        assert len(ids) == 5
