#!/usr/bin/env python3
"""Editor --runpython diagnostic for the non-null render/capture envelope."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.editor_python import maxine_package_prefab_smoke


if __name__ == "__main__":
    os.environ["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] = "non-null-editor-render-capture-envelope"
    raise SystemExit(maxine_package_prefab_smoke.main())
