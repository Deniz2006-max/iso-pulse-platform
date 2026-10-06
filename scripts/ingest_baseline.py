#!/usr/bin/env python3
"""Alias for `scripts/index_mevzuat.py` — incremental embed into Chroma.

Already-ingested chroma_ids are skipped. BGE-M3 loads only when there are
new provisions to upsert.
"""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).with_name("index_mevzuat.py")
    runpy.run_path(str(target), run_name="__main__")
