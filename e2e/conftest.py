"""E2E test configuration for Transcripta application.

This module provides:
- Automated Electron app launch and management
- Simulated audio input using test files
- Screenshot capture on failure
- Video recording of test sessions
- Performance metrics collection
- Parallel test execution support
- Test isolation and cleanup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

E2E_DIR = Path(__file__).parent
PROJECT_ROOT = E2E_DIR.parent
ELECTRON_DIR = PROJECT_ROOT / "app" / "electron"
TEST_DATA_DIR = E2E_DIR / "test_data"
SCREENSHOTS_DIR = E2E_DIR / "screenshots"
VIDEOS_DIR = E2E_DIR / "videos"
METRICS_DIR = E2E_DIR / "metrics"

# Default timeouts
APP_LAUNCH_TIMEOUT = 30.0  # seconds
TEST_TIMEOUT = 120.0  # seconds
ACTION_TIMEOUT = 10.0  # seconds

# Audio test file parameters
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class E2EConfig:
    """Configuration for E2E tests."""

    headless: bool = False
    record_video: bool = True
    capture_screenshots: bool = True
    collect_metrics: bool = True
    keep_test_data: bool = False
    parallel: bool = False
    electron_dev_mode: bool = True
    mock_audio: bool = True
    mock_stt: bool = True


@dataclass
class PerformanceMetrics:
    """Performance metrics collected during tests."""

    test_name: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    memory_usage_mb: list[float] = field(default_factory=list)
    cpu_usage_percent: list[float] = field(default_factory=list)
    audio_latency_ms: list[float] = field(default_factory=list)
    transcription_latency_ms: list[float] = field(default_factory=list)
    fps: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate test duration."""
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "test_name": self.test_name,
            "duration_seconds": self.duration_seconds,
            "memory_usage_mb": {
                "min": min(self.memory_usage_mb) if self.memory_usage_mb else 0,
                "max": max(self.memory_usage_mb) if self.memory_usage_mb else 0,
                "avg": sum(self.memory_usage_mb) / len(self.memory_usage_mb)
                if self.memory_usage_mb
                else 0,
            },
            "cpu_usage_percent": {
                "min": min(self.cpu_usage_percent) if self.cpu_usage_percent else 0,
                "max": max(self.cpu_usage_percent) if self.cpu_usage_percent else 0,
                "avg": sum(self.cpu_usage_percent) / len(self.cpu_usage_percent)
                if self.cpu_usage_percent
                else 0,
            },
            "audio_latency_ms": {
                "min": min(self.audio_latency_ms) if self.audio_latency_ms else 0,
                "max": max(self.audio_latency_ms) if self.audio_latency_ms else 0,
                "avg": sum(self.audio_latency_ms) / len(self.audio_latency_ms)
                if self.audio_latency_ms
                else 0,
            },
            "transcription_latency_ms": {
                "min": min(self.transcription_latency_ms) if self.transcription_latency_ms else 0,
                "max": max(self.transcription_latency_ms) if self.transcription_latency_ms else 0,
                "avg": sum(self.transcription_latency_ms) / len(self.transcription_latency_ms)
                if self.transcription_latency_ms
                else 0,
            },
            "fps": {
                "min": min(self.fps) if self.fps else 0,
                "max": max(self.fps) if self.fps else 0,
                "avg": sum(self.fps) / len(self.fps) if self.fps else 0,
            },
            "errors": self.errors,
        }


@dataclass
class TestSession:
    """Represents an active E2E test session."""

    session_id: str
    temp_dir: Path
    app_process: subprocess.Popen | None = None
    api_port: int = 8000
    metrics: PerformanceMetrics | None = None
    video_path: Path | None = None
    _cleanup_funcs: list[Callable[[], None]] = field(default_factory=list)

    def add_cleanup(self, func: Callable[[], None]) -> None:
        """Add a cleanup function to run on teardown."""
        self._cleanup_funcs.append(func)

    def cleanup(self) -> None:
        """Run all cleanup functions."""
        for func in reversed(self._cleanup_funcs):
            try:
                func()
            except Exception as e:
                logger.warning(f"Cleanup function failed: {e}")


# =============================================================================
# Audio Test Data Generator
# =============================================================================


class AudioTestDataGenerator:
    """Generates synthetic audio test data for E2E tests."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self.test_files: list[Path] = []

    def generate_sine_wave(
        self,
        duration_seconds: float,
        frequency: float = 440.0,
        amplitude: float = 0.3,
    ) -> np.ndarray:
        """Generate a sine wave audio signal."""
        t = np.linspace(0, duration_seconds, int(self.sample_rate * duration_seconds))
        return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)

    def generate_silence(self, duration_seconds: float) -> np.ndarray:
        """Generate silence."""
        return np.zeros(int(self.sample_rate * duration_seconds), dtype=np.float32)

    def generate_speech_like(
        self,
        duration_seconds: float,
        num_phrases: int = 3,
    ) -> np.ndarray:
        """Generate speech-like audio with pauses."""
        phrase_duration = duration_seconds / num_phrases
        pause_duration = 0.3
        active_duration = phrase_duration - pause_duration

        audio = []
        for i in range(num_phrases):
            # Generate a modulated tone for "speech"
            freq = 150 + i * 50  # Varying frequency
            t = np.linspace(0, active_duration, int(self.sample_rate * active_duration))
            # Add some modulation
            modulation = 1 + 0.3 * np.sin(2 * np.pi * 5 * t)
            phrase = 0.4 * modulation * np.sin(2 * np.pi * freq * t)
            audio.extend(phrase)

            # Add pause
            audio.extend(np.zeros(int(self.sample_rate * pause_duration)))

        return np.array(audio, dtype=np.float32)

    def save_wav(self, audio: np.ndarray, filename: str) -> Path:
        """Save audio data as WAV file."""
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
        filepath = TEST_DATA_DIR / filename

        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        with wave.open(str(filepath), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        self.test_files.append(filepath)
        return filepath

    def create_test_audio_suite(self) -> dict[str, Path]:
        """Create a suite of test audio files."""
        files = {}

        # Short utterance (3 seconds)
        short = self.generate_speech_like(3.0, num_phrases=2)
        files["short_utterance"] = self.save_wav(short, "short_utterance.wav")

        # Medium utterance (10 seconds)
        medium = self.generate_speech_like(10.0, num_phrases=5)
        files["medium_utterance"] = self.save_wav(medium, "medium_utterance.wav")

        # Long session (60 seconds)
        long_audio = self.generate_speech_like(60.0, num_phrases=20)
        files["long_session"] = self.save_wav(long_audio, "long_session.wav")

        # With pauses (chapter detection test)
        with_pauses = []
        for i in range(5):
            with_pauses.extend(self.generate_speech_like(5.0, num_phrases=2))
            with_pauses.extend(self.generate_silence(2.5))  # Long pause for chapter
        files["with_pauses"] = self.save_wav(np.array(with_pauses), "with_pauses.wav")

        # Silence only
        silence = self.generate_silence(5.0)
        files["silence_only"] = self.save_wav(silence, "silence_only.wav")

        # Noise
        noise = np.random.normal(0, 0.1, int(self.sample_rate * 5))
        files["noise_only"] = self.save_wav(noise.astype(np.float32), "noise_only.wav")

        return files

    def cleanup(self) -> None:
        """Remove all generated test files."""
        for filepath in self.test_files:
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove test file {filepath}: {e}")


# =============================================================================
# Electron App Controller
# =============================================================================


class ElectronAppController:
    """Controls the Electron application for E2E testing."""

    def __init__(
        self,
        config: E2EConfig,
        temp_dir: Path,
        api_port: int = 8000,
    ) -> None:
        self.config = config
        self.temp_dir = temp_dir
        self.api_port = api_port
        self.process: subprocess.Popen | None = None
        self._log_file: Path | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def _find_electron_executable(self) -> Path:
        """Find the Electron executable path."""
        system = platform.system().lower()

        if system == "windows":
            # Look for electron in node_modules
            electron_paths = [
                ELECTRON_DIR / "node_modules" / ".bin" / "electron.cmd",
                ELECTRON_DIR / "node_modules" / ".bin" / "electron.exe",
            ]
        elif system == "darwin":
            electron_paths = [
                ELECTRON_DIR / "node_modules" / ".bin" / "electron",
                "/Applications/Transcripta.app/Contents/MacOS/Transcripta",
            ]
        else:  # Linux
            electron_paths = [
                ELECTRON_DIR / "node_modules" / ".bin" / "electron",
                "/usr/bin/transcripta",
            ]

        for path in electron_paths:
            if path.exists():
                return path

        # Fallback to electron in PATH
        return Path("electron")

    def launch(self) -> bool:
        """Launch the Electron application."""
        logger.info("Launching Electron application...")

        electron_exe = self._find_electron_executable()
        app_path = ELECTRON_DIR

        # Setup environment
        env = os.environ.copy()
        env["TRANSCRIPTA_E2E_TEST"] = "1"
        env["TRANSCRIPTA_API_PORT"] = str(self.api_port)
        env["TRANSCRIPTA_MOCK_AUDIO"] = "1" if self.config.mock_audio else "0"
        env["TRANSCRIPTA_MOCK_STT"] = "1" if self.config.mock_stt else "0"
        env["TRANSCRIPTA_HEADLESS"] = "1" if self.config.headless else "0"

        # Setup log file
        self._log_file = self.temp_dir / "electron.log"

        # Build command
        cmd = [
            str(electron_exe),
            str(app_path),
            "--remote-debugging-port=9223",
        ]

        if self.config.headless:
            cmd.extend(["--headless", "--disable-gpu"])

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(app_path),
            )

            # Start log readers
            self._start_log_readers()

            # Wait for app to be ready
            if not self._wait_for_ready():
                logger.error("Application failed to start within timeout")
                self.terminate()
                return False

            logger.info(f"Electron application launched (PID: {self.process.pid})")
            return True

        except Exception as e:
            logger.exception("Failed to launch Electron application")
            return False

    def _start_log_readers(self) -> None:
        """Start threads to read stdout/stderr."""

        def read_stream(stream, name: str):
            with open(self._log_file, "a") as log:
                for line in stream:
                    log.write(f"[{name}] {line}")
                    log.flush()

        if self.process:
            self._stdout_thread = threading.Thread(
                target=read_stream,
                args=(self.process.stdout, "OUT"),
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=read_stream,
                args=(self.process.stderr, "ERR"),
                daemon=True,
            )
            self._stdout_thread.start()
            self._stderr_thread.start()

    def _wait_for_ready(self, timeout: float = APP_LAUNCH_TIMEOUT) -> bool:
        """Wait for the application to be ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.process and self.process.poll() is not None:
                # Process exited
                return False

            # Check if API is responding
            try:
                import urllib.request

                req = urllib.request.Request(
                    f"http://localhost:{self.api_port}/health",
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=1.0) as response:
                    if response.status == 200:
                        return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def terminate(self) -> None:
        """Terminate the Electron application."""
        if self.process is None:
            return

        logger.info("Terminating Electron application...")

        try:
            # Try graceful termination first
            if platform.system() == "Windows":
                self.process.terminate()
            else:
                self.process.send_signal(subprocess.signal.SIGTERM)

            # Wait for process to exit
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                # Force kill
                self.process.kill()
                self.process.wait()

        except Exception as e:
            logger.warning(f"Error terminating process: {e}")

        finally:
            self.process = None

    def is_running(self) -> bool:
        """Check if the application is still running."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_logs(self) -> str:
        """Get application logs."""
        if self._log_file and self._log_file.exists():
            return self._log_file.read_text()
        return ""


# =============================================================================
# Mock STT Engine for Testing
# =============================================================================


class MockSTTEngine:
    """Mock STT engine for reliable E2E testing."""

    def __init__(self) -> None:
        self.transcriptions: list[dict[str, Any]] = []
        self.partial_callbacks: list[Callable[[str], None]] = []
        self.segment_callbacks: list[Callable[[dict], None]] = []
        self._recording = False

    def start_recording(self) -> None:
        """Start mock recording."""
        self._recording = True

    def stop_recording(self) -> dict[str, Any]:
        """Stop mock recording and return result."""
        self._recording = False
        return {
            "text": "This is a mock transcription for testing purposes.",
            "confidence": 0.95,
            "language": "en",
        }

    def inject_mock_transcription(self, text: str, confidence: float = 0.95) -> None:
        """Inject a mock transcription result."""
        result = {
            "text": text,
            "confidence": confidence,
            "language": "en",
            "timestamp": time.time(),
        }
        self.transcriptions.append(result)

        for callback in self.segment_callbacks:
            callback(result)

    def add_partial_callback(self, callback: Callable[[str], None]) -> None:
        """Add callback for partial results."""
        self.partial_callbacks.append(callback)

    def add_segment_callback(self, callback: Callable[[dict], None]) -> None:
        """Add callback for segments."""
        self.segment_callbacks.append(callback)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def e2e_config() -> E2EConfig:
    """Provide E2E test configuration."""
    return E2EConfig(
        headless=os.environ.get("E2E_HEADLESS", "false").lower() == "true",
        record_video=os.environ.get("E2E_RECORD_VIDEO", "true").lower() == "true",
        capture_screenshots=os.environ.get("E2E_SCREENSHOTS", "true").lower() == "true",
        collect_metrics=os.environ.get("E2E_METRICS", "true").lower() == "true",
        keep_test_data=os.environ.get("E2E_KEEP_DATA", "false").lower() == "true",
        parallel=os.environ.get("E2E_PARALLEL", "false").lower() == "true",
    )


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide test data directory."""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def audio_generator() -> Generator[AudioTestDataGenerator, None, None]:
    """Provide audio test data generator."""
    generator = AudioTestDataGenerator()
    yield generator
    generator.cleanup()


@pytest.fixture(scope="session")
def test_audio_files(audio_generator: AudioTestDataGenerator) -> dict[str, Path]:
    """Provide suite of test audio files."""
    return audio_generator.create_test_audio_suite()


@pytest.fixture
def temp_test_dir(request: pytest.FixtureRequest) -> Generator[Path, None, None]:
    """Provide temporary directory for test isolation."""
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    temp_dir = tempfile.mkdtemp(prefix=f"e2e_{test_name}_")
    path = Path(temp_dir)

    yield path

    # Cleanup
    if not os.environ.get("E2E_KEEP_DATA", "false").lower() == "true":
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {path}: {e}")


@pytest.fixture
async def test_session(
    e2e_config: E2EConfig,
    temp_test_dir: Path,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[TestSession, None]:
    """Provide a complete E2E test session."""
    session_id = f"{request.node.name}_{int(time.time())}"

    # Find available port
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    session = TestSession(
        session_id=session_id,
        temp_dir=temp_test_dir,
        api_port=port,
        metrics=PerformanceMetrics(test_name=request.node.name)
        if e2e_config.collect_metrics
        else None,
    )

    # Setup video recording if enabled
    if e2e_config.record_video:
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        session.video_path = VIDEOS_DIR / f"{session_id}.webm"

    try:
        yield session
    finally:
        # Run cleanup
        session.cleanup()

        # Save metrics
        if session.metrics and e2e_config.collect_metrics:
            session.metrics.end_time = time.time()
            METRICS_DIR.mkdir(parents=True, exist_ok=True)
            metrics_file = METRICS_DIR / f"{session_id}_metrics.json"
            with open(metrics_file, "w") as f:
                json.dump(session.metrics.to_dict(), f, indent=2)


@pytest.fixture
async def electron_app(
    e2e_config: E2EConfig,
    test_session: TestSession,
) -> AsyncGenerator[ElectronAppController, None]:
    """Provide running Electron application."""
    controller = ElectronAppController(
        config=e2e_config,
        temp_dir=test_session.temp_dir,
        api_port=test_session.api_port,
    )

    if not controller.launch():
        pytest.fail("Failed to launch Electron application")

    test_session.app_process = controller.process

    try:
        yield controller
    finally:
        controller.terminate()


@pytest.fixture
def mock_stt_engine() -> MockSTTEngine:
    """Provide mock STT engine."""
    return MockSTTEngine()


@pytest.fixture
def screenshot_on_failure(request: pytest.FixtureRequest, e2e_config: E2EConfig):
    """Capture screenshot on test failure."""
    yield

    if not e2e_config.capture_screenshots:
        return

    # Check if test failed
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        screenshot_path = SCREENSHOTS_DIR / f"{request.node.name}_failure.png"

        # Try to capture screenshot (implementation depends on testing framework)
        # This is a placeholder for actual screenshot capture logic
        logger.info(f"Test failed, would capture screenshot to {screenshot_path}")


# =============================================================================
# Async Fixtures for API Testing
# =============================================================================


@pytest_asyncio.fixture
async def api_client(test_session: TestSession):
    """Provide HTTP client for API testing."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        yield APIClient(session, f"http://localhost:{test_session.api_port}")


class APIClient:
    """Simple API client for E2E tests."""

    def __init__(self, session, base_url: str):
        self.session = session
        self.base_url = base_url

    async def get(self, path: str, **kwargs) -> dict[str, Any]:
        """Make GET request."""
        async with self.session.get(f"{self.base_url}{path}", **kwargs) as response:
            return await response.json()

    async def post(self, path: str, **kwargs) -> dict[str, Any]:
        """Make POST request."""
        async with self.session.post(f"{self.base_url}{path}", **kwargs) as response:
            return await response.json()

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return await self.get("/api/health")

    async def start_hotkey_session(self, **params) -> dict[str, Any]:
        """Start hotkey recording session."""
        payload = {
            "capture_source": "microphone",
            "device_id": params.pop("device_id", None),
            "model_name": params.pop("model_name", "whisper-turbo"),
            "language_mode": params.pop("language_mode", "auto"),
            "execution_mode": params.pop("execution_mode", "auto"),
        }
        payload.update(params)
        return await self.post("/api/transcription/hotkey/start", json=payload)

    async def stop_hotkey_session(self, **params) -> dict[str, Any]:
        """Stop hotkey recording session."""
        payload = {"mode": params.pop("mode", "finish_and_paste")}
        payload.update(params)
        return await self.post("/api/transcription/hotkey/stop", json=payload)

    async def get_hotkey_status(self) -> dict[str, Any]:
        """Get hotkey status."""
        return await self.get("/api/transcription/hotkey/status")

    async def start_system_session(self, **params) -> dict[str, Any]:
        """Start system recording session."""
        payload = {
            "title": params.pop("title", "System Audio Session"),
            "output_root": params.pop("output_root", "sessions"),
            "model_name": params.pop("model_name", "whisper-turbo"),
            "language_mode": params.pop("language_mode", "auto"),
            "device_id": params.pop("device_id", "default"),
            "live_mode": params.pop("live_mode", "balanced"),
            "execution_mode": params.pop("execution_mode", "auto"),
            "capture_source": "system",
            "vad_threshold": params.pop("vad_threshold", 0.6),
            "vad_min_silence_ms": params.pop("vad_min_silence_ms", 450),
            "vad_speech_pad_ms": params.pop("vad_speech_pad_ms", 200),
        }
        payload.update(params)
        return await self.post("/api/session/start", json=payload)

    async def stop_system_session(self, **params) -> dict[str, Any]:
        """Stop system recording session."""
        return await self.post("/api/session/stop", json=params or None)

    async def get_mode_status(self) -> dict[str, Any]:
        """Get current session and hotkey status."""
        return {
            "session": await self.get("/api/session"),
            "hotkey": await self.get_hotkey_status(),
        }

    async def switch_mode(self, mode: str) -> dict[str, Any]:
        """Compatibility shim for selecting active capture source."""
        return {"mode": mode}


# =============================================================================
# Helper Functions
# =============================================================================


def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = ACTION_TIMEOUT,
    interval: float = 0.1,
) -> bool:
    """Wait for a condition to be true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


async def async_wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = ACTION_TIMEOUT,
    interval: float = 0.1,
) -> bool:
    """Async wait for a condition to be true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


def simulate_hotkey_press(key_combination: str = "ctrl+shift+r") -> None:
    """Simulate hotkey press (platform-specific)."""
    system = platform.system().lower()

    try:
        if system == "windows":
            import ctypes
            from ctypes import wintypes

            # Parse key combination
            keys = key_combination.split("+")
            modifier = keys[0].upper()
            main_key = keys[-1].upper()

            # Key codes
            VK_CONTROL = 0x11
            VK_SHIFT = 0x10
            VK_MENU = 0x12  # Alt

            key_map = {
                "CTRL": VK_CONTROL,
                "CONTROL": VK_CONTROL,
                "SHIFT": VK_SHIFT,
                "ALT": VK_MENU,
                "R": 0x52,
                "SPACE": 0x20,
            }

            user32 = ctypes.windll.user32

            # Press modifier
            if modifier in key_map:
                user32.keybd_event(key_map[modifier], 0, 0, 0)

            # Press main key
            if main_key in key_map:
                user32.keybd_event(key_map[main_key], 0, 0, 0)
                user32.keybd_event(key_map[main_key], 0, 2, 0)

            # Release modifier
            if modifier in key_map:
                user32.keybd_event(key_map[modifier], 0, 2, 0)

        elif system == "darwin":
            import subprocess

            script = f"""
                tell application "System Events"
                    keystroke "r" using {{control down, shift down}}
                end tell
            """
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)

        else:  # Linux
            import subprocess

            subprocess.run(
                ["xdotool", "key", key_combination.replace("+", "+")],
                capture_output=True,
                timeout=5,
            )

    except Exception as e:
        logger.warning(f"Failed to simulate hotkey: {e}")


@pytest.fixture(autouse=True)
def isolate_tests(temp_test_dir: Path) -> Generator[None, None, None]:
    """Ensure test isolation by using temporary directories."""
    # Set environment variables for isolation
    old_home = os.environ.get("HOME")
    old_userprofile = os.environ.get("USERPROFILE")

    # Override home directory for test isolation
    os.environ["HOME"] = str(temp_test_dir)
    os.environ["USERPROFILE"] = str(temp_test_dir)
    os.environ["TRANSCRIPTA_DATA_DIR"] = str(temp_test_dir / ".transcripta")

    yield

    # Restore environment
    if old_home:
        os.environ["HOME"] = old_home
    if old_userprofile:
        os.environ["USERPROFILE"] = old_userprofile

    if "TRANSCRIPTA_DATA_DIR" in os.environ:
        del os.environ["TRANSCRIPTA_DATA_DIR"]


# =============================================================================
# pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "hotkey: mark test as hotkey mode test")
    config.addinivalue_line("markers", "system: mark test as system mode test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "flaky: mark test as potentially flaky")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add e2e marker to all tests in e2e directory
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


def pytest_html_report_title(report):
    """Set HTML report title."""
    report.title = "Transcripta E2E Test Report"
