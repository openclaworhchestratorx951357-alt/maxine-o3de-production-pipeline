#!/usr/bin/env python3
"""Validate a design-only sandbox rollback artifact structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_FIELDS = [
    "schema_version",
    "rollback_id",
    "sandbox_id",
    "source_manifest",
    "target_manifest_copy",
    "pre_write_snapshot",
    "pre_write_snapshot_sha256",
    "proposed_post_write_state",
    "proposed_field_changes",
    "rollback_actions",
    "rollback_report_path",
    "operator_approval_ref",
    "execution_gate_ref",
    "safety",
]

REQUIRED_SAFETY = {
    "read_only_contract": True,
    "rollback_execution_implemented": False,
    "sandbox_write_implemented": False,
    "production_paths_allowed": False,
    "o3de_engine_modification_allowed": False,
    "maxineshow_project_modification_allowed": False,
    "asset_processor_allowed": False,
    "o3de_editor_allowed": False,
    "prefab_publication_allowed": False,
    "entity_spawn_allowed": False,
    "real_asset_ids_allowed": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sandbox rollback artifact structure.")
    parser.add_argument("--artifact", required=True, help="Path to rollback artifact JSON")
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_disallowed_patterns(value: Any, failures: List[str], path: str = "root") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k).lower()
            child_path = f"{path}.{k}"
            if "assetid" in key or "asset_id" in key:
                text = str(v).strip().lower() if not isinstance(v, (dict, list)) else ""
                if v not in (None, "", False) and text not in ("", "false", "none", "null"):
                    failures.append(f"real Asset ID-like claim detected at {child_path}")
            if key == "resolved" and v is True:
                failures.append(f"actual resolved write claim detected at {child_path}")
            find_disallowed_patterns(v, failures, child_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            find_disallowed_patterns(item, failures, f"{path}[{idx}]")


def main() -> int:
    args = parse_args()
    artifact_path = Path(args.artifact)
    if not artifact_path.is_absolute():
        artifact_path = (Path(__file__).resolve().parents[2] / artifact_path).resolve()

    if not artifact_path.exists():
        print(f"FAIL: artifact not found: {artifact_path}")
        return 2

    try:
        artifact = load_json(artifact_path)
    except Exception as exc:
        print(f"FAIL: unable to parse artifact JSON: {exc}")
        return 2

    failures: List[str] = []

    for field in REQUIRED_FIELDS:
        if field not in artifact:
            failures.append(f"missing required field: {field}")

    for path_field in ["target_manifest_copy", "pre_write_snapshot"]:
        if path_field in artifact and not isinstance(artifact[path_field], str):
            failures.append(f"{path_field} must be a path string")

    if "proposed_field_changes" in artifact and not isinstance(artifact["proposed_field_changes"], list):
        failures.append("proposed_field_changes must be an array")

    if "rollback_actions" in artifact and not isinstance(artifact["rollback_actions"], list):
        failures.append("rollback_actions must be an array")

    safety = artifact.get("safety", {})
    if not isinstance(safety, dict):
        failures.append("safety must be an object")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) is not expected:
                failures.append(f"safety.{key} must be {str(expected).lower()}")

    find_disallowed_patterns(artifact, failures)

    if failures:
        print("FAIL: sandbox rollback artifact verification failed.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("PASS: sandbox rollback artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
