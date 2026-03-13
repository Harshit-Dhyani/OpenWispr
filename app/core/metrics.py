"""Backward compatibility - metrics and performance_monitor moved to app.core.metrics package."""

from app.core.metrics.metrics import MetricsCollector  # noqa: F401
from app.core.metrics.performance_monitor import (  # noqa: F401
    PerformanceMonitor,
    get_performance_monitor,
)
