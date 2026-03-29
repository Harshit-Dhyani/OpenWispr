"""Metrics collection and reporting system.

Provides comprehensive metrics tracking for latency, throughput, resources,
audio quality, model performance, and session statistics with minimal overhead.
"""

from __future__ import annotations

import csv
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = auto()
    GAUGE = auto()
    HISTOGRAM = auto()
    TIMER = auto()
    SET = auto()


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert for threshold violations."""

    id: str
    severity: AlertSeverity
    metric_name: str
    message: str
    value: float
    threshold: float
    timestamp: float
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


@dataclass
class LatencyBreakdown:
    """Detailed latency breakdown by phase."""

    audio_capture_ms: float = 0.0
    preprocessing_ms: float = 0.0
    vad_detection_ms: float = 0.0
    model_inference_ms: float = 0.0
    postprocessing_ms: float = 0.0
    websocket_emit_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class MetricValue:
    """Single metric value with timestamp."""

    value: int | float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class HistogramSnapshot:
    """Snapshot of histogram data."""

    count: int
    sum: float
    min: float
    max: float
    mean: float
    p50: float
    p95: float
    p99: float
    std_dev: float


class RingBuffer:
    """Thread-safe ring buffer for metric storage."""

    def __init__(self, capacity: int = 10000):
        self._capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._total_added = 0

    def append(self, value: MetricValue) -> None:
        """Add value to buffer (thread-safe)."""
        with self._lock:
            self._buffer.append(value)
            self._total_added += 1

    def extend(self, values: list[MetricValue]) -> None:
        """Add multiple values (thread-safe)."""
        with self._lock:
            self._buffer.extend(values)
            self._total_added += len(values)

    def get_recent(self, count: int = 100) -> list[MetricValue]:
        """Get most recent values."""
        with self._lock:
            return list(self._buffer)[-count:]

    def get_range(self, start_time: float, end_time: float | None = None) -> list[MetricValue]:
        """Get values within time range."""
        end_time = end_time or time.time()
        with self._lock:
            return [v for v in self._buffer if start_time <= v.timestamp <= end_time]

    def clear(self) -> None:
        """Clear all values."""
        with self._lock:
            self._buffer.clear()
            self._total_added = 0

    @property
    def size(self) -> int:
        """Current buffer size."""
        with self._lock:
            return len(self._buffer)

    @property
    def total_added(self) -> int:
        """Total values ever added."""
        with self._lock:
            return self._total_added


class Histogram:
    """Efficient histogram for latency distributions with O(1) incremental stats."""

    def __init__(self, max_values: int = 10000):
        self._values: deque = deque(maxlen=max_values)
        self._lock = threading.RLock()
        self._count: int = 0
        self._sum: float = 0.0
        self._min: float = float("inf")
        self._max: float = 0.0
        self._p50_cache: float = 0.0
        self._p95_cache: float = 0.0
        self._p99_cache: float = 0.0

    def record(self, value: float) -> None:
        """Record a value."""
        with self._lock:
            self._values.append(value)
            self._count += 1
            self._sum += value
            if value < self._min:
                self._min = value
            if value > self._max:
                self._max = value
            if self._count % 100 == 0:
                self._recompute_percentiles()

    def _recompute_percentiles(self) -> None:
        """Recompute percentiles every N samples to avoid O(n log n) every call."""
        if len(self._values) < 10:
            return
        sorted_vals = sorted(self._values)
        n = len(sorted_vals)
        self._p50_cache = sorted_vals[int(n * 0.5)]
        self._p95_cache = sorted_vals[int(n * 0.95)]
        self._p99_cache = sorted_vals[int(n * 0.99)]

    def snapshot(self) -> HistogramSnapshot | None:
        """Get histogram snapshot with cached percentiles."""
        with self._lock:
            if not self._values:
                return None

            n = len(self._values)
            mean = self._sum / n
            variance = sum((v - mean) ** 2 for v in self._values) / n
            std_dev = variance**0.5

            if n >= 50:
                p50, p95, p99 = self._p50_cache, self._p95_cache, self._p99_cache
            elif n >= 20:
                sorted_vals = sorted(self._values)
                p50 = sorted_vals[int(n * 0.5)]
                p95 = self._p95_cache if n >= 95 else sorted_vals[int(n * 0.95)]
                p99 = self._p99_cache if n >= 99 else sorted_vals[int(n * 0.99)]
            else:
                sorted_vals = sorted(self._values)
                p50 = sorted_vals[int(n * 0.5)]
                p95 = sorted_vals[int(n * 0.95)]
                p99 = sorted_vals[int(n * 0.99)]

            return HistogramSnapshot(
                count=n,
                sum=self._sum,
                min=self._min,
                max=self._max,
                mean=mean,
                p50=p50,
                p95=p95,
                p99=p99,
                std_dev=std_dev,
            )

    def clear(self) -> None:
        """Clear histogram."""
        with self._lock:
            self._values.clear()
            self._count = 0
            self._sum = 0.0
            self._min = float("inf")
            self._max = 0.0
            self._p50_cache = 0.0
            self._p95_cache = 0.0
            self._p99_cache = 0.0


class Metric:
    """Base metric class."""

    def __init__(self, name: str, metric_type: MetricType, description: str = ""):
        self.name = name
        self.metric_type = metric_type
        self.description = description
        self._lock = threading.RLock()
        self._created_at = time.time()

    def reset(self) -> None:
        """Reset metric to initial state."""
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:
        """Get current snapshot."""
        raise NotImplementedError


class Counter(Metric):
    """Monotonically increasing counter."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, MetricType.COUNTER, description)
        self._value: float = 0.0

    def inc(self, value: float = 1) -> None:
        """Increment counter."""
        with self._lock:
            self._value += value

    def reset(self) -> None:
        """Reset counter."""
        with self._lock:
            self._value = 0

    @property
    def value(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        return {"name": self.name, "type": "counter", "value": self.value}


class Gauge(Metric):
    """Metric that can go up and down."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, MetricType.GAUGE, description)
        self._value = 0.0
        self._history = RingBuffer(capacity=1000)

    def set(self, value: float) -> None:
        """Set gauge value."""
        with self._lock:
            self._value = value
            self._history.append(MetricValue(value, time.time()))

    def inc(self, value: float = 1) -> None:
        """Increment gauge."""
        with self._lock:
            self._value += value
            self._history.append(MetricValue(self._value, time.time()))

    def dec(self, value: float = 1) -> None:
        """Decrement gauge."""
        with self._lock:
            self._value -= value
            self._history.append(MetricValue(self._value, time.time()))

    def reset(self) -> None:
        """Reset gauge."""
        with self._lock:
            self._value = 0.0
            self._history.clear()

    @property
    def value(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": "gauge",
            "value": self.value,
            "history_size": self._history.size,
        }


class Timer(Metric):
    """Timer for measuring durations."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, MetricType.TIMER, description)
        self._histogram = Histogram()
        self._active_timers: dict[str, float] = {}

    @contextmanager
    def time(self, timer_id: str | None = None):
        """Context manager for timing code blocks."""
        timer_id = timer_id or f"{threading.current_thread().ident}_{time.time()}"
        self.start(timer_id)
        try:
            yield self
        finally:
            self.stop(timer_id)

    def start(self, timer_id: str) -> None:
        """Start a timer."""
        with self._lock:
            self._active_timers[timer_id] = time.perf_counter()

    def stop(self, timer_id: str) -> float:
        """Stop timer and record duration."""
        end = time.perf_counter()
        with self._lock:
            if timer_id not in self._active_timers:
                return 0.0
            start = self._active_timers.pop(timer_id)
            duration_ms = (end - start) * 1000
            self._histogram.record(duration_ms)
            return duration_ms

    def record(self, duration_ms: float) -> None:
        """Manually record a duration."""
        self._histogram.record(duration_ms)

    def reset(self) -> None:
        """Reset timer."""
        with self._lock:
            self._histogram.clear()
            self._active_timers.clear()

    def snapshot(self) -> dict[str, Any]:
        hist = self._histogram.snapshot()
        return {
            "name": self.name,
            "type": "timer",
            "histogram": asdict(hist) if hist else None,
        }


class MetricsCollector:
    """Central metrics collection and management."""

    _instance: MetricsCollector | None = None
    _lock = threading.Lock()

    def __new__(cls) -> MetricsCollector:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        self._initialized: bool
        if self._initialized:
            return

        self._metrics: dict[str, Metric] = {}
        self._metric_lock = threading.RLock()
        self._registry_lock = threading.Lock()
        self._subscribers: set[Callable[[str, dict[str, Any]], None]] = set()
        self._initialized = True
        self._enabled = True

        # Initialize default metrics
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """Initialize default metrics."""
        # Latency metrics
        self.register_timer("latency.first_word", "Time to first word")
        self.register_timer("latency.inter_word", "Time between words")
        self.register_timer("latency.end_to_end", "End-to-end latency")
        self.register_timer("latency.inference", "Model inference time")

        # Throughput metrics
        self.register_counter("throughput.words_total", "Total words processed")
        self.register_gauge("throughput.wpm", "Words per minute")
        self.register_gauge("throughput.rtf", "Real-time factor")

        # Resource metrics
        self.register_gauge("resource.cpu_percent", "CPU usage percentage")
        self.register_gauge("resource.memory_mb", "Memory usage in MB")
        self.register_gauge("resource.gpu_percent", "GPU usage percentage")
        self.register_gauge("resource.gpu_memory_mb", "GPU memory in MB")

        # Audio metrics
        self.register_counter("audio.samples_processed", "Audio samples processed")
        self.register_gauge("audio.drop_rate", "Audio drop rate")
        self.register_gauge("audio.buffer_health", "Buffer health percentage")
        self.register_counter("audio.vad_detections", "VAD detections")
        self.register_gauge("audio.vad_accuracy", "VAD accuracy")

        # Model metrics
        self.register_counter("model.inference_count", "Total inferences")
        self.register_gauge("model.cache_hit_rate", "Cache hit rate")
        self.register_gauge("model.queue_depth", "Inference queue depth")

        # Session metrics
        self.register_counter("session.active", "Active sessions")
        self.register_timer("session.duration", "Session duration")
        self.register_counter("session.segments_total", "Total segments")

    def register_counter(self, name: str, description: str = "") -> Counter:
        """Register a counter metric."""
        with self._metric_lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description)
            return cast(Counter, self._metrics[name])

    def register_gauge(self, name: str, description: str = "") -> Gauge:
        """Register a gauge metric."""
        with self._metric_lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description)
            return cast(Gauge, self._metrics[name])

    def register_timer(self, name: str, description: str = "") -> Timer:
        """Register a timer metric."""
        with self._metric_lock:
            if name not in self._metrics:
                self._metrics[name] = Timer(name, description)
            return cast(Timer, self._metrics[name])

    def get_metric(self, name: str) -> Metric | None:
        """Get metric by name."""
        with self._metric_lock:
            return self._metrics.get(name)

    def counter(self, name: str) -> Counter | None:
        """Get counter metric."""
        metric = self.get_metric(name)
        return metric if isinstance(metric, Counter) else None

    def gauge(self, name: str) -> Gauge | None:
        """Get gauge metric."""
        metric = self.get_metric(name)
        return metric if isinstance(metric, Gauge) else None

    def timer(self, name: str) -> Timer | None:
        """Get timer metric."""
        metric = self.get_metric(name)
        return metric if isinstance(metric, Timer) else None

    def inc(self, name: str, value: float = 1) -> None:
        """Increment a counter."""
        if not self._enabled:
            return
        counter = self.counter(name)
        if counter:
            counter.inc(value)
            self._notify(name, counter.snapshot())

    def set(self, name: str, value: float) -> None:
        """Set a gauge value."""
        if not self._enabled:
            return
        gauge = self.gauge(name)
        if gauge:
            gauge.set(value)
            self._notify(name, gauge.snapshot())

    @contextmanager
    def time(self, name: str, timer_id: str | None = None):
        """Context manager for timing."""
        if not self._enabled:
            yield None
            return

        timer = self.timer(name)
        if timer:
            with timer.time(timer_id):
                yield timer
        else:
            yield None

    def record_time(self, name: str, duration_ms: float) -> None:
        """Record a timing manually."""
        if not self._enabled:
            return
        timer = self.timer(name)
        if timer:
            timer.record(duration_ms)
            self._notify(name, timer.snapshot())

    def snapshot_all(self) -> dict[str, dict[str, Any]]:
        """Get snapshot of all metrics."""
        with self._metric_lock:
            return {name: metric.snapshot() for name, metric in self._metrics.items()}

    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._metric_lock:
            for metric in self._metrics.values():
                metric.reset()

    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Subscribe to metric updates."""
        with self._registry_lock:
            self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Unsubscribe from metric updates."""
        with self._registry_lock:
            self._subscribers.discard(callback)

    def _notify(self, name: str, data: dict[str, Any]) -> None:
        """Notify subscribers of metric update."""
        with self._registry_lock:
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(name, data)
            except Exception as e:
                logger.warning("Subscriber callback failed for metric %s: %s", name, e)

    def enable(self) -> None:
        """Enable metrics collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable metrics collection."""
        self._enabled = False

    def export_json(self, filepath: str | Path) -> None:
        """Export metrics to JSON."""
        filepath = Path(filepath)
        snapshot = {
            "exported_at": datetime.now().isoformat(),
            "metrics": self.snapshot_all(),
        }
        with open(filepath, "w") as f:
            json.dump(snapshot, f, indent=2)

    def export_csv(self, filepath: str | Path, metric_names: list[str] | None = None) -> None:
        """Export metrics to CSV."""
        filepath = Path(filepath)

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "metric_name", "type", "value"])

            for name, metric in self._metrics.items():
                if metric_names and name not in metric_names:
                    continue

                snapshot = metric.snapshot()
                if "value" in snapshot:
                    writer.writerow(
                        [
                            datetime.now().isoformat(),
                            name,
                            snapshot["type"],
                            snapshot["value"],
                        ]
                    )


class AlertManager:
    """Manages alerts for threshold violations."""

    def __init__(self):
        self._thresholds: dict[str, dict[str, Any]] = {}
        self._alerts: list[Alert] = []
        self._alert_handlers: list[Callable[[Alert], None]] = []
        self._lock = threading.RLock()
        self._alert_counter = 0

    def set_threshold(
        self,
        metric_name: str,
        min_value: float | None = None,
        max_value: float | None = None,
        severity: AlertSeverity = AlertSeverity.WARNING,
    ) -> None:
        """Set threshold for a metric."""
        with self._lock:
            self._thresholds[metric_name] = {
                "min": min_value,
                "max": max_value,
                "severity": severity,
            }

    def check_metric(self, metric_name: str, value: float) -> Alert | None:
        """Check metric against thresholds."""
        with self._lock:
            if metric_name not in self._thresholds:
                return None

            threshold = self._thresholds[metric_name]
            min_val = threshold.get("min")
            max_val = threshold.get("max")
            severity = threshold.get("severity", AlertSeverity.WARNING)

            alert = None

            if min_val is not None and value < min_val:
                self._alert_counter += 1
                alert = Alert(
                    id=f"alert_{self._alert_counter}_{int(time.time())}",
                    severity=severity,
                    metric_name=metric_name,
                    message=f"{metric_name} below threshold: {value:.2f} < {min_val:.2f}",
                    value=value,
                    threshold=min_val,
                    timestamp=time.time(),
                )
            elif max_val is not None and value > max_val:
                self._alert_counter += 1
                alert = Alert(
                    id=f"alert_{self._alert_counter}_{int(time.time())}",
                    severity=severity,
                    metric_name=metric_name,
                    message=f"{metric_name} above threshold: {value:.2f} > {max_val:.2f}",
                    value=value,
                    threshold=max_val,
                    timestamp=time.time(),
                )

            if alert:
                self._alerts.append(alert)
                self._notify_handlers(alert)

            return alert

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add alert handler."""
        with self._lock:
            self._alert_handlers.append(handler)

    def remove_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove alert handler."""
        with self._lock:
            if handler in self._alert_handlers:
                self._alert_handlers.remove(handler)

    def _notify_handlers(self, alert: Alert) -> None:
        """Notify all handlers."""
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.warning(f"Alert handler failed: {e}")

    def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
    ) -> list[Alert]:
        """Get alerts with optional filtering."""
        with self._lock:
            alerts = self._alerts

            if severity:
                alerts = [a for a in alerts if a.severity == severity]

            if acknowledged is not None:
                alerts = [a for a in alerts if a.acknowledged == acknowledged]

            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
            return False

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self._alerts.clear()

    def get_thresholds(self) -> dict[str, dict[str, Any]]:
        """Get all thresholds."""
        with self._lock:
            return self._thresholds.copy()


class PerformanceReport:
    """Performance report generator."""

    def __init__(self, collector: MetricsCollector | None = None):
        self.collector = collector or MetricsCollector()

    def generate_summary(self, time_window_seconds: int = 300) -> dict[str, Any]:
        """Generate performance summary."""
        now = time.time()
        start_time = now - time_window_seconds

        snapshot = self.collector.snapshot_all()

        # Calculate derived metrics
        total_words = 0
        rtf = 0.0
        avg_latency = 0.0

        if "throughput.words_total" in snapshot:
            total_words = snapshot["throughput.words_total"].get("value", 0)

        if "throughput.rtf" in snapshot:
            rtf = snapshot["throughput.rtf"].get("value", 0)

        latency_hist = snapshot.get("latency.end_to_end", {}).get("histogram", {})
        if latency_hist:
            avg_latency = latency_hist.get("mean", 0)

        return {
            "generated_at": datetime.now().isoformat(),
            "time_window_seconds": time_window_seconds,
            "metrics": {
                "total_words": total_words,
                "real_time_factor": rtf,
                "average_latency_ms": avg_latency,
            },
            "raw": snapshot,
        }

    def detect_regression(
        self,
        baseline: dict[str, float],
        current: dict[str, float],
        thresholds: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Detect performance regressions."""
        regressions = []
        thresholds = thresholds or {
            "latency.end_to_end": 1.2,
            "throughput.rtf": 1.1,
            "resource.cpu_percent": 1.5,
        }

        for metric, baseline_val in baseline.items():
            if metric not in current:
                continue

            current_val = current[metric]
            threshold = thresholds.get(metric, 1.1)

            ratio = current_val / baseline_val if baseline_val > 0 else 0

            if ratio > threshold:
                regressions.append(
                    {
                        "metric": metric,
                        "baseline": baseline_val,
                        "current": current_val,
                        "ratio": ratio,
                        "threshold": threshold,
                    }
                )

        return regressions


# Global instances
collector = MetricsCollector()
alert_manager = AlertManager()
reporter = PerformanceReport(collector)


def get_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return collector


def get_alert_manager() -> AlertManager:
    """Get global alert manager."""
    return alert_manager


def get_reporter() -> PerformanceReport:
    """Get global performance reporter."""
    return reporter
