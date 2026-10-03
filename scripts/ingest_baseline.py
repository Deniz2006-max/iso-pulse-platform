#!/usr/bin/env python3
"""Alias for `scripts/index_mevzuat.py` — embed data/mevzuat into Chroma."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).with_name("index_mevzuat.py")
    runpy.run_path(str(target), run_name="__main__")
