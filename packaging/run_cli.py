"""PyInstaller 진입점 — CLI. `python -m aoi_hw_check.cli`와 동일하게 동작한다."""

from __future__ import annotations

import sys

from aoi_hw_check.cli import main

if __name__ == "__main__":
    sys.exit(main())
