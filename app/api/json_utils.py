"""JSON serialization utilities for API responses.

This module provides the make_json_safe function that recursively converts
Python objects to JSON-serializable types. Handles:

- NumPy scalars and arrays (numpy.int64 -> int, numpy.float64 -> float)
- Dataclasses (converted to dict)
- Path objects (converted to string)
- datetime/date objects (converted to ISO format)
- Pydantic models (via model_dump)
- Nested dicts, lists, tuples, sets

This is essential for WebSocket and SSE responses where complex objects
must be serialized to JSON.

Example:
    from app.api.json_utils import make_json_safe
    
    data = {
        "array": np.array([1, 2, 3]),
        "timestamp": datetime.now(),
        "path": Path("/tmp/file.txt"),
    }
    json_str = json.dumps(make_json_safe(data))
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np


def make_json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return make_json_safe(value.tolist())
    if is_dataclass(value):
        return make_json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return make_json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    return value
