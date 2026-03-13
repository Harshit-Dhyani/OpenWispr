"""Backward compatibility - auto_optimizer moved to app.core.optimization package."""

from app.core.optimization.auto_optimizer import (  # noqa: F401
    AutoOptimizer,
    get_recommended_settings,
)
