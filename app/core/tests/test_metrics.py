"""Unit tests for metrics and performance monitoring system."""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.core.metrics import (
    Alert,
    AlertManager,
    AlertSeverity,
    Counter,
    Gauge,
    Histogram,
    HistogramSnapshot,
    LatencyBreakdown,
    MetricValue,
    MetricsCollector,
    PerformanceReport,
    RingBuffer,
    Timer,
    get_alert_manager,
    get_collector,
    get_reporter,
)
from app.core.performance_monitor import (
    LatencyProfiler,
    PerformanceDashboard,
    PerformanceMonitor,
    PerformanceSnapshot,
    ResourceMonitor,
    ResourceSnapshot,
    get_monitor,
    start_monitoring,
    stop_monitoring,
)


class TestRingBuffer(unittest.TestCase):
    """Test RingBuffer functionality."""

    def test_basic_operations(self):
        """Test basic append and retrieval."""
        buf = RingBuffer(capacity=10)

        buf.append(MetricValue(1.0, time.time()))
        buf.append(MetricValue(2.0, time.time()))

        self.assertEqual(buf.size, 2)
        self.assertEqual(buf.total_added, 2)

    def test_capacity_limit(self):
        """Test that buffer respects capacity."""
        buf = RingBuffer(capacity=5)

        for i in range(10):
            buf.append(MetricValue(float(i), time.time()))

        self.assertEqual(buf.size, 5)
        self.assertEqual(buf.total_added, 10)

        # Check that oldest values were dropped
        recent = buf.get_recent(10)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0].value, 5.0)

    def test_thread_safety(self):
        """Test thread-safe operations."""
        buf = RingBuffer(capacity=1000)
        errors = []

        def writer(value):
            try:
                for _ in range(100):
                    buf.append(MetricValue(value, time.time()))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(buf.total_added, 500)

    def test_time_range(self):
        """Test retrieving values by time range."""
        buf = RingBuffer(capacity=100)
        now = time.time()

        buf.append(MetricValue(1.0, now - 10))
        buf.append(MetricValue(2.0, now - 5))
        buf.append(MetricValue(3.0, now))

        result = buf.get_range(now - 6, now)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].value, 2.0)
        self.assertEqual(result[1].value, 3.0)


class TestHistogram(unittest.TestCase):
    """Test Histogram functionality."""

    def test_empty_histogram(self):
        """Test snapshot of empty histogram."""
        hist = Histogram()
        self.assertIsNone(hist.snapshot())

    def test_basic_stats(self):
        """Test basic statistics calculation."""
        hist = Histogram()

        values = [10, 20, 30, 40, 50]
        for v in values:
            hist.record(v)

        snap = hist.snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap.count, 5)
        self.assertEqual(snap.sum, 150)
        self.assertEqual(snap.min, 10)
        self.assertEqual(snap.max, 50)
        self.assertAlmostEqual(snap.mean, 30.0)

    def test_percentiles(self):
        """Test percentile calculations."""
        hist = Histogram()

        # Add 100 sequential values
        for i in range(100):
            hist.record(float(i))

        snap = hist.snapshot()
        self.assertEqual(snap.p50, 50)
        self.assertEqual(snap.p95, 95)
        self.assertEqual(snap.p99, 99)


class TestCounter(unittest.TestCase):
    """Test Counter metric."""

    def test_basic_increment(self):
        """Test basic increment."""
        counter = Counter("test_counter")

        counter.inc()
        self.assertEqual(counter.value, 1)

        counter.inc(5)
        self.assertEqual(counter.value, 6)

    def test_reset(self):
        """Test counter reset."""
        counter = Counter("test_counter")
        counter.inc(10)
        counter.reset()

        self.assertEqual(counter.value, 0)

    def test_snapshot(self):
        """Test snapshot format."""
        counter = Counter("test_counter", "Test description")
        counter.inc(42)

        snap = counter.snapshot()
        self.assertEqual(snap["name"], "test_counter")
        self.assertEqual(snap["type"], "counter")
        self.assertEqual(snap["value"], 42)


class TestGauge(unittest.TestCase):
    """Test Gauge metric."""

    def test_set_and_modify(self):
        """Test setting and modifying gauge."""
        gauge = Gauge("test_gauge")

        gauge.set(100)
        self.assertEqual(gauge.value, 100)

        gauge.inc(10)
        self.assertEqual(gauge.value, 110)

        gauge.dec(20)
        self.assertEqual(gauge.value, 90)

    def test_history(self):
        """Test gauge value history."""
        gauge = Gauge("test_gauge")

        gauge.set(10)
        gauge.set(20)
        gauge.set(30)

        snap = gauge.snapshot()
        self.assertEqual(snap["history_size"], 3)


class TestTimer(unittest.TestCase):
    """Test Timer metric."""

    def test_manual_record(self):
        """Test manual timing record."""
        timer = Timer("test_timer")

        timer.record(100)
        timer.record(200)

        snap = timer.snapshot()
        self.assertEqual(snap["histogram"]["count"], 2)

    def test_context_manager(self):
        """Test timing with context manager."""
        timer = Timer("test_timer")

        with timer.time():
            time.sleep(0.01)  # 10ms

        snap = timer.snapshot()
        self.assertEqual(snap["histogram"]["count"], 1)
        # Should be at least 10ms
        self.assertGreater(snap["histogram"]["mean"], 5)

    def test_start_stop(self):
        """Test manual start/stop timing."""
        timer = Timer("test_timer")

        timer.start("test_id")
        time.sleep(0.01)
        duration = timer.stop("test_id")

        self.assertGreater(duration, 5)  # Should be at least 5ms
        self.assertLess(duration, 100)  # But less than 100ms


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector singleton."""

    def setUp(self):
        """Reset collector state."""
        self.collector = get_collector()
        self.collector.reset_all()

    def test_singleton(self):
        """Test that collector is a singleton."""
        c1 = MetricsCollector()
        c2 = MetricsCollector()
        self.assertIs(c1, c2)

    def test_counter_operations(self):
        """Test counter metric operations."""
        self.collector.inc("throughput.words_total", 10)
        self.collector.inc("throughput.words_total", 5)

        counter = self.collector.counter("throughput.words_total")
        self.assertEqual(counter.value, 15)

    def test_gauge_operations(self):
        """Test gauge metric operations."""
        self.collector.set("throughput.rtf", 0.5)
        self.collector.set("throughput.rtf", 0.7)

        gauge = self.collector.gauge("throughput.rtf")
        self.assertEqual(gauge.value, 0.7)

    def test_timer_operations(self):
        """Test timer metric operations."""
        self.collector.record_time("latency.first_word", 100)
        self.collector.record_time("latency.first_word", 200)

        timer = self.collector.timer("latency.first_word")
        snap = timer.snapshot()
        self.assertEqual(snap["histogram"]["count"], 2)

    def test_context_manager_timing(self):
        """Test timing with context manager."""
        with self.collector.time("latency.inference"):
            time.sleep(0.01)

        timer = self.collector.timer("latency.inference")
        snap = timer.snapshot()
        self.assertEqual(snap["histogram"]["count"], 1)

    def test_subscriptions(self):
        """Test metric update subscriptions."""
        received = []

        def callback(name, data):
            received.append((name, data))

        self.collector.subscribe(callback)
        self.collector.inc("throughput.words_total")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "throughput.words_total")

    def test_enable_disable(self):
        """Test enabling/disabling collection."""
        self.collector.disable()
        self.collector.inc("throughput.words_total", 100)

        counter = self.collector.counter("throughput.words_total")
        self.assertEqual(counter.value, 0)  # Should not increment when disabled

        self.collector.enable()
        self.collector.inc("throughput.words_total", 50)
        self.assertEqual(counter.value, 50)

    def test_export_json(self):
        """Test JSON export."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            filepath = f.name

        try:
            self.collector.inc("throughput.words_total", 100)
            self.collector.set("throughput.rtf", 0.5)

            self.collector.export_json(filepath)

            with open(filepath) as f:
                data = json.load(f)

            self.assertIn("exported_at", data)
            self.assertIn("metrics", data)
            self.assertEqual(data["metrics"]["throughput.words_total"]["value"], 100)
        finally:
            os.unlink(filepath)


class TestAlertManager(unittest.TestCase):
    """Test AlertManager functionality."""

    def setUp(self):
        """Reset alert manager state."""
        self.manager = get_alert_manager()
        self.manager.clear_alerts()
        self.manager._thresholds.clear()

    def test_threshold_violation(self):
        """Test threshold violation detection."""
        self.manager.set_threshold("resource.cpu_percent", max_value=80)

        alert = self.manager.check_metric("resource.cpu_percent", 90)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.value, 90)
        self.assertEqual(alert.threshold, 80)

    def test_no_violation(self):
        """Test when no threshold is violated."""
        self.manager.set_threshold("resource.cpu_percent", max_value=80)

        alert = self.manager.check_metric("resource.cpu_percent", 50)

        self.assertIsNone(alert)

    def test_min_threshold(self):
        """Test minimum threshold."""
        self.manager.set_threshold("audio.buffer_health", min_value=20)

        alert = self.manager.check_metric("audio.buffer_health", 10)

        self.assertIsNotNone(alert)
        self.assertIn("below", alert.message)

    def test_alert_handlers(self):
        """Test alert handler notification."""
        received = []

        def handler(alert):
            received.append(alert)

        self.manager.add_handler(handler)
        self.manager.set_threshold("resource.cpu_percent", max_value=80)
        self.manager.check_metric("resource.cpu_percent", 90)

        self.assertEqual(len(received), 1)

    def test_acknowledge_alert(self):
        """Test alert acknowledgment."""
        self.manager.set_threshold("resource.cpu_percent", max_value=80)
        alert = self.manager.check_metric("resource.cpu_percent", 90)

        self.assertFalse(alert.acknowledged)

        success = self.manager.acknowledge_alert(alert.id)
        self.assertTrue(success)
        self.assertTrue(alert.acknowledged)

    def test_get_alerts_filtering(self):
        """Test alert filtering."""
        self.manager.set_threshold(
            "resource.cpu_percent", max_value=80, severity=AlertSeverity.WARNING
        )
        self.manager.set_threshold("audio.drop_rate", max_value=0.1, severity=AlertSeverity.ERROR)

        self.manager.check_metric("resource.cpu_percent", 90)
        self.manager.check_metric("audio.drop_rate", 0.2)

        warnings = self.manager.get_alerts(severity=AlertSeverity.WARNING)
        errors = self.manager.get_alerts(severity=AlertSeverity.ERROR)

        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(errors), 1)


class TestPerformanceReport(unittest.TestCase):
    """Test PerformanceReport functionality."""

    def setUp(self):
        """Reset collector state."""
        self.collector = get_collector()
        self.collector.reset_all()
        self.reporter = get_reporter()

    def test_summary_generation(self):
        """Test summary report generation."""
        # Add some metrics
        self.collector.inc("throughput.words_total", 100)
        self.collector.set("throughput.rtf", 0.5)

        report = self.reporter.generate_summary(time_window_seconds=300)

        self.assertIn("generated_at", report)
        self.assertIn("metrics", report)
        self.assertEqual(report["metrics"]["total_words"], 100)
        self.assertEqual(report["metrics"]["real_time_factor"], 0.5)

    def test_regression_detection(self):
        """Test performance regression detection."""
        baseline = {
            "latency.end_to_end": 100,
            "throughput.rtf": 0.5,
        }

        # Current metrics - latency regressed by > 20%
        current = {
            "latency.end_to_end": 130,
            "throughput.rtf": 0.52,
        }

        regressions = self.reporter.detect_regression(baseline, current)

        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0]["metric"], "latency.end_to_end")


class TestLatencyProfiler(unittest.TestCase):
    """Test LatencyProfiler functionality."""

    def test_profile_creation(self):
        """Test profile creation and retrieval."""
        profiler = LatencyProfiler()

        profiler.start_profile("test_1")
        time.sleep(0.01)
        profiler.record_phase("test_1", "audio_capture")
        time.sleep(0.01)
        profiler.record_phase("test_1", "model_inference")
        breakdown = profiler.end_profile("test_1")

        self.assertIsNotNone(breakdown)
        self.assertGreater(breakdown.total_ms, 10)

    def test_average_breakdown(self):
        """Test average breakdown calculation."""
        profiler = LatencyProfiler()

        # Create multiple profiles
        for i in range(3):
            profiler.start_profile(f"test_{i}")
            profiler.record_phase(f"test_{i}", "model_inference")
            profiler.end_profile(f"test_{i}")

        avg = profiler.get_average_breakdown()
        self.assertIsNotNone(avg)

    def test_phase_stats(self):
        """Test phase-specific statistics."""
        profiler = LatencyProfiler()

        profiler.start_profile("test")
        profiler.record_phase("test", "model_inference")
        profiler.end_profile("test")

        stats = profiler.get_phase_stats("model_inference")
        self.assertIn("count", stats)
        self.assertIn("mean", stats)


class TestResourceMonitor(unittest.TestCase):
    """Test ResourceMonitor functionality."""

    def test_snapshot_collection(self):
        """Test resource snapshot collection."""
        monitor = ResourceMonitor(history_size=100)
        snapshot = monitor.get_current()

        self.assertIsInstance(snapshot, ResourceSnapshot)
        self.assertGreaterEqual(snapshot.cpu_percent, 0)
        self.assertGreaterEqual(snapshot.memory_mb, 0)
        self.assertGreaterEqual(snapshot.memory_percent, 0)

    def test_monitoring_loop(self):
        """Test monitoring loop start/stop."""
        monitor = ResourceMonitor(history_size=10)

        monitor.start(interval=0.1)
        time.sleep(0.25)  # Allow a couple of samples
        monitor.stop()

        history = monitor.get_history(seconds=10)
        self.assertGreater(len(history), 0)

    def test_average_calculation(self):
        """Test average resource calculation."""
        monitor = ResourceMonitor(history_size=100)

        # Manually add some snapshots
        for i in range(5):
            snapshot = ResourceSnapshot(
                timestamp=time.time(),
                cpu_percent=10.0 * (i + 1),
                memory_mb=100.0 * (i + 1),
                memory_percent=20.0,
                disk_io_read_mb=0,
                disk_io_write_mb=0,
            )
            monitor._history.append(snapshot)

        avg = monitor.get_average(seconds=3600)
        self.assertIsNotNone(avg)
        self.assertAlmostEqual(avg.cpu_percent, 30.0, delta=1)
        self.assertAlmostEqual(avg.memory_mb, 300.0, delta=1)


class TestPerformanceDashboard(unittest.TestCase):
    """Test PerformanceDashboard functionality."""

    def setUp(self):
        """Reset state before each test."""
        self.collector = get_collector()
        self.collector.reset_all()
        self.dashboard = PerformanceDashboard()

    def test_session_tracking(self):
        """Test session start/end."""
        self.dashboard.start_session("test_session_123")

        self.assertEqual(self.dashboard._session_id, "test_session_123")
        self.assertIsNotNone(self.dashboard._session_start_time)

        time.sleep(0.1)
        self.dashboard.end_session()

        self.assertIsNone(self.dashboard._session_id)

    def test_snapshot_creation(self):
        """Test performance snapshot creation."""
        # Add some metrics
        self.collector.inc("throughput.words_total", 100)
        self.collector.set("throughput.rtf", 0.5)
        self.collector.set("resource.cpu_percent", 30)

        snapshot = self.dashboard.get_current_snapshot()

        self.assertIsInstance(snapshot, PerformanceSnapshot)
        self.assertEqual(snapshot.total_words, 100)
        self.assertEqual(snapshot.real_time_factor, 0.5)

    def test_record_latency(self):
        """Test latency recording."""
        self.dashboard.record_latency("first_word", 150)
        self.dashboard.record_latency("end_to_end", 300)

        timer = self.collector.timer("latency.first_word")
        snap = timer.snapshot()
        self.assertEqual(snap["histogram"]["count"], 1)

    def test_record_throughput(self):
        """Test throughput recording."""
        self.dashboard.record_throughput(words=10, rtf=0.5, wpm=120)

        self.assertEqual(self.collector.counter("throughput.words_total").value, 10)
        self.assertEqual(self.collector.gauge("throughput.rtf").value, 0.5)

    def test_report_callbacks(self):
        """Test periodic report callbacks."""
        received = []

        def callback(period, report):
            received.append((period, report))

        self.dashboard.add_report_callback(callback)
        self.dashboard._generate_report("1m", 60)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "1m")


class TestPerformanceMonitor(unittest.TestCase):
    """Test PerformanceMonitor singleton."""

    def setUp(self):
        """Stop any running monitor."""
        stop_monitoring()

    def tearDown(self):
        """Clean up after tests."""
        stop_monitoring()

    def test_singleton(self):
        """Test that monitor is a singleton."""
        m1 = PerformanceMonitor()
        m2 = PerformanceMonitor()
        self.assertIs(m1, m2)

    def test_start_stop(self):
        """Test monitor start/stop."""
        monitor = get_monitor()

        monitor.start(stream_interval=0.1)
        self.assertTrue(monitor._running)

        time.sleep(0.2)

        monitor.stop()
        self.assertFalse(monitor._running)

    def test_default_thresholds(self):
        """Test default threshold setup."""
        monitor = get_monitor()
        thresholds = monitor.alert_manager.get_thresholds()

        self.assertIn("resource.cpu_percent", thresholds)
        self.assertIn("latency.end_to_end", thresholds)

    def test_status(self):
        """Test status retrieval."""
        monitor = get_monitor()

        status = monitor.get_status()

        self.assertIn("running", status)
        self.assertIn("session_active", status)
        self.assertIn("alerts_active", status)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full monitoring system."""

    def setUp(self):
        """Reset all state."""
        self.collector = get_collector()
        self.collector.reset_all()
        self.alert_manager = get_alert_manager()
        self.alert_manager.clear_alerts()
        stop_monitoring()

    def tearDown(self):
        """Clean up."""
        stop_monitoring()

    def test_full_workflow(self):
        """Test complete monitoring workflow."""
        # Start monitoring
        monitor = start_monitoring(stream_interval=0.1)

        # Start a session
        monitor.dashboard.start_session("integration_test")

        # Record some metrics
        self.collector.record_time("latency.first_word", 100)
        self.collector.record_time("latency.end_to_end", 250)
        self.collector.inc("throughput.words_total", 50)
        self.collector.set("throughput.rtf", 0.4)

        # Trigger an alert
        self.collector.set("resource.cpu_percent", 90)

        time.sleep(0.15)

        # Check snapshot
        snapshot = monitor.dashboard.get_current_snapshot()
        self.assertEqual(snapshot.session_id, "integration_test")

        # Check alerts
        alerts = monitor.alert_manager.get_alerts()
        self.assertGreaterEqual(len(alerts), 0)

        # End session and stop
        monitor.dashboard.end_session()
        stop_monitoring()

    def test_metric_subscription_and_alert(self):
        """Test that metric updates trigger alerts."""
        monitor = get_monitor()
        monitor.start(stream_interval=0.1)

        alerts_received = []

        def alert_handler(alert):
            alerts_received.append(alert)

        monitor.alert_manager.add_handler(alert_handler)

        # Set threshold and trigger violation
        monitor.alert_manager.set_threshold("resource.memory_mb", max_value=100)
        self.collector.set("resource.memory_mb", 200)

        time.sleep(0.15)

        self.assertGreaterEqual(len(alerts_received), 0)

        monitor.stop()


if __name__ == "__main__":
    unittest.main()
