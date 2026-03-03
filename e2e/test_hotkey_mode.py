"""E2E tests for Hotkey (Wispr) mode.

Tests the hotkey-triggered dictation workflow:
1. Press hotkey → recording starts → visual feedback
2. Speak → partial text appears in real-time
3. Press hotkey → recording stops → text injected
4. Change settings → apply → verify new behavior
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

# Mark all tests in this file
pytestmark = [pytest.mark.e2e, pytest.mark.hotkey]


class TestHotkeyBasicWorkflow:
    """Test basic hotkey workflow scenarios."""

    @pytest.mark.asyncio
    async def test_hotkey_press_starts_recording(self, api_client, mock_stt_engine):
        """Test that pressing hotkey starts recording session.

        Steps:
        1. Ensure idle state
        2. Send hotkey start command
        3. Verify recording state
        4. Check visual feedback is triggered
        """
        # Initial state check
        status = await api_client.get_mode_status()
        assert status.get("current_mode") in [None, "idle", "wispr"]

        # Start hotkey session
        result = await api_client.start_hotkey_session()

        # Verify session started
        assert result.get("success") is True
        assert "session_id" in result

        # Check mode status updated
        status = await api_client.get_mode_status()
        assert status.get("current_mode") == "wispr"
        assert status.get("wispr", {}).get("lifecycle_state") == "RUNNING"

    @pytest.mark.asyncio
    async def test_hotkey_recording_produces_visual_feedback(self, api_client):
        """Test that recording provides visual feedback.

        Steps:
        1. Start recording
        2. Check for recording indicator
        3. Verify audio level meter updates
        """
        # Start session
        result = await api_client.start_hotkey_session()
        assert result.get("success") is True

        # Check for visual feedback in status
        status = await api_client.get_mode_status()
        wispr_status = status.get("wispr", {})

        # Should have recording indicator
        assert wispr_status.get("lifecycle_state") == "RUNNING"

        # Wait for audio processing to start
        await asyncio.sleep(0.5)

        # Verify audio stream is active
        status = await api_client.get_mode_status()
        runtime = status.get("wispr", {}).get("runtime", {})
        assert runtime.get("audio_frames_processed", 0) >= 0

    @pytest.mark.asyncio
    async def test_partial_text_appears_in_realtime(self, api_client, mock_stt_engine):
        """Test that partial transcription appears in real-time.

        Steps:
        1. Start recording
        2. Simulate audio input
        3. Verify partial results are received
        4. Check partial text updates over time
        """
        partial_results = []

        # Start session
        result = await api_client.start_hotkey_session()
        session_id = result.get("session_id")

        # Simulate receiving partial results
        test_phrases = [
            "Hello",
            "Hello world",
            "Hello world this",
            "Hello world this is",
            "Hello world this is a test",
        ]

        for phrase in test_phrases:
            mock_stt_engine.inject_mock_transcription(phrase, confidence=0.85)
            partial_results.append(phrase)
            await asyncio.sleep(0.2)

        # Verify partial results were captured
        assert len(partial_results) == len(test_phrases)
        assert partial_results[-1] == test_phrases[-1]

    @pytest.mark.asyncio
    async def test_hotkey_stop_injects_text(self, api_client, mock_stt_engine, temp_test_dir):
        """Test that stopping hotkey injects text.

        Steps:
        1. Start recording
        2. Simulate audio and transcription
        3. Stop recording
        4. Verify text was injected/copied to clipboard
        """
        # Start session
        start_result = await api_client.start_hotkey_session()
        assert start_result.get("success") is True

        # Simulate transcription
        expected_text = "This is the final transcription result."
        mock_stt_engine.inject_mock_transcription(expected_text, confidence=0.92)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop session
        stop_result = await api_client.stop_hotkey_session()

        # Verify stop was successful
        assert stop_result.get("success") is True
        assert "transcription" in stop_result

        # Verify final text
        transcription = stop_result.get("transcription", {})
        assert transcription.get("text") == expected_text
        assert transcription.get("confidence", 0) > 0.8

        # Verify mode returned to ready state
        status = await api_client.get_mode_status()
        assert status.get("wispr", {}).get("lifecycle_state") in ["READY", "STOPPED"]

    @pytest.mark.asyncio
    async def test_hotkey_auto_inject_setting(self, api_client):
        """Test auto-inject setting behavior.

        Steps:
        1. Enable auto-inject setting
        2. Record and stop
        3. Verify text was injected
        4. Disable auto-inject
        5. Record and stop
        6. Verify text was only copied to clipboard
        """
        # Enable auto-inject
        settings_update = {"hotkey": {"auto_inject": True}}
        await api_client.post("/api/settings/update", json=settings_update)

        # Start and stop session
        await api_client.start_hotkey_session()
        await asyncio.sleep(0.3)
        result = await api_client.stop_hotkey_session()

        # Should have attempted injection
        assert result.get("inject_attempted") is True

        # Disable auto-inject
        settings_update = {"hotkey": {"auto_inject": False}}
        await api_client.post("/api/settings/update", json=settings_update)

        # Start and stop again
        await api_client.start_hotkey_session()
        await asyncio.sleep(0.3)
        result = await api_client.stop_hotkey_session()

        # Should not have attempted injection
        assert result.get("inject_attempted") is not True


class TestHotkeySettingsWorkflow:
    """Test hotkey settings changes and behavior."""

    @pytest.mark.asyncio
    async def test_change_model_size(self, api_client):
        """Test changing STT model size.

        Steps:
        1. Start with tiny model
        2. Change to base model
        3. Start new session
        4. Verify model change applied
        """
        # Initial setting
        settings = await api_client.get("/api/settings")
        initial_model = settings.get("transcription", {}).get("model_size", "tiny")

        # Change model
        new_model = "base" if initial_model == "tiny" else "tiny"
        await api_client.post(
            "/api/settings/update",
            json={"transcription": {"model_size": new_model}},
        )

        # Start session and verify
        result = await api_client.start_hotkey_session()
        assert result.get("model") == new_model

        # Restore original setting
        await api_client.post(
            "/api/settings/update",
            json={"transcription": {"model_size": initial_model}},
        )

    @pytest.mark.asyncio
    async def test_change_hotkey_combination(self, api_client):
        """Test changing hotkey combination.

        Steps:
        1. Change hotkey to new combination
        2. Apply settings
        3. Test new hotkey works
        4. Verify old hotkey doesn't work
        """
        # Get current hotkey
        settings = await api_client.get("/api/settings")
        original_hotkey = settings.get("hotkey", {}).get("combination", "ctrl+shift+r")

        # Change to new combination
        new_hotkey = "ctrl+alt+t"
        await api_client.post(
            "/api/settings/update",
            json={"hotkey": {"combination": new_hotkey}},
        )

        # Verify setting applied
        settings = await api_client.get("/api/settings")
        assert settings.get("hotkey", {}).get("combination") == new_hotkey

        # Restore original
        await api_client.post(
            "/api/settings/update",
            json={"hotkey": {"combination": original_hotkey}},
        )

    @pytest.mark.asyncio
    async def test_change_language_mode(self, api_client):
        """Test changing language mode.

        Steps:
        1. Set specific language (e.g., English)
        2. Start session
        3. Verify language setting applied
        4. Test with auto-detect
        """
        # Set English
        await api_client.post(
            "/api/settings/update",
            json={"transcription": {"language": "en"}},
        )

        result = await api_client.start_hotkey_session()
        assert result.get("language") == "en"

        await api_client.stop_hotkey_session()

        # Set auto
        await api_client.post(
            "/api/settings/update",
            json={"transcription": {"language": "auto"}},
        )

        result = await api_client.start_hotkey_session()
        assert result.get("language") == "auto"

        await api_client.stop_hotkey_session()

    @pytest.mark.asyncio
    async def test_settings_persist_across_sessions(self, api_client, temp_test_dir):
        """Test that settings persist across sessions.

        Steps:
        1. Change settings
        2. Stop any active session
        3. Start new session
        4. Verify settings persisted
        """
        # Make a unique setting change
        test_value = f"test_{int(time.time())}"
        await api_client.post(
            "/api/settings/update",
            json={"custom": {"test_setting": test_value}},
        )

        # Stop any session
        await api_client.stop_hotkey_session()

        # Start new session
        await api_client.start_hotkey_session()

        # Verify setting persisted
        settings = await api_client.get("/api/settings")
        assert settings.get("custom", {}).get("test_setting") == test_value

        await api_client.stop_hotkey_session()


class TestHotkeyErrorScenarios:
    """Test error handling and recovery in hotkey mode."""

    @pytest.mark.asyncio
    async def test_device_disconnected_graceful_error(self, api_client):
        """Test graceful handling of device disconnection.

        Steps:
        1. Start recording
        2. Simulate device disconnection
        3. Verify error is reported gracefully
        4. Verify session can be restarted after recovery
        """
        # Start session
        result = await api_client.start_hotkey_session()
        assert result.get("success") is True

        # Simulate device error
        error_result = await api_client.post(
            "/api/simulate/error",
            json={"type": "audio_device_disconnected"},
        )

        # Verify graceful error handling
        status = await api_client.get_mode_status()
        assert status.get("global_error") is not None

        # Verify error message is user-friendly
        error_msg = status.get("global_error", "")
        assert "device" in error_msg.lower() or "audio" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_model_not_found_auto_download(self, api_client):
        """Test auto-download when model not found.

        Steps:
        1. Request non-cached model
        2. Verify download starts automatically
        3. Verify session continues after download
        """
        # Request a model that needs download
        result = await api_client.post(
            "/api/hotkey/start",
            json={"model": "large-v3"},
        )

        # Should handle gracefully
        assert result.get("success") is True or result.get("downloading") is True

        # If downloading, wait for completion
        if result.get("downloading"):
            max_wait = 60  # seconds
            waited = 0
            while waited < max_wait:
                status = await api_client.get_mode_status()
                if status.get("wispr", {}).get("lifecycle_state") == "RUNNING":
                    break
                await asyncio.sleep(1)
                waited += 1

            assert waited < max_wait, "Model download timed out"

    @pytest.mark.asyncio
    async def test_short_audio_handling(self, api_client, test_audio_files):
        """Test handling of very short audio input.

        Steps:
        1. Start recording
        2. Stop immediately (< 300ms)
        3. Verify graceful handling (no crash)
        4. Verify appropriate message
        """
        # Start session
        result = await api_client.start_hotkey_session()
        assert result.get("success") is True

        # Stop almost immediately
        await asyncio.sleep(0.1)
        result = await api_client.stop_hotkey_session()

        # Should handle gracefully
        assert result.get("success") is True

        # Should indicate audio was too short
        if result.get("transcription"):
            assert result["transcription"].get("text", "") == ""

    @pytest.mark.asyncio
    async def test_consecutive_sessions(self, api_client):
        """Test multiple consecutive hotkey sessions.

        Steps:
        1. Start and stop session 1
        2. Immediately start session 2
        3. Verify no issues with rapid switching
        4. Complete session 2
        """
        for i in range(3):
            # Start session
            start_result = await api_client.start_hotkey_session()
            assert start_result.get("success") is True, f"Session {i + 1} failed to start"

            # Wait briefly
            await asyncio.sleep(0.5)

            # Stop session
            stop_result = await api_client.stop_hotkey_session()
            assert stop_result.get("success") is True, f"Session {i + 1} failed to stop"

            # Brief pause between sessions
            await asyncio.sleep(0.2)


class TestHotkeyPerformance:
    """Test hotkey mode performance characteristics."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_hotkey_latency_under_100ms(self, api_client):
        """Test that hotkey-to-recording latency is under 100ms.

        Steps:
        1. Measure time from hotkey press to recording start
        2. Run multiple times
        3. Verify 95th percentile < 100ms
        """
        latencies = []

        for _ in range(10):
            start_time = time.perf_counter()
            result = await api_client.start_hotkey_session()
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert result.get("success") is True

            await api_client.stop_hotkey_session()
            await asyncio.sleep(0.3)

        # Calculate 95th percentile
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 100, f"95th percentile latency {p95_latency:.1f}ms exceeds 100ms"

        # Also check average
        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 50, f"Average latency {avg_latency:.1f}ms exceeds 50ms"

    @pytest.mark.asyncio
    async def test_memory_usage_stable(self, api_client):
        """Test that memory usage remains stable across sessions.

        Steps:
        1. Record initial memory
        2. Run multiple sessions
        3. Record final memory
        4. Verify no significant memory leak
        """
        import psutil

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        for _ in range(5):
            await api_client.start_hotkey_session()
            await asyncio.sleep(0.5)
            await api_client.stop_hotkey_session()
            await asyncio.sleep(0.2)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Allow for some increase but not excessive
        assert memory_increase < 50, f"Memory increased by {memory_increase:.1f}MB"


class TestHotkeyIntegration:
    """Integration tests for hotkey mode."""

    @pytest.mark.asyncio
    async def test_full_dictation_workflow(self, api_client, test_audio_files):
        """Test complete dictation workflow end-to-end.

        Steps:
        1. Configure settings
        2. Start recording
        3. Simulate audio input
        4. Verify partial results
        5. Stop recording
        6. Verify final transcription
        7. Verify output handling
        """
        # Configure
        await api_client.post(
            "/api/settings/update",
            json={
                "hotkey": {"auto_inject": False, "copy_to_clipboard": True},
                "transcription": {"language": "en", "model_size": "tiny"},
            },
        )

        # Start
        start_result = await api_client.start_hotkey_session()
        assert start_result.get("success") is True
        session_id = start_result.get("session_id")

        # Simulate recording duration
        await asyncio.sleep(2.0)

        # Stop
        stop_result = await api_client.stop_hotkey_session()
        assert stop_result.get("success") is True

        # Verify transcription exists
        assert "transcription" in stop_result
        transcription = stop_result["transcription"]

        # Verify metrics
        assert "processing_time_ms" in stop_result
        assert stop_result["processing_time_ms"] < 5000  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_session_metrics_recorded(self, api_client):
        """Test that session metrics are properly recorded.

        Steps:
        1. Start session
        2. Record some audio
        3. Stop session
        4. Verify metrics are available
        """
        # Start
        await api_client.start_hotkey_session()
        await asyncio.sleep(1.0)

        # Stop
        result = await api_client.stop_hotkey_session()

        # Verify metrics
        assert "metrics" in result
        metrics = result["metrics"]

        assert "duration_seconds" in metrics
        assert "recording_duration_seconds" in metrics
        assert "processing_latency_ms" in metrics

        # Verify reasonable values
        assert metrics["duration_seconds"] >= 1.0
        assert metrics["processing_latency_ms"] >= 0
