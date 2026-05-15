#!/usr/bin/env python3
"""Non-null Editor visual runner readiness/temp-scene contract wrapper."""

from __future__ import annotations

import os

import maxine_package_prefab_smoke


if __name__ == "__main__":
    os.environ["MAXINE_EDITOR_SMOKE_DIAGNOSTIC_MODE"] = "non-null-editor-visual-runner-readiness"
    raise SystemExit(maxine_package_prefab_smoke.main())
