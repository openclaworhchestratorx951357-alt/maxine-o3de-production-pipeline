#!/usr/bin/env python3
"""Run the focused Editor viewport materialization readiness smoke."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.editor_python import maxine_package_prefab_smoke


def main() -> int:
    os.environ["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] = (
        "focused-editor-viewport-activation-default-viewport-materialization"
    )
    os.environ.setdefault("MAXINE_ENABLE_FOCUSED_EDITOR_VIEWPORT_MATERIALIZATION", "1")
    os.environ.setdefault("MAXINE_ENABLE_OPERATOR_AP_ALIGNMENT_REMEDIATION_VERIFICATION", "1")
    os.environ.setdefault("MAXINE_ENABLE_ASSET_PROCESSOR_PROJECT_BUILD_ALIGNMENT_REPAIR", "1")
    os.environ.setdefault("MAXINE_ENABLE_EDITOR_AP_NEGOTIATION_VIEWPORT_MATERIALIZATION_READINESS", "1")
    os.environ.setdefault("MAXINE_ENABLE_EDITOR_NONBLOCKING_VIEWPORT_SWAPCHAIN_READINESS", "1")
    os.environ.setdefault("MAXINE_ENABLE_EDITOR_SAFE_TEMP_VISUAL_SCENE_DISPLAY_CONTEXT", "1")
    return maxine_package_prefab_smoke.main()


if __name__ == "__main__":
    raise SystemExit(main())
