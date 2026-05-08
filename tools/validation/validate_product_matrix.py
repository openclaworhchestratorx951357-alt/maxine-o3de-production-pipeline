#!/usr/bin/env python3
"""Validate MAXINE product matrix examples and lane product rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.product_matrix_resolver import validate_product_matrix_payload
from tools.validation.results import combine_statuses
from tools.validation.schema_utils import load_json, print_result, schema_validate


SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.product-matrix.schema.json"
DEFAULT_PATH = REPO_ROOT / "examples" / "production" / "product_matrix_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MAXINE product matrix JSON.")
    parser.add_argument("matrix", nargs="?", default=str(DEFAULT_PATH))
    args = parser.parse_args()

    path = Path(args.matrix)
    if not path.is_absolute():
        path = REPO_ROOT / path
    schema = load_json(SCHEMA_PATH)
    payload = load_json(path)
    result = schema_validate(payload, schema)
    result.merge(validate_product_matrix_payload(payload))
    print_result(str(path), result)
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
