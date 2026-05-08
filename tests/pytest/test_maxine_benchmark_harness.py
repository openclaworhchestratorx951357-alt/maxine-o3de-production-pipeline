import json
from pathlib import Path

from tools.benchmark.reconstruction_benchmark import (
    BenchmarkCandidate,
    run_benchmark,
    validate_benchmark_report,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_REPORT = REPO_ROOT / "examples" / "production" / "benchmark_report.fixture.example.json"


def test_unavailable_candidate_skipped_not_failed(tmp_path: Path):
    report = run_benchmark(
        [BenchmarkCandidate(name="TripoSR", executable=None, license="MIT")],
        output_root=tmp_path,
    )

    assert report["status"] == "warn"
    assert report["candidates"][0]["status"] == "skipped"


def test_local_fake_candidate_produces_fixture_output(tmp_path: Path):
    report = run_benchmark(
        [BenchmarkCandidate(name="fixture_local", executable="fixture://local", license="fixture-only")],
        output_root=tmp_path,
    )

    candidate = report["candidates"][0]
    assert candidate["status"] == "pass"
    assert candidate["artifact_hashes"]
    assert (tmp_path / "fixture_local" / "output.obj").exists()


def test_benchmark_report_schema_validates():
    payload = json.loads(BENCHMARK_REPORT.read_text(encoding="utf-8-sig"))
    result = validate_benchmark_report(payload)

    assert result.ok


def test_license_required_for_release_lane_candidate_report():
    report = {
        "schema_version": "1.0.0",
        "report_id": "benchmark-no-license",
        "status": "pass",
        "network_calls_performed": False,
        "candidates": [
            {
                "name": "fixture_local",
                "status": "pass",
                "release_lane_candidate": True,
                "license": "",
                "artifact_hashes": [],
            }
        ],
    }

    result = validate_benchmark_report(report)

    assert not result.ok
    assert "license" in " ".join(result.messages)


def test_no_network_path_exists_in_tests(tmp_path: Path):
    report = run_benchmark(
        [BenchmarkCandidate(name="fixture_local", executable="fixture://local", license="fixture-only")],
        output_root=tmp_path,
        allow_network=False,
    )

    assert report["network_calls_performed"] is False
