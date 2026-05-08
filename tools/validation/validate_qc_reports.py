#!/usr/bin/env python3
"""Validate MAXINE QC report examples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validation.results import combine_statuses
from tools.validation.schema_utils import load_json, print_result, schema_validate


SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.qc-report.schema.json"
DEFAULT_REPORT = REPO_ROOT / "examples" / "production" / "qc_report.release_rigged.pass.example.json"


def _validate_report(path: Path):
    result = schema_validate(load_json(path), load_json(SCHEMA_PATH))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MAXINE QC report JSON.")
    parser.add_argument("report", nargs="*", help="QC report paths.")
    args = parser.parse_args()
    paths = [Path(raw) for raw in args.report] if args.report else [DEFAULT_REPORT]
    statuses = []
    for path in paths:
        if not path.is_absolute():
            path = REPO_ROOT / path
        result = _validate_report(path)
        print_result(str(path), result)
        statuses.append(result.status)
    overall = combine_statuses(statuses)
    print(f"Overall QC report validation: {overall}")
    return 0 if overall == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
