"""OpenWispr application package."""

from __future__ import annotations

import numpy as np


def _patch_numpy_fromstring_binary_mode() -> None:
    original_fromstring = np.fromstring

    def compat_fromstring(string, dtype=float, count=-1, sep="", *, like=None):
        if sep == "" and not isinstance(string, str):
            return np.frombuffer(string, dtype=dtype, count=count)
        return original_fromstring(string, dtype=dtype, count=count, sep=sep, like=like)

    if getattr(np.fromstring, "__name__", "") != "compat_fromstring":
        np.fromstring = compat_fromstring


_patch_numpy_fromstring_binary_mode()

