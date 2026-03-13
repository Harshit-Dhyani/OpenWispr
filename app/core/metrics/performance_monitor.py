"""Real-time performance monitoring system.

Provides live performance dashboards, resource monitoring, latency profiling,
and WebSocket streaming for real-time UI updates.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .metrics import (
    Alert,
    AlertManager,
    AlertSeverity,
    LatencyBreakdown,
    MetricsCollector,
    get_alert_manager,
    get_collector,
    get_reporter,
)

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """System resource snapshot."""

    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    gpu_percent: float | None = None
    gpu_memory_mb: float | None = None
    thread_count: int = 0
    open_files: int = 0


@dataclass
class PerformanceSnapshot:
    """Complete performance snapshot for UI."""

    timestamp: float
    session_id: str | None

    # Latency metrics
    first_word_latency_ms: float
    avg_inter_word_latency_ms: float
    end_to_end_latency_ms: float

    # Throughput
    real_time_factor: float
    words_per_minute: float

    # Resources
    cpu_percent: float
    memory_mb: float
    gpu_percent: float | None
    gpu_memory_mb: float | None

    # Audio
    buffer_health_percent: float
    audio_drop_rate: float
    vad_accuracy: float

    # Model
    cache_hit_rate: float
    queue_depth: int
    inference_count: int

    # Session
    session_duration_seconds: float
    segment_count: int
    total_words: int


class LatencyProfiler:
    """Detailed latency profiling with phase breakdown."""

    def __init__(self, max_samples: int = 1000):
        self._samples: deque = deque(maxlen=max_samples)
        self._active_profiles: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._phase_times: dict[str, deque] = {
            "audio_capture": deque(maxlen=max_samples),
            "preprocessing": deque(maxlen=max_samples),
            "vad_detection": deque(maxlen=max_samples),
            "model_inference": deque(maxlen=max_samples),
            "postprocessing": deque(maxlen=max_samples),
            "websocket_emit": deque(maxlen=max_samples),
        }

    def start_profile(self, profile_id: str) -> None:
        """Start a latency profile."""
        with self._lock:
            self._active_profiles[profile_id] = {
                "start_time": time.perf_counter(),
                "phases": {},
            }

    def record_phase(self, profile_id: str, phase: str) -> None:
        """Record phase transition."""
        with self._lock:
            if profile_id not in self._active_profiles:
                return

            now = time.perf_counter()
            profile = self._active_profiles[profile_id]

            # Calculate time since start or last phase
            if not profile["phases"]:
                elapsed_ms = (now - profile["start_time"]) * 1000
            else:
                last_phase_time = max(profile["phases"].values())
                elapsed_ms = (now - last_phase_time / 1000) * 1000

            profile["phases"][phase] = now * 1000

            # Record in phase times
            if phase in self._phase_times:
                self._phase_times[phase].append(elapsed_ms)

    def end_profile(self, profile_id: str) -> LatencyBreakdown | None:
        """End profiling and return breakdown."""
        with self._lock:
            if profile_id not in self._active_profiles:
                return None

            profile = self._active_profiles.pop(profile_id)
            end_time = time.perf_counter()
            phases = profile["phases"]

            breakdown = LatencyBreakdown(
                audio_capture_ms=phases.get("audio_capture", 0),
                preprocessing_ms=phases.get("preprocessing", 0),
                vad_detection_ms=phases.get("vad_detection", 0),
                model_inference_ms=phases.get("model_inference", 0),
                postprocessing_ms=phases.get("postprocessing", 0),
                websocket_emit_ms=phases.get("websocket_emit", 0),
                total_ms=(end_time - profile["start_time"]) * 1000,
            )

            self._samples.append(breakdown)
            return breakdown

    def get_average_breakdown(self) -> LatencyBreakdown:
        """Get average latency breakdown."""
        with self._lock:
            if not self._samples:
                return LatencyBreakdown()

            n = len(self._samples)
            return LatencyBreakdown(
                audio_capture_ms=sum(s.audio_capture_ms for s in self._samples) / n,
                preprocessing_ms=sum(s.preprocessing_ms for s in self._samples) / n,
                vad_detection_ms=sum(s.vad_detection_ms for s in self._samples) / n,
                model_inference_ms=sum(s.model_inference_ms for s in self._samples) / n,
                postprocessing_ms=sum(s.postprocessing_ms for s in self._samples) / n,
                websocket_emit_ms=sum(s.websocket_emit_ms for s in self._samples) / n,
                total_ms=sum(s.total_ms for s in self._samples) / n,
            )

    def get_phase_stats(self, phase: str) -> dict[str, float]:
        """Get statistics for a specific phase."""
        with self._lock:
            times = list(self._phase_times.get(phase, []))

            if not times:
                return {"count": 0, "mean": 0, "p95": 0, "p99": 0}

            times_sorted = sorted(times)
            n = len(times_sorted)

            return {
                "count": n,
                "mean": sum(times) / n,
                "min": times_sorted[0],
                "max": times_sorted[-1],
                "p95": times_sorted[int(n * 0.95)],
                "p99": times_sorted[int(n * 0.99)],
            }

    def clear(self) -> None:
        """Clear all samples."""
        with self._lock:
            self._samples.clear()
            self._active_profiles.clear()
            for times in self._phase_times.values():
                times.clear()


class ResourceMonitor:
    """Monitor system resources with minimal overhead."""

    def __init__(self, history_size: int = 3600):
        self._history: deque = deque(maxlen=history_size)
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._interval = 1.0

        # Try to import psutil for better resource monitoring
        self._psutil = None
        self._pynvml = None
        self._process = None

        try:
            import psutil

            self._psutil = psutil
            self._process = psutil.Process()
        except ImportError:
            logger.debug("psutil not available, using basic resource monitoring")

        try:
            import pynvml

            self._pynvml = pynvml
            pynvml.nvmlInit()
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except (ImportError, Exception):
            logger.debug("GPU monitoring not available")

    def start(self, interval: float = 1.0) -> None:
        """Start resource monitoring."""
        if self._running:
            return

        self._interval = interval
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Resource monitoring started")

    def stop(self) -> None:
        """Stop resource monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Resource monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                snapshot = self._collect_snapshot()
                with self._lock:
                    self._history.append(snapshot)

                # Update metrics collector
                collector = get_collector()
                collector.set("resource.cpu_percent", snapshot.cpu_percent)
                collector.set("resource.memory_mb", snapshot.memory_mb)

                if snapshot.gpu_percent is not None:
                    collector.set("resource.gpu_percent", snapshot.gpu_percent)
                if snapshot.gpu_memory_mb is not None:
                    collector.set("resource.gpu_memory_mb", snapshot.gpu_memory_mb)

            except Exception as e:
                logger.warning(f"Resource collection error: {e}")

            time.sleep(self._interval)

    def _collect_snapshot(self) -> ResourceSnapshot:
        """Collect resource snapshot."""
        timestamp = time.time()

        if self._psutil and self._process:
            cpu_percent = self._process.cpu_percent()
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)

            system_memory = self._psutil.virtual_memory()
            memory_percent = system_memory.percent

            io_counters = self._process.io_counters()
            disk_io_read_mb = io_counters.read_bytes / (1024 * 1024)
            disk_io_write_mb = io_counters.write_bytes / (1024 * 1024)

            thread_count = self._process.num_threads()

            try:
                open_files = len(self._process.open_files())
            except Exception as e:
                logger.warning("Failed to get open files count: %s", e)
                open_files = 0
        else:
            # Fallback to basic monitoring

            cpu_percent = 0.0
            memory_mb = 0.0
            memory_percent = 0.0
            disk_io_read_mb = 0.0
            disk_io_write_mb = 0.0
            thread_count = threading.active_count()
            open_files = 0

        # GPU stats
        gpu_percent = None
        gpu_memory_mb = None

        if self._pynvml and hasattr(self, "_gpu_handle"):
            try:
                util = self._pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                gpu_percent = util.gpu

                mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                gpu_memory_mb = mem_info.used / (1024 * 1024)
            except Exception as e:
                logger.warning("Failed to get GPU stats: %s", e)

        return ResourceSnapshot(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            gpu_percent=gpu_percent,
            gpu_memory_mb=gpu_memory_mb,
            thread_count=thread_count,
            open_files=open_files,
        )

    def get_current(self) -> ResourceSnapshot:
        """Get current resource snapshot."""
        return self._collect_snapshot()

    def get_history(self, seconds: int = 300) -> list[ResourceSnapshot]:
        """Get resource history."""
        cutoff = time.time() - seconds
        with self._lock:
            return [s for s in self._history if s.timestamp >= cutoff]

    def get_average(self, seconds: int = 300) -> ResourceSnapshot | None:
        """Get average resource usage."""
        history = self.get_history(seconds)

        if not history:
            return None

        n = len(history)

        def avg(values: list[float | None]) -> float | None:
            valid = [v for v in values if v is not None]
            return sum(valid) / len(valid) if valid else None

        return ResourceSnapshot(
            timestamp=history[-1].timestamp,
            cpu_percent=sum(s.cpu_percent for s in history) / n,
            memory_mb=sum(s.memory_mb for s in history) / n,
            memory_percent=sum(s.memory_percent for s in history) / n,
            disk_io_read_mb=sum(s.disk_io_read_mb for s in history) / n,
            disk_io_write_mb=sum(s.disk_io_write_mb for s in history) / n,
            gpu_percent=avg([s.gpu_percent for s in history]),
            gpu_memory_mb=avg([s.gpu_memory_mb for s in history]),
            thread_count=int(sum(s.thread_count for s in history) / n),
            open_files=int(sum(s.open_files for s in history) / n),
        )


class PerformanceDashboard:
    """Real-time performance dashboard with WebSocket streaming."""

    def __init__(self):
        self._collector = get_collector()
        self._alert_manager = get_alert_manager()
        self._resource_monitor = ResourceMonitor()
        self._latency_profiler = LatencyProfiler()
        self._reporter = get_reporter()

        self._websocket_clients: set[Any] = set()
        self._lock = threading.RLock()
        self._running = False
        self._streaming_thread: threading.Thread | None = None
        self._stream_interval = 1.0

        # Summary report scheduling
        self._last_minute_report = 0.0
        self._last_5min_report = 0.0
        self._last_hour_report = 0.0
        self._report_callbacks: list[Callable[[str, dict], None]] = []

        # Session tracking
        self._session_start_time: float | None = None
        self._session_id: str | None = None

    def start(
        self,
        stream_interval: float = 1.0,
        monitor_resources: bool = True,
    ) -> None:
        """Start the performance dashboard."""
        self._stream_interval = stream_interval
        self._running = True

        if monitor_resources:
            self._resource_monitor.start()

        self._streaming_thread = threading.Thread(target=self._streaming_loop, daemon=True)
        self._streaming_thread.start()

        logger.info("Performance dashboard started")

    def stop(self) -> None:
        """Stop the performance dashboard."""
        self._running = False
        self._resource_monitor.stop()

        if self._streaming_thread:
            self._streaming_thread.join(timeout=2.0)

        logger.info("Performance dashboard stopped")

    def start_session(self, session_id: str) -> None:
        """Start tracking a session."""
        self._session_id = session_id
        self._session_start_time = time.time()
        self._collector.inc("session.active")
        logger.info(f"Started tracking session: {session_id}")

    def end_session(self) -> None:
        """End current session."""
        if self._session_start_time:
            duration = time.time() - self._session_start_time
            self._collector.record_time("session.duration", duration * 1000)

        self._session_id = None
        self._session_start_time = None

    def _streaming_loop(self) -> None:
        """Main streaming loop."""
        while self._running:
            try:
                snapshot = self._create_snapshot()
                self._broadcast_snapshot(snapshot)
                self._check_scheduled_reports()

            except Exception as e:
                logger.warning(f"Streaming error: {e}")

            time.sleep(self._stream_interval)

    def _create_snapshot(self) -> PerformanceSnapshot:
        """Create performance snapshot."""
        snapshot = self._collector.snapshot_all()
        resources = self._resource_monitor.get_current()

        session_duration = 0.0
        if self._session_start_time:
            session_duration = time.time() - self._session_start_time

        latency_hist = snapshot.get("latency.end_to_end", {}).get("histogram", {}) or {}

        return PerformanceSnapshot(
            timestamp=time.time(),
            session_id=self._session_id,
            first_word_latency_ms=(
                snapshot.get("latency.first_word", {}).get("histogram") or {}
            ).get("mean", 0),
            avg_inter_word_latency_ms=(
                snapshot.get("latency.inter_word", {}).get("histogram") or {}
            ).get("mean", 0),
            end_to_end_latency_ms=latency_hist.get("mean", 0),
            real_time_factor=snapshot.get("throughput.rtf", {}).get("value", 0),
            words_per_minute=snapshot.get("throughput.wpm", {}).get("value", 0),
            cpu_percent=resources.cpu_percent if resources else 0,
            memory_mb=resources.memory_mb if resources else 0,
            gpu_percent=resources.gpu_percent if resources else None,
            gpu_memory_mb=resources.gpu_memory_mb if resources else None,
            buffer_health_percent=snapshot.get("audio.buffer_health", {}).get("value", 100),
            audio_drop_rate=snapshot.get("audio.drop_rate", {}).get("value", 0),
            vad_accuracy=snapshot.get("audio.vad_accuracy", {}).get("value", 0),
            cache_hit_rate=snapshot.get("model.cache_hit_rate", {}).get("value", 0),
            queue_depth=int(snapshot.get("model.queue_depth", {}).get("value", 0)),
            inference_count=int(snapshot.get("model.inference_count", {}).get("value", 0)),
            session_duration_seconds=session_duration,
            segment_count=int(snapshot.get("session.segments_total", {}).get("value", 0)),
            total_words=int(snapshot.get("throughput.words_total", {}).get("value", 0)),
        )

    def _broadcast_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Broadcast snapshot to all WebSocket clients."""
        data = {
            "type": "performance_snapshot",
            "data": asdict(snapshot),
        }

        with self._lock:
            clients = list(self._websocket_clients)

        # Store for later retrieval
        self._latest_snapshot = snapshot

    def _check_scheduled_reports(self) -> None:
        """Check and generate scheduled reports."""
        now = time.time()

        # 1 minute report
        if now - self._last_minute_report >= 60:
            self._generate_report("1m", 60)
            self._last_minute_report = now

        # 5 minute report
        if now - self._last_5min_report >= 300:
            self._generate_report("5m", 300)
            self._last_5min_report = now

        # 1 hour report
        if now - self._last_hour_report >= 3600:
            self._generate_report("1h", 3600)
            self._last_hour_report = now

    def _generate_report(self, period: str, seconds: int) -> None:
        """Generate and dispatch summary report."""
        report = self._reporter.generate_summary(seconds)
        report["period"] = period

        for callback in self._report_callbacks:
            try:
                callback(period, report)
            except Exception as e:
                logger.warning(f"Report callback error: {e}")

    def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        return self._create_snapshot()

    def get_latency_breakdown(self) -> LatencyBreakdown:
        """Get average latency breakdown."""
        return self._latency_profiler.get_average_breakdown()

    def get_resource_history(self, seconds: int = 300) -> list[ResourceSnapshot]:
        """Get resource history."""
        return self._resource_monitor.get_history(seconds)

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        limit: int = 50,
    ) -> list[Alert]:
        """Get recent alerts."""
        return self._alert_manager.get_alerts(severity=severity)[:limit]

    def add_report_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Add callback for periodic reports."""
        self._report_callbacks.append(callback)

    def remove_report_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Remove report callback."""
        if callback in self._report_callbacks:
            self._report_callbacks.remove(callback)

    # Convenience methods for recording metrics

    def record_latency(self, latency_type: str, duration_ms: float) -> None:
        """Record latency metric."""
        metric_map = {
            "first_word": "latency.first_word",
            "inter_word": "latency.inter_word",
            "end_to_end": "latency.end_to_end",
            "inference": "latency.inference",
        }

        metric_name = metric_map.get(latency_type)
        if metric_name:
            self._collector.record_time(metric_name, duration_ms)

    def record_throughput(self, words: int, rtf: float, wpm: float) -> None:
        """Record throughput metrics."""
        self._collector.inc("throughput.words_total", words)
        self._collector.set("throughput.rtf", rtf)
        self._collector.set("throughput.wpm", wpm)

    def record_audio_metrics(
        self,
        samples: int,
        drop_rate: float,
        buffer_health: float,
        vad_detections: int,
        vad_accuracy: float,
    ) -> None:
        """Record audio metrics."""
        self._collector.inc("audio.samples_processed", samples)
        self._collector.set("audio.drop_rate", drop_rate)
        self._collector.set("audio.buffer_health", buffer_health)
        self._collector.inc("audio.vad_detections", vad_detections)
        self._collector.set("audio.vad_accuracy", vad_accuracy)

    def record_model_metrics(
        self,
        inference_time_ms: float,
        cache_hit_rate: float,
        queue_depth: int,
    ) -> None:
        """Record model metrics."""
        self._collector.inc("model.inference_count")
        self._collector.record_time("latency.inference", inference_time_ms)
        self._collector.set("model.cache_hit_rate", cache_hit_rate)
        self._collector.set("model.queue_depth", queue_depth)

    def record_segment(self, word_count: int) -> None:
        """Record segment completion."""
        self._collector.inc("session.segments_total")
        self._collector.inc("throughput.words_total", word_count)

    def start_latency_profile(self, profile_id: str) -> None:
        """Start latency profiling."""
        self._latency_profiler.start_profile(profile_id)

    def record_latency_phase(self, profile_id: str, phase: str) -> None:
        """Record latency phase."""
        self._latency_profiler.record_phase(profile_id, phase)

    def end_latency_profile(self, profile_id: str) -> LatencyBreakdown | None:
        """End latency profiling."""
        return self._latency_profiler.end_profile(profile_id)


class PerformanceMonitor:
    """Main performance monitoring coordinator."""

    _instance: PerformanceMonitor | None = None
    _lock = threading.Lock()

    def __new__(cls) -> PerformanceMonitor:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._dashboard = PerformanceDashboard()
        self._collector = get_collector()
        self._alert_manager = get_alert_manager()
        self._resource_monitor = ResourceMonitor()
        self._initialized = True
        self._running = False

        # Setup default thresholds
        self._setup_default_thresholds()

    def _setup_default_thresholds(self) -> None:
        """Setup default alert thresholds."""
        self._alert_manager.set_threshold(
            "resource.cpu_percent",
            max_value=80.0,
            severity=AlertSeverity.WARNING,
        )
        self._alert_manager.set_threshold(
            "resource.memory_mb",
            max_value=4096.0,
            severity=AlertSeverity.WARNING,
        )
        self._alert_manager.set_threshold(
            "latency.end_to_end",
            max_value=500.0,
            severity=AlertSeverity.WARNING,
        )
        self._alert_manager.set_threshold(
            "audio.drop_rate",
            max_value=0.05,
            severity=AlertSeverity.ERROR,
        )
        self._alert_manager.set_threshold(
            "audio.buffer_health",
            min_value=20.0,
            severity=AlertSeverity.ERROR,
        )

    def start(self, stream_interval: float = 1.0) -> None:
        """Start performance monitoring."""
        if self._running:
            return

        self._running = True
        self._dashboard.start(stream_interval=stream_interval)

        # Subscribe to metric updates for alerting
        self._collector.subscribe(self._on_metric_update)

        logger.info("Performance monitor started")

    def stop(self) -> None:
        """Stop performance monitoring."""
        if not self._running:
            return

        self._running = False
        self._dashboard.stop()
        self._collector.unsubscribe(self._on_metric_update)

        logger.info("Performance monitor stopped")

    def _on_metric_update(self, name: str, data: dict[str, Any]) -> None:
        """Handle metric update for alerting."""
        if "value" in data:
            self._alert_manager.check_metric(name, data["value"])

    @property
    def dashboard(self) -> PerformanceDashboard:
        """Get performance dashboard."""
        return self._dashboard

    @property
    def collector(self) -> MetricsCollector:
        """Get metrics collector."""
        return self._collector

    @property
    def alert_manager(self) -> AlertManager:
        """Get alert manager."""
        return self._alert_manager

    def get_status(self) -> dict[str, Any]:
        """Get monitoring status."""
        return {
            "running": self._running,
            "session_active": self._dashboard._session_id is not None,
            "session_id": self._dashboard._session_id,
            "alerts_active": len(self._alert_manager.get_alerts(acknowledged=False)),
            "collector_metrics": len(self._collector.snapshot_all()),
        }

    def export_metrics(self, filepath: str | Path, format: str = "json") -> None:
        """Export metrics to file."""
        filepath = Path(filepath)

        if format == "json":
            self._collector.export_json(filepath)
        elif format == "csv":
            self._collector.export_csv(filepath)
        else:
            raise ValueError(f"Unknown format: {format}")


# Global instance
_monitor: PerformanceMonitor | None = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


def start_monitoring(stream_interval: float = 1.0) -> PerformanceMonitor:
    """Start global performance monitoring."""
    monitor = get_monitor()
    monitor.start(stream_interval)
    return monitor


def stop_monitoring() -> None:
    """Stop global performance monitoring."""
    global _monitor
    if _monitor:
        _monitor.stop()
        _monitor = None
