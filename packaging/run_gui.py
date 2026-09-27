"""PyInstaller 진입점 — GUI. `python -m aoi_hw_check.gui`와 동일하게 동작한다."""

from __future__ import annotations

import sys

from aoi_hw_check.gui import main

if __name__ == "__main__":
    sys.exit(main())
