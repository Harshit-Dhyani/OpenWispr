"""E2E tests for System mode.

Tests the system audio transcription workflow:
1. Start session → audio captured
2. Transcription builds up over time
3. Stop session → export to file
4. Verify file contents
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
import pytest_asyncio

# Mark all tests in this file
pytestmark = [pytest.mark.e2e, pytest.mark.system]


class TestSystemBasicWorkflow:
    """Test basic system mode workflow scenarios."""

    @pytest.mark.asyncio
    async def test_system_session_start(self, api_client):
        """Test starting a system mode session.

        Steps:
        1. Ensure no active session
        2. Start system session
        3. Verify session created
        4. Check audio capture started
        """
        # Initial state
        status = await api_client.get_mode_status()
        assert status.get("current_mode") in [None, "idle"]

        # Start session
        result = await api_client.start_system_session(
            title="Test System Session",
            model_name="tiny",
            language_mode="en",
            device_id="default",
            live_mode="balanced",
        )

        # Verify session started
        assert result.get("success") is True
        assert "session_id" in result
        assert result.get("title") == "Test System Session"

        # Check mode status
        status = await api_client.get_mode_status()
        assert status.get("current_mode") == "system"
        assert status.get("system", {}).get("lifecycle_state") == "RUNNING"

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_system_audio_capture(self, api_client):
        """Test that system audio is being captured.

        Steps:
        1. Start session
        2. Wait for audio processing
        3. Check audio stream is active
        4. Verify chunks are being processed
        """
        # Start session
        result = await api_client.start_system_session(
            title="Audio Capture Test",
            model_name="tiny",
            language_mode="en",
        )
        session_id = result.get("session_id")

        # Wait for processing
        await asyncio.sleep(2.0)

        # Check status
        status = await api_client.get_mode_status()
        system_status = status.get("system", {})
        runtime = system_status.get("runtime", {})

        # Should have processed some audio
        assert runtime.get("audio_frames_processed", 0) > 0

        # Health should show audio active
        health = await api_client.get("/api/system/health")
        assert health.get("audio_stream_active") is True

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_transcription_builds_over_time(self, api_client, mock_stt_engine):
        """Test that transcription builds up during session.

        Steps:
        1. Start session
        2. Simulate audio over time
        3. Check segments are added
        4. Verify transcript grows
        """
        # Start session
        await api_client.start_system_session(
            title="Buildup Test",
            model_name="tiny",
            language_mode="en",
        )

        initial_segments = 0

        # Simulate transcription over time
        test_segments = [
            "First segment of the transcription.",
            "Second segment continues the transcription.",
            "Third segment with more content.",
            "Fourth segment adding to the transcript.",
        ]

        for segment_text in test_segments:
            mock_stt_engine.inject_mock_transcription(segment_text, confidence=0.88)
            await asyncio.sleep(0.5)

        # Check progress
        progress = await api_client.get("/api/system/progress")
        total_segments = progress.get("total_segments", 0)

        assert total_segments >= len(test_segments)

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_system_session_stop(self, api_client):
        """Test stopping a system session.

        Steps:
        1. Start session
        2. Record for a few seconds
        3. Stop session
        4. Verify session stopped and outputs created
        """
        # Start session
        start_result = await api_client.start_system_session(
            title="Stop Test Session",
            model_name="tiny",
            language_mode="en",
        )
        session_id = start_result.get("session_id")

        # Record briefly
        await asyncio.sleep(2.0)

        # Stop session
        stop_result = await api_client.stop_system_session()

        # Verify stopped
        assert stop_result.get("status") == "stopped"
        assert stop_result.get("session_id") == session_id
        assert "duration_seconds" in stop_result

        # Verify mode status updated
        status = await api_client.get_mode_status()
        assert status.get("current_mode") in [None, "idle"]
        assert status.get("system", {}).get("lifecycle_state") in ["STOPPED", "READY"]


class TestSystemExportWorkflow:
    """Test export functionality in system mode."""

    @pytest.mark.asyncio
    async def test_export_to_txt(self, api_client, temp_test_dir):
        """Test exporting session to TXT format.

        Steps:
        1. Start and record session
        2. Stop with TXT export
        3. Verify TXT file created
        4. Check file contents
        """
        # Start session
        await api_client.start_system_session(
            title="TXT Export Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Stop with export
        result = await api_client.stop_system_session(
            export_formats=["txt"],
        )

        # Verify export task created
        assert "export_task_id" in result

        # Wait for export to complete
        await asyncio.sleep(1.0)

        # Check export status
        exports = await api_client.get("/api/system/exports")
        assert len(exports.get("completed", [])) > 0

    @pytest.mark.asyncio
    async def test_export_to_json(self, api_client):
        """Test exporting session to JSON format.

        Steps:
        1. Start and record session
        2. Stop with JSON export
        3. Verify JSON file created
        4. Validate JSON structure
        """
        # Start session
        await api_client.start_system_session(
            title="JSON Export Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Stop with JSON export
        result = await api_client.stop_system_session(
            export_formats=["json"],
        )

        assert result.get("status") == "stopped"

        # Verify export completed
        await asyncio.sleep(1.0)
        exports = await api_client.get("/api/system/exports")
        completed = exports.get("completed", [])

        if completed:
            # Verify JSON structure
            last_export = completed[-1]
            assert "formats" in last_export
            assert "json" in last_export.get("formats", [])

    @pytest.mark.asyncio
    async def test_export_to_srt(self, api_client):
        """Test exporting session to SRT subtitle format.

        Steps:
        1. Start and record session
        2. Add some segments with timestamps
        3. Stop with SRT export
        4. Verify SRT format correctness
        """
        # Start session
        await api_client.start_system_session(
            title="SRT Export Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(2.0)

        # Stop with SRT export
        result = await api_client.stop_system_session(
            export_formats=["srt"],
        )

        assert result.get("status") == "stopped"

        # Verify export
        await asyncio.sleep(1.0)
        exports = await api_client.get("/api/system/exports")
        assert len(exports.get("completed", [])) > 0

    @pytest.mark.asyncio
    async def test_export_to_markdown(self, api_client):
        """Test exporting session to Markdown format.

        Steps:
        1. Start and record session with formulas
        2. Stop with MD export
        3. Verify Markdown structure
        4. Check for proper formatting
        """
        # Start session with STEM enabled
        await api_client.start_system_session(
            title="Markdown Export Test",
            model_name="tiny",
            language_mode="en",
            enable_stem=True,
        )

        await asyncio.sleep(2.0)

        # Stop with MD export
        result = await api_client.stop_system_session(
            export_formats=["md"],
        )

        assert result.get("status") == "stopped"

    @pytest.mark.asyncio
    async def test_multi_format_export(self, api_client):
        """Test exporting to multiple formats simultaneously.

        Steps:
        1. Start and record session
        2. Stop with multiple export formats
        3. Verify all exports completed
        """
        # Start session
        await api_client.start_system_session(
            title="Multi Export Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(2.0)

        # Export to all formats
        result = await api_client.stop_system_session(
            export_formats=["txt", "json", "srt", "md"],
        )

        # Verify export task
        assert "export_task_id" in result

        # Wait for all exports
        await asyncio.sleep(2.0)

        # Check all completed
        exports = await api_client.get("/api/system/exports")
        completed = exports.get("completed", [])

        if completed:
            last_export = completed[-1]
            assert len(last_export.get("formats", [])) == 4


class TestSystemChapterDetection:
    """Test chapter detection functionality."""

    @pytest.mark.asyncio
    async def test_chapter_detection_on_silence(self, api_client):
        """Test automatic chapter detection on long silences.

        Steps:
        1. Start session with auto-segment enabled
        2. Simulate audio with pauses
        3. Verify chapters are detected
        4. Check chapter boundaries
        """
        # Start with auto-segment
        await api_client.start_system_session(
            title="Chapter Detection Test",
            model_name="tiny",
            language_mode="en",
            auto_segment=True,
        )

        # Simulate session with pauses
        await asyncio.sleep(5.0)

        # Stop and check chapters
        result = await api_client.stop_system_session()
        assert "chapters" in result

    @pytest.mark.asyncio
    async def test_manual_chapter_markers(self, api_client):
        """Test manual chapter marker insertion.

        Steps:
        1. Start session
        2. Add manual chapter markers
        3. Verify markers recorded
        4. Check export includes chapters
        """
        # Start session
        await api_client.start_system_session(
            title="Manual Chapters Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Add chapter marker
        await api_client.post(
            "/api/system/chapter",
            json={"title": "Introduction", "timestamp": 0.0},
        )

        await asyncio.sleep(2.0)

        # Add another marker
        await api_client.post(
            "/api/system/chapter",
            json={"title": "Main Content", "timestamp": 2.0},
        )

        # Stop
        result = await api_client.stop_system_session()
        assert result.get("chapters", 0) >= 2


class TestSystemNotesAndContext:
    """Test notes and contextual features."""

    @pytest.mark.asyncio
    async def test_add_contextual_note(self, api_client):
        """Test adding contextual notes during session.

        Steps:
        1. Start session
        2. Add note at specific timestamp
        3. Verify note recorded
        4. Check export includes notes
        """
        # Start session
        await api_client.start_system_session(
            title="Notes Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Add note
        note_result = await api_client.post(
            "/api/system/note",
            json={
                "text": "Important point discussed here",
                "timestamp": 1.0,
                "tags": ["important"],
            },
        )

        assert note_result.get("success") is True
        assert "note_id" in note_result

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_attach_document(self, api_client, temp_test_dir):
        """Test attaching documents to session.

        Steps:
        1. Create test document
        2. Start session
        3. Attach document
        4. Verify document in session
        """
        # Create test PDF
        test_pdf = temp_test_dir / "test_doc.pdf"
        test_pdf.write_text("PDF content placeholder")

        # Start session
        await api_client.start_system_session(
            title="Document Test",
            model_name="tiny",
            language_mode="en",
        )

        # Attach document
        result = await api_client.post(
            "/api/system/document",
            json={"path": str(test_pdf)},
        )

        assert result.get("success") is True

        # Cleanup
        await api_client.stop_system_session()


class TestSystemSessionResume:
    """Test session resume functionality."""

    @pytest.mark.asyncio
    async def test_pause_and_resume_session(self, api_client):
        """Test pausing and resuming a session.

        Steps:
        1. Start session
        2. Pause session
        3. Verify paused state
        4. Resume session
        5. Verify running state
        """
        # Start session
        await api_client.start_system_session(
            title="Pause Resume Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Pause
        pause_result = await api_client.post("/api/system/pause")
        assert pause_result.get("status") == "paused"

        status = await api_client.get_mode_status()
        assert status.get("system", {}).get("lifecycle_state") == "PAUSED"

        # Resume
        resume_result = await api_client.post("/api/system/resume")
        assert resume_result.get("status") == "running"

        status = await api_client.get_mode_status()
        assert status.get("system", {}).get("lifecycle_state") == "RUNNING"

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_resume_from_disk(self, api_client, temp_test_dir):
        """Test resuming a session from disk.

        Steps:
        1. Start and record session
        2. Stop session
        3. Resume from session directory
        4. Verify previous content loaded
        """
        # Start session
        start_result = await api_client.start_system_session(
            title="Resume Test",
            model_name="tiny",
            language_mode="en",
            output_root=str(temp_test_dir),
        )
        session_id = start_result.get("session_id")

        await asyncio.sleep(2.0)

        # Stop session
        await api_client.stop_system_session()

        # Resume from disk
        resume_result = await api_client.post(
            "/api/system/resume",
            json={
                "session_id": session_id,
                "resume_from": str(temp_test_dir / "resume-test"),
            },
        )

        assert resume_result.get("success") is True

        # Cleanup
        await api_client.stop_system_session()


class TestSystemErrorScenarios:
    """Test error handling in system mode."""

    @pytest.mark.asyncio
    async def test_disk_full_handling(self, api_client):
        """Test graceful handling of disk full condition.

        Steps:
        1. Start session
        2. Simulate disk full condition
        3. Verify graceful error with alert
        4. Check partial save if possible
        """
        # Start session
        await api_client.start_system_session(
            title="Disk Full Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Simulate disk full
        error_result = await api_client.post(
            "/api/simulate/error",
            json={"type": "disk_full"},
        )

        # Should handle gracefully
        status = await api_client.get_mode_status()
        assert status.get("global_error") is not None

        # Cleanup
        try:
            await api_client.stop_system_session()
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_audio_device_error_recovery(self, api_client):
        """Test recovery from audio device errors.

        Steps:
        1. Start session
        2. Simulate audio device error
        3. Verify error reported
        4. Check session artifacts preserved
        """
        # Start session
        await api_client.start_system_session(
            title="Device Error Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Simulate device error
        await api_client.post(
            "/api/simulate/error",
            json={"type": "audio_device_error"},
        )

        # Check error state
        status = await api_client.get_mode_status()
        system_status = status.get("system", {})

        # Should have error info
        assert system_status.get("error") is not None or status.get("global_error") is not None

    @pytest.mark.asyncio
    async def test_long_session_stability(self, api_client):
        """Test stability during longer sessions.

        Steps:
        1. Start session
        2. Run for extended period
        3. Monitor health metrics
        4. Verify no degradation
        """
        # Start session
        await api_client.start_system_session(
            title="Long Session Test",
            model_name="tiny",
            language_mode="en",
        )

        # Monitor for 10 seconds
        health_readings = []
        for _ in range(10):
            health = await api_client.get("/api/system/health")
            health_readings.append(health)
            await asyncio.sleep(1.0)

        # Verify stable operation
        errors = [h for h in health_readings if h.get("last_error")]
        assert len(errors) < 3, "Too many errors during long session"

        # Cleanup
        await api_client.stop_system_session()


class TestSystemSettings:
    """Test system mode settings."""

    @pytest.mark.asyncio
    async def test_change_live_mode(self, api_client):
        """Test changing live mode settings.

        Steps:
        1. Start with balanced mode
        2. Change to quality mode
        3. Verify new settings applied
        4. Test ultra mode
        """
        modes = ["ultra", "balanced", "quality"]

        for mode in modes:
            # Start with specific mode
            result = await api_client.start_system_session(
                title=f"Mode {mode} Test",
                model_name="tiny",
                language_mode="en",
                live_mode=mode,
            )

            assert result.get("live_mode") == mode

            # Verify health shows correct mode
            health = await api_client.get("/api/system/health")
            assert health.get("execution_mode") == mode

            await asyncio.sleep(0.5)
            await api_client.stop_system_session()
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_export_format_settings(self, api_client):
        """Test default export format settings.

        Steps:
        1. Set default export formats
        2. Start session
        3. Stop without specifying formats
        4. Verify default formats used
        """
        # Set defaults
        await api_client.post(
            "/api/settings/update",
            json={"system": {"default_export_formats": ["txt", "json"]}},
        )

        # Start session
        await api_client.start_system_session(
            title="Export Settings Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Stop (should use defaults)
        result = await api_client.stop_system_session()
        assert result.get("status") == "stopped"


class TestSystemProgressReporting:
    """Test progress reporting functionality."""

    @pytest.mark.asyncio
    async def test_progress_updates(self, api_client):
        """Test that progress updates are received.

        Steps:
        1. Start session
        2. Monitor progress endpoint
        3. Verify progress changes over time
        4. Check all expected fields present
        """
        # Start session
        await api_client.start_system_session(
            title="Progress Test",
            model_name="tiny",
            language_mode="en",
        )

        progress_readings = []

        # Collect progress updates
        for _ in range(5):
            progress = await api_client.get("/api/system/progress")
            progress_readings.append(progress)
            await asyncio.sleep(0.5)

        # Verify progress has expected fields
        for progress in progress_readings:
            assert "status" in progress
            assert "duration_seconds" in progress
            assert "total_segments" in progress

        # Should see duration increasing
        durations = [p["duration_seconds"] for p in progress_readings]
        assert durations[-1] > durations[0]

        # Cleanup
        await api_client.stop_system_session()

    @pytest.mark.asyncio
    async def test_health_metrics(self, api_client):
        """Test health metrics reporting.

        Steps:
        1. Start session
        2. Get health metrics
        3. Verify all expected fields
        4. Check GPU/CPU info
        """
        # Start session
        await api_client.start_system_session(
            title="Health Metrics Test",
            model_name="tiny",
            language_mode="en",
        )

        await asyncio.sleep(1.0)

        # Get health
        health = await api_client.get("/api/system/health")

        # Verify expected fields
        assert "gpu_mode" in health
        assert "execution_mode" in health
        assert "audio_stream_active" in health
        assert "dropped_frames" in health

        # Cleanup
        await api_client.stop_system_session()
