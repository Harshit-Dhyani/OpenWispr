"""Lightweight session handler for hotkey/microphone transcription mode.

Designed for rapid start/stop dictation with minimal resource footprint.
All audio data stays in memory during recording for <100ms hotkey response.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class HotkeySessionState(Enum):
    """State machine states for hotkey session lifecycle."""

    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass(slots=True)
class HotkeySessionMetrics:
    """Performance metrics for a hotkey session."""

    session_id: str
    start_time: float = 0.0
    stop_time: float = 0.0
    first_audio_time: float = 0.0
    first_partial_time: float = 0.0
    processing_start_time: float = 0.0
    completion_time: float = 0.0
    total_audio_samples: int = 0
    partial_results_count: int = 0
    final_text_length: int = 0
    confidence: float = 0.0
    inject_success: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Total session duration from start to completion."""
        if self.start_time and self.completion_time:
            return self.completion_time - self.start_time
        return 0.0

    @property
    def recording_duration_seconds(self) -> float:
        """Duration of recording phase."""
        if self.start_time and self.stop_time:
            return self.stop_time - self.start_time
        return 0.0

    @property
    def hotkey_to_audio_latency_ms(self) -> float:
        """Latency from hotkey press to first audio capture."""
        if self.start_time and self.first_audio_time:
            return (self.first_audio_time - self.start_time) * 1000
        return 0.0

    @property
    def processing_latency_ms(self) -> float:
        """Time spent in processing phase."""
        if self.processing_start_time and self.completion_time:
            return (self.completion_time - self.processing_start_time) * 1000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "duration_seconds": round(self.duration_seconds, 3),
            "recording_duration_seconds": round(self.recording_duration_seconds, 3),
            "hotkey_to_audio_latency_ms": round(self.hotkey_to_audio_latency_ms, 2),
            "processing_latency_ms": round(self.processing_latency_ms, 2),
            "total_audio_samples": self.total_audio_samples,
            "partial_results_count": self.partial_results_count,
            "final_text_length": self.final_text_length,
            "confidence": round(self.confidence, 3),
            "inject_success": self.inject_success,
            "errors": self.errors,
        }


@dataclass(slots=True)
class HotkeySessionConfig:
    """Configuration for hotkey transcription sessions."""

    # Audio settings
    sample_rate: int = 16000
    max_duration_seconds: float = 60.0
    channels: int = 1

    # Behavior settings
    auto_inject: bool = True
    copy_to_clipboard: bool = True
    show_floating_window: bool = False
    save_sessions: bool = False

    # Model settings - use tiny for speed
    model_name: str = "tiny"
    language_mode: str = "auto"
    compute_type: str = "int8"
    device: str = "cpu"

    # Storage settings (only used if save_sessions=True)
    output_dir: Path | None = None

    # Performance settings
    streaming_window_ms: int = 400
    streaming_overlap_ms: int = 80
    vad_filter: bool = True
    beam_size: int = 1

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = Path.home() / ".openwispr" / "hotkey_sessions"


class TextInjector(Protocol):
    """Protocol for text injection implementations."""

    def inject(self, text: str) -> bool:
        """Inject text at current cursor position. Returns success status."""
        ...

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard. Returns success status."""
        ...


class PlatformTextInjector:
    """Cross-platform text injection with graceful fallback."""

    def __init__(self) -> None:
        self._platform = platform.system().lower()
        self._last_error: str | None = None

    def inject(self, text: str) -> bool:
        """Inject text at cursor position using platform-specific method."""
        try:
            if self._platform == "windows":
                return self._inject_windows(text)
            elif self._platform == "darwin":
                return self._inject_macos(text)
            elif self._platform == "linux":
                return self._inject_linux(text)
            else:
                self._last_error = f"Unsupported platform: {self._platform}"
                return False
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"Text injection failed: {e}")
            return False

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard."""
        try:
            if self._platform == "windows":
                return self._copy_windows(text)
            elif self._platform == "darwin":
                return self._copy_macos(text)
            elif self._platform == "linux":
                return self._copy_linux(text)
            else:
                return self._copy_fallback(text)
        except Exception as e:
            logger.warning(f"Clipboard copy failed: {e}")
            return False

    def _inject_windows(self, text: str) -> bool:
        """Windows text injection using clipboard + paste shortcut."""
        try:
            import ctypes

            # Copy to clipboard first
            if not self._copy_windows(text):
                return False

            # Simulate Ctrl+V
            user32 = ctypes.windll.user32

            # Key codes
            VK_CONTROL = 0x11
            VK_V = 0x56

            # Press Ctrl
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            # Press V
            user32.keybd_event(VK_V, 0, 0, 0)
            # Release V
            user32.keybd_event(VK_V, 0, 2, 0)
            # Release Ctrl
            user32.keybd_event(VK_CONTROL, 0, 2, 0)

            return True
        except Exception as e:
            logger.debug(f"Windows injection failed: {e}")
            return False

    def _inject_macos(self, text: str) -> bool:
        """macOS text injection using AppleScript."""
        try:
            escaped_text = text.replace('"', '\\"')
            script = f'''
                tell application "System Events"
                    keystroke "{escaped_text}"
                end tell
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except Exception as e:
            logger.debug(f"macOS injection failed: {e}")
            return False

    def _inject_linux(self, text: str) -> bool:
        """Linux text injection using xdotool or ydotool."""
        try:
            # Try xdotool first (X11)
            result = subprocess.run(
                ["xdotool", "type", "--delay", "0", text],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True

            # Fallback to ydotool (Wayland)
            subprocess.run(
                ["ydotool", "type", text],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except Exception as e:
            logger.debug(f"Linux injection failed: {e}")
            return False

    def _copy_windows(self, text: str) -> bool:
        """Windows clipboard using ctypes."""
        try:
            import ctypes

            CF_UNICODETEXT = 13
            GHND = 0x0042

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            # Open clipboard
            if not user32.OpenClipboard(0):
                return False

            try:
                user32.EmptyClipboard()

                # Allocate global memory
                text_bytes = text.encode("utf-16-le")
                size = len(text_bytes) + 2
                h_global = kernel32.GlobalAlloc(GHND, size)
                if not h_global:
                    return False

                # Lock and copy
                ptr = kernel32.GlobalLock(h_global)
                ctypes.memmove(ptr, text_bytes, len(text_bytes))
                ctypes.memset(ptr + len(text_bytes), 0, 2)
                kernel32.GlobalUnlock(h_global)

                # Set clipboard data
                user32.SetClipboardData(CF_UNICODETEXT, h_global)
                return True
            finally:
                user32.CloseClipboard()
        except Exception as e:
            logger.debug(f"Windows clipboard failed: {e}")
            return False

    def _copy_macos(self, text: str) -> bool:
        """macOS clipboard using pbcopy."""
        try:
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                text=True,
            )
            process.communicate(text, timeout=5)
            return process.returncode == 0
        except Exception as e:
            logger.debug(f"macOS clipboard failed: {e}")
            return False

    def _copy_linux(self, text: str) -> bool:
        """Linux clipboard using xclip or wl-copy."""
        try:
            # Try xclip first (X11)
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                text=True,
            )
            process.communicate(text, timeout=2)
            if process.returncode == 0:
                return True
        except Exception as e:
            logger.debug(f"Linux clipboard (xclip) failed: {e}")

        try:
            # Try wl-copy (Wayland)
            process = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
                text=True,
            )
            process.communicate(text, timeout=2)
            return process.returncode == 0
        except Exception as e:
            logger.debug(f"Linux clipboard failed: {e}")
            return False

    def _copy_fallback(self, text: str) -> bool:
        """Fallback clipboard using tkinter."""
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return True
        except Exception as e:
            logger.debug(f"Fallback clipboard failed: {e}")
            return False

    @property
    def last_error(self) -> str | None:
        return self._last_error


class CircularAudioBuffer:
    """Memory-only circular audio buffer for hotkey recording.

    Stores audio in memory without any disk I/O. Automatically overwrites
    oldest data when buffer is full (max 60 seconds).
    """

    def __init__(self, sample_rate: int = 16000, max_duration_seconds: float = 60.0) -> None:
        self.sample_rate = sample_rate
        self.max_duration_seconds = max_duration_seconds
        self.max_samples = int(sample_rate * max_duration_seconds)
        self._buffer: deque[float] = deque(maxlen=self.max_samples)
        self._lock = threading.Lock()
        self._start_time: float | None = None
        self._sample_count = 0

    def push(self, samples: np.ndarray) -> int:
        """Push audio samples to buffer. Returns number of samples added."""
        with self._lock:
            if self._start_time is None:
                self._start_time = time.monotonic()

            samples_list = samples.tolist() if isinstance(samples, np.ndarray) else list(samples)
            self._buffer.extend(samples_list)
            self._sample_count += len(samples_list)
            return len(samples_list)

    def get_all(self) -> np.ndarray:
        """Get all audio data as numpy array."""
        with self._lock:
            return np.array(self._buffer, dtype=np.float32)

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()
            self._start_time = None
            self._sample_count = 0

    @property
    def duration_seconds(self) -> float:
        """Current buffer duration in seconds."""
        with self._lock:
            return len(self._buffer) / self.sample_rate

    @property
    def is_full(self) -> bool:
        """Check if buffer has reached capacity."""
        with self._lock:
            return len(self._buffer) >= self.max_samples

    @property
    def sample_count(self) -> int:
        """Total number of samples stored."""
        with self._lock:
            return len(self._buffer)


class HotkeySession:
    """Lightweight session for hotkey-triggered dictation.

    Features:
    - Memory-only audio buffering (no disk I/O during recording)
    - <100ms hotkey-to-recording latency
    - Streaming transcription with partial results
    - Auto-inject or clipboard copy on completion
    - Optional session persistence (disabled by default)
    - Automatic cleanup after transcription

    State Machine:
        IDLE -> RECORDING -> PROCESSING -> COMPLETE
                   |           |
                   v           v
                 ERROR <------+
    """

    def __init__(
        self,
        config: HotkeySessionConfig | None = None,
        text_injector: TextInjector | None = None,
    ) -> None:
        self.config = config or HotkeySessionConfig()
        self._text_injector = text_injector or PlatformTextInjector()

        # State machine
        self._state = HotkeySessionState.IDLE
        self._state_lock = threading.RLock()
        self._error: str | None = None

        # Session identity
        self._session_id = uuid.uuid4().hex[:12]
        self._started_at: datetime | None = None

        # Audio buffer (memory-only)
        self._audio_buffer = CircularAudioBuffer(
            sample_rate=self.config.sample_rate,
            max_duration_seconds=self.config.max_duration_seconds,
        )

        # Transcription state
        self._transcription_result: str = ""
        self._partial_results: list[str] = []
        self._confidence = 0.0

        # Transcriber (lazy-loaded)
        self._transcriber: Any | None = None
        self._transcriber_lock = threading.Lock()

        # Metrics
        self._metrics = HotkeySessionMetrics(session_id=self._session_id)

        # Callbacks
        self._on_partial: Callable[[str], None] | None = None
        self._on_state_change: Callable[[HotkeySessionState, HotkeySessionState], None] | None = (
            None
        )
        self._on_complete: Callable[[str, HotkeySessionMetrics], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        # Stop event for recording thread
        self._stop_event = threading.Event()
        self._recording_thread: threading.Thread | None = None

        logger.debug(
            "HotkeySession initialized",
            extra={
                "session_id": self._session_id,
                "auto_inject": self.config.auto_inject,
                "save_sessions": self.config.save_sessions,
            },
        )

    @property
    def state(self) -> HotkeySessionState:
        """Current session state."""
        with self._state_lock:
            return self._state

    @property
    def session_id(self) -> str:
        """Unique session identifier."""
        return self._session_id

    @property
    def metrics(self) -> HotkeySessionMetrics:
        """Session performance metrics."""
        return self._metrics

    @property
    def transcription_result(self) -> str:
        """Final transcription result."""
        return self._transcription_result

    def set_callbacks(
        self,
        *,
        on_partial: Callable[[str], None] | None = None,
        on_state_change: Callable[[HotkeySessionState, HotkeySessionState], None] | None = None,
        on_complete: Callable[[str, HotkeySessionMetrics], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """Register session callbacks."""
        self._on_partial = on_partial
        self._on_state_change = on_state_change
        self._on_complete = on_complete
        self._on_error = on_error

    def _transition_state(self, new_state: HotkeySessionState) -> None:
        """Transition to new state with callback notification."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state

            logger.debug(
                "State transition",
                extra={
                    "session_id": self._session_id,
                    "from": old_state.name,
                    "to": new_state.name,
                },
            )

        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.warning(f"State change callback error: {e}")

    def start(self) -> bool:
        """Start recording session.

        Target: <100ms from hotkey press to recording start.
        Returns True if successfully started.
        """
        start_time = time.perf_counter()

        with self._state_lock:
            if self._state != HotkeySessionState.IDLE:
                logger.warning(
                    "Cannot start session: not in IDLE state",
                    extra={
                        "session_id": self._session_id,
                        "current_state": self._state.name,
                    },
                )
                return False

        try:
            # Reset state
            self._audio_buffer.clear()
            self._transcription_result = ""
            self._partial_results = []
            self._confidence = 0.0
            self._error = None
            self._stop_event.clear()

            # Initialize metrics
            self._metrics = HotkeySessionMetrics(session_id=self._session_id)
            self._metrics.start_time = time.monotonic()
            self._started_at = datetime.now(UTC)

            # Transition to recording
            self._transition_state(HotkeySessionState.RECORDING)

            # Start recording thread
            self._recording_thread = threading.Thread(
                target=self._recording_loop,
                name=f"hotkey-recording-{self._session_id}",
                daemon=True,
            )
            self._recording_thread.start()

            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Hotkey session started",
                extra={
                    "session_id": self._session_id,
                    "start_latency_ms": round(latency_ms, 2),
                },
            )

            return True

        except Exception as e:
            self._error = str(e)
            self._transition_state(HotkeySessionState.ERROR)
            logger.exception("Failed to start hotkey session")
            return False

    def stop(self) -> bool:
        """Stop recording and begin transcription.

        Returns True if successfully stopped and processing began.
        """
        with self._state_lock:
            if self._state != HotkeySessionState.RECORDING:
                logger.warning(
                    "Cannot stop session: not in RECORDING state",
                    extra={
                        "session_id": self._session_id,
                        "current_state": self._state.name,
                    },
                )
                return False

        try:
            self._metrics.stop_time = time.monotonic()
            self._stop_event.set()

            # Wait for recording thread to finish
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=1.0)

            # Transition to processing
            self._transition_state(HotkeySessionState.PROCESSING)
            self._metrics.processing_start_time = time.monotonic()

            # Start processing in background thread
            processing_thread = threading.Thread(
                target=self._process_transcription,
                name=f"hotkey-processing-{self._session_id}",
                daemon=True,
            )
            processing_thread.start()

            logger.info(
                "Hotkey session stopped, processing",
                extra={
                    "session_id": self._session_id,
                    "recording_duration": round(self._metrics.recording_duration_seconds, 3),
                    "audio_samples": self._audio_buffer.sample_count,
                },
            )

            return True

        except Exception as e:
            self._error = str(e)
            self._transition_state(HotkeySessionState.ERROR)
            if self._on_error:
                self._on_error(str(e))
            logger.exception("Failed to stop hotkey session")
            return False

    def _recording_loop(self) -> None:
        """Main recording loop - captures audio to memory buffer."""
        try:
            # Import here to avoid circular dependencies
            from app.audio.backends import open_audio_backend

            # Open audio backend with minimal latency settings
            selection = open_audio_backend(
                device_id=None,  # Use default device
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                block_size=int(self.config.sample_rate * 0.02),  # 20ms blocks for low latency
                preferred_backend="auto",
            )
            backend = selection.backend
            backend.start()

            first_audio = True
            consecutive_errors = 0
            max_errors = 5

            while not self._stop_event.is_set():
                try:
                    # Read audio block with short timeout
                    data = backend.read(timeout=0.05)

                    if data is not None and data.size > 0:
                        if first_audio:
                            self._metrics.first_audio_time = time.monotonic()
                            first_audio = False

                        # Push to memory buffer (no disk I/O)
                        count = self._audio_buffer.push(data)
                        self._metrics.total_audio_samples += count

                        consecutive_errors = 0

                        # Check for buffer full
                        if self._audio_buffer.is_full:
                            logger.warning(
                                "Audio buffer full, auto-stopping",
                                extra={"session_id": self._session_id},
                            )
                            self.stop()
                            break

                    # Optional: Process streaming partials here for real-time feedback
                    if self._on_partial and self._audio_buffer.duration_seconds > 0.5:
                        self._process_streaming_partial()

                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        raise RuntimeError(f"Audio capture failed: {e}")

        except Exception as e:
            self._error = str(e)
            self._metrics.errors.append(str(e))
            self._transition_state(HotkeySessionState.ERROR)
            if self._on_error:
                self._on_error(str(e))
            logger.exception("Recording loop error")

        finally:
            try:
                if "backend" in locals():
                    backend.stop()
            except Exception as e:
                logger.warning(f"Failed to stop audio backend: {e}")

    def _process_streaming_partial(self) -> None:
        """Process partial transcription for real-time feedback."""
        # This is a lightweight partial - full transcription happens on stop
        # Can be enhanced with actual streaming transcription for UI feedback
        pass

    def _process_transcription(self) -> None:
        """Process final transcription and handle output."""
        try:
            audio_data = self._audio_buffer.get_all()

            if len(audio_data) < self.config.sample_rate * 0.3:  # < 300ms
                logger.warning(
                    "Audio too short, skipping transcription",
                    extra={
                        "session_id": self._session_id,
                        "duration": len(audio_data) / self.config.sample_rate,
                    },
                )
                self._transcription_result = ""
                self._complete_session()
                return

            # Get or create transcriber
            with self._transcriber_lock:
                if self._transcriber is None:
                    self._transcriber = self._create_transcriber()

            # Transcribe
            result = self._transcribe_audio(audio_data)
            self._transcription_result = result.get("text", "")
            self._confidence = result.get("confidence", 0.0)

            self._metrics.final_text_length = len(self._transcription_result)
            self._metrics.confidence = self._confidence

            logger.info(
                "Transcription complete",
                extra={
                    "session_id": self._session_id,
                    "text_length": self._metrics.final_text_length,
                    "confidence": round(self._confidence, 3),
                },
            )

            # Handle output (inject/clipboard)
            self._handle_output()

            # Optional: Save session
            if self.config.save_sessions:
                self._save_session()

            self._complete_session()

        except Exception as e:
            self._error = str(e)
            self._metrics.errors.append(str(e))
            self._transition_state(HotkeySessionState.ERROR)
            if self._on_error:
                self._on_error(str(e))
            logger.exception("Transcription processing error")

    def _create_transcriber(self) -> Any:
        """Create lightweight transcriber instance."""
        from app.stt.fast_engine import FastTranscriber

        return FastTranscriber(
            model_name=self.config.model_name,
            device=self.config.device,
            compute_type=self.config.compute_type,
            beam_size=self.config.beam_size,
            best_of=1,
            temperature=0.0,
            vad_filter=self.config.vad_filter,
            language_mode=self.config.language_mode,
            execution_mode="fast",
            max_queue_items=4,
        )

    def _transcribe_audio(self, audio_data: np.ndarray) -> dict[str, Any]:
        """Transcribe audio data using configured transcriber."""
        if self._transcriber is None:
            raise RuntimeError("Transcriber not initialized")

        # Load model if needed
        if not hasattr(self._transcriber, "_model") or self._transcriber._model is None:
            self._transcriber.load_model()

        # Transcribe
        segments, info = self._transcriber._model.transcribe(
            audio_data,
            language=self.config.language_mode if self.config.language_mode != "auto" else None,
            beam_size=self.config.beam_size,
            best_of=1,
            temperature=0.0,
            vad_filter=self.config.vad_filter,
            vad_parameters={
                "threshold": 0.35,
                "min_silence_duration_ms": 200,
                "speech_pad_ms": 200,
            },
            word_timestamps=False,
        )

        # Collect results
        texts = []
        confidences = []

        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)
                # Calculate confidence proxy
                avg_logprob = getattr(segment, "avg_logprob", 0)
                no_speech_prob = getattr(segment, "no_speech_prob", 0)
                conf = max(0.0, min(0.99, 0.65 + (avg_logprob + 1.2) / 1.2 * 0.25))
                conf -= no_speech_prob * 0.25
                confidences.append(max(0.0, conf))

        full_text = " ".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": full_text,
            "confidence": avg_confidence,
            "language": getattr(info, "language", self.config.language_mode),
        }

    def _handle_output(self) -> None:
        """Handle text output (inject and/or clipboard)."""
        if not self._transcription_result:
            return

        text = self._transcription_result

        # Try auto-inject first if enabled
        if self.config.auto_inject:
            success = self._text_injector.inject(text)
            self._metrics.inject_success = success

            if not success:
                logger.warning(
                    "Text injection failed, falling back to clipboard",
                    extra={"session_id": self._session_id},
                )
                # Fallback to clipboard
                if self.config.copy_to_clipboard:
                    self._text_injector.copy_to_clipboard(text)
        elif self.config.copy_to_clipboard:
            # Clipboard only
            self._text_injector.copy_to_clipboard(text)

    def _save_session(self) -> None:
        """Save session to disk if enabled."""
        if not self.config.output_dir:
            return

        try:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"hotkey_{self._session_id}_{timestamp}"

            # Save transcript
            transcript_path = self.config.output_dir / f"{filename}.txt"
            transcript_path.write_text(self._transcription_result, encoding="utf-8")

            # Save metrics
            metrics_path = self.config.output_dir / f"{filename}.json"
            import json

            metrics_path.write_text(
                json.dumps(self._metrics.to_dict(), indent=2),
                encoding="utf-8",
            )

            logger.debug(
                "Session saved",
                extra={
                    "session_id": self._session_id,
                    "path": str(transcript_path),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to save session: {e}")

    def _complete_session(self) -> None:
        """Complete the session and cleanup."""
        self._metrics.completion_time = time.monotonic()
        self._transition_state(HotkeySessionState.COMPLETE)

        if self._on_complete:
            try:
                self._on_complete(self._transcription_result, self._metrics)
            except Exception as e:
                logger.warning(f"Complete callback error: {e}")

        # Auto-cleanup after completion
        self._cleanup()

    def _cleanup(self) -> None:
        """Cleanup resources."""
        self._audio_buffer.clear()

        # Keep transcriber for reuse (don't unload model)
        # But reset any per-session state

        logger.debug(
            "Session cleanup complete",
            extra={
                "session_id": self._session_id,
                "final_state": self._state.name,
            },
        )

    def force_cleanup(self) -> None:
        """Force cleanup of all resources."""
        self._stop_event.set()

        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=1.0)

        self._audio_buffer.clear()

        # Release transcriber
        with self._transcriber_lock:
            if self._transcriber is not None:
                try:
                    self._transcriber.stop()
                except Exception as e:
                    logger.warning(f"Failed to stop transcriber: {e}")
                    self._transcriber = None

        with self._state_lock:
            self._state = HotkeySessionState.IDLE

        logger.debug("Forced cleanup complete", extra={"session_id": self._session_id})

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state to dictionary."""
        return {
            "session_id": self._session_id,
            "state": self._state.name,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "transcription_result": self._transcription_result,
            "confidence": round(self._confidence, 3),
            "metrics": self._metrics.to_dict(),
            "error": self._error,
        }


class HotkeySessionPool:
    """Pool of reusable hotkey sessions for rapid activation.

    Pre-initializes transcriber to eliminate model loading latency.
    """

    def __init__(
        self,
        config: HotkeySessionConfig | None = None,
        pool_size: int = 2,
    ) -> None:
        self.config = config or HotkeySessionConfig()
        self.pool_size = pool_size
        self._sessions: deque[HotkeySession] = deque()
        self._active_session: HotkeySession | None = None
        self._lock = threading.RLock()
        self._transcriber: Any | None = None

    def preload(self) -> bool:
        """Preload transcriber model for instant activation.

        Returns True if model loaded successfully.
        """
        try:
            from app.stt.fast_engine import FastTranscriber

            transcriber = FastTranscriber(
                model_name=self.config.model_name,
                device=self.config.device,
                compute_type=self.config.compute_type,
                beam_size=self.config.beam_size,
                language_mode=self.config.language_mode,
            )

            start_time = time.perf_counter()
            transcriber.load_model()
            load_time_ms = (time.perf_counter() - start_time) * 1000

            self._transcriber = transcriber

            logger.info(
                "Hotkey pool preloaded",
                extra={
                    "model_name": self.config.model_name,
                    "load_time_ms": round(load_time_ms, 2),
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to preload hotkey pool: {e}")
            return False

    def acquire(self) -> HotkeySession:
        """Acquire a ready-to-use session from the pool."""
        with self._lock:
            if self._active_session is not None:
                # Force cleanup existing session
                self._active_session.force_cleanup()

            session = HotkeySession(config=self.config)

            # Share preloaded transcriber if available
            if self._transcriber is not None:
                session._transcriber = self._transcriber

            self._active_session = session
            return session

    def release(self, session: HotkeySession) -> None:
        """Return session to pool after use."""
        with self._lock:
            if self._active_session is session:
                session.force_cleanup()
                self._active_session = None

    @property
    def is_ready(self) -> bool:
        """Check if pool has preloaded model ready."""
        return self._transcriber is not None

    @property
    def active_session(self) -> HotkeySession | None:
        """Get currently active session if any."""
        with self._lock:
            return self._active_session
