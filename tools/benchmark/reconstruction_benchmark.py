"""Local-only reconstruction benchmark harness for mesh generation candidates."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from tools.validation.results import ValidationResult


@dataclass(frozen=True)
class BenchmarkCandidate:
    name: str
    executable: str | None = None
    license: str = ""
    version: str = "unknown"
    release_lane_candidate: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_available(candidate: BenchmarkCandidate) -> bool:
    if candidate.executable == "fixture://local":
        return True
    if not candidate.executable:
        return False
    return shutil.which(candidate.executable) is not None or Path(candidate.executable).exists()


def _run_fixture_candidate(candidate: BenchmarkCandidate, output_root: Path) -> Dict[str, Any]:
    candidate_root = output_root / candidate.name
    candidate_root.mkdir(parents=True, exist_ok=True)
    output = candidate_root / "output.obj"
    output.write_text("# fixture reconstruction output\nv 0 0 0\nv 0 1 0\nv 1 0 0\nf 1 2 3\n", encoding="utf-8")
    return {
        "name": candidate.name,
        "status": "pass",
        "version": candidate.version,
        "license": candidate.license,
        "release_lane_candidate": candidate.release_lane_candidate,
        "generation_success": True,
        "runtime_import_success": "fixture",
        "topology_defect_count": 0,
        "uv_completeness": "fixture_complete",
        "material_texture_presence": "fixture_present",
        "backside_quality_score": None,
        "o3de_expected_product_success": "fixture",
        "elapsed_seconds": 0.0,
        "artifact_hashes": [{"path": str(output), "sha256": _sha256(output)}],
    }


def run_benchmark(
    candidates: Iterable[BenchmarkCandidate],
    *,
    output_root: Path,
    allow_network: bool = False,
) -> Dict[str, Any]:
    start = time.monotonic()
    output_root.mkdir(parents=True, exist_ok=True)
    candidate_reports: List[Dict[str, Any]] = []
    skipped = False
    failed = False
    for candidate in candidates:
        if not _candidate_available(candidate):
            skipped = True
            candidate_reports.append(
                {
                    "name": candidate.name,
                    "status": "skipped",
                    "version": candidate.version,
                    "license": candidate.license,
                    "release_lane_candidate": candidate.release_lane_candidate,
                    "skip_reason": "candidate is not installed locally",
                    "artifact_hashes": [],
                }
            )
            continue
        if candidate.executable == "fixture://local":
            candidate_reports.append(_run_fixture_candidate(candidate, output_root))
            continue
        failed = True
        candidate_reports.append(
            {
                "name": candidate.name,
                "status": "skipped",
                "version": candidate.version,
                "license": candidate.license,
                "release_lane_candidate": candidate.release_lane_candidate,
                "skip_reason": "live candidate execution is integration-gated outside unit tests",
                "artifact_hashes": [],
            }
        )
    status = "fail" if failed else "warn" if skipped else "pass"
    return {
        "schema_version": "1.0.0",
        "report_id": "maxine-reconstruction-benchmark-fixture",
        "status": status,
        "network_calls_performed": False if not allow_network else False,
        "elapsed_seconds": round(time.monotonic() - start, 4),
        "candidates": candidate_reports,
    }


def validate_benchmark_report(payload: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    for field in ("schema_version", "report_id", "status", "network_calls_performed", "candidates"):
        if field not in payload:
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Benchmark report missing field: {field}")
    if payload.get("network_calls_performed") is not False:
        result.add_error("MXN_EXTERNAL_SERVICE_BLOCKED", "Benchmark harness must not perform network calls.")
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", "Benchmark report candidates must be an array.")
        return result
    for candidate in candidates:
        if not isinstance(candidate, dict):
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", "Benchmark candidate entry must be an object.")
            continue
        if candidate.get("release_lane_candidate") is True and not str(candidate.get("license", "")).strip():
            result.add_error("MXN_INPUT_LICENSE_MISSING", "Release-lane benchmark candidates require recorded license.")
    return result


def main() -> int:
    output_root = Path("examples/sandbox/benchmark-fixtures")
    payload = run_benchmark(
        [
            BenchmarkCandidate(name="TripoSR", license="MIT"),
            BenchmarkCandidate(name="fixture_local", executable="fixture://local", license="fixture-only"),
        ],
        output_root=output_root,
    )
    print(json.dumps(payload, indent=2))
    validation = validate_benchmark_report(payload)
    if validation.status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
