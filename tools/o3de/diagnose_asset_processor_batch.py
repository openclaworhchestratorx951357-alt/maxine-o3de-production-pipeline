#!/usr/bin/env python3
"""Bounded diagnostics for AssetProcessorBatch executable provenance and stalls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.golden_project_fixture import DEFAULT_FIXTURE as DEFAULT_GOLDEN_PROJECT_FIXTURE


APB_TOOL_NAMES = {"assetprocessorbatch.exe", "assetprocessorbatch"}
ASSET_PROCESSOR_NAMES = {"assetprocessor.exe", "assetprocessor"}
MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PROVENANCE_INCOMPLETE = "MXN_PROVENANCE_INCOMPLETE"
MXN_APB_DIAGNOSTIC_STALLED = "MXN_APB_DIAGNOSTIC_STALLED"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "o3de-integration" / "apb" / "diagnostics"


def build_diagnostic_report(
    *,
    search_roots: Iterable[Path | str] | None = None,
    engine_root: Path | str | None = None,
    project_path: Path | str | None = None,
    candidate: Path | str | None = None,
    run_bounded_diagnostics: bool = False,
    timeout_seconds: int = 120,
    env: Mapping[str, str] | None = None,
    command_runner: Callable[..., Dict[str, Any]] | None = None,
    artifact_root: Path | str = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    selected_engine_root = _resolve_optional_path(engine_root or env.get("O3DE_ENGINE_ROOT", ""))
    selected_project_path = _resolve_optional_path(project_path or env.get("O3DE_PROJECT_PATH", ""))
    explicit_candidate = _resolve_optional_path(
        candidate or env.get("ASSET_PROCESSOR_BATCH_EXECUTABLE", "") or env.get("ASSET_PROCESSOR_BATCH", "")
    )
    roots = _collect_search_roots(search_roots, env=env, engine_root=selected_engine_root, project_path=selected_project_path)
    candidates = _inventory_candidates(
        roots,
        explicit_candidate=explicit_candidate,
        engine_root=selected_engine_root,
        project_path=selected_project_path,
    )
    selected = _select_candidate(candidates)
    rejected = [candidate_payload for candidate_payload in candidates if not selected or candidate_payload["path"] != selected["path"]]
    diagnostic_candidate = explicit_candidate or (Path(selected["path"]) if selected else _first_apb_candidate(candidates))

    command_matrix: List[Dict[str, Any]] = []
    if run_bounded_diagnostics and diagnostic_candidate:
        command_matrix = _run_diagnostic_matrix(
            diagnostic_candidate=diagnostic_candidate,
            engine_root=selected_engine_root,
            project_path=selected_project_path,
            timeout_seconds=timeout_seconds,
            env=env,
            command_runner=command_runner,
            artifact_root=_resolve_path(artifact_root),
        )

    stall_detected = any(command.get("status") == "stalled" for command in command_matrix)
    c1060_detected = any(_command_mentions(command, "C1060") for command in command_matrix)
    warnings = _unique(_candidate_warnings(candidates) + _command_warnings(command_matrix))
    errors = _unique(_candidate_errors(candidates) + _command_errors(command_matrix))
    status = _diagnostic_status(selected=selected, command_matrix=command_matrix, stall_detected=stall_detected)
    if status == "stalled" and MXN_APB_DIAGNOSTIC_STALLED not in errors:
        errors.append(MXN_APB_DIAGNOSTIC_STALLED)
    if selected is None and MXN_PROVENANCE_INCOMPLETE not in warnings:
        warnings.append(MXN_PROVENANCE_INCOMPLETE)

    report = {
        "schema_version": "1.0.0",
        "report_type": "maxine_apb_diagnostic_report",
        "generated_at": _utc_now(),
        "status": status,
        "selected_engine_root": _path_string(selected_engine_root),
        "selected_project_path": _path_string(selected_project_path),
        "selected_project_name": _read_project_name(selected_project_path),
        "apb_candidates": candidates,
        "selected_apb_candidate": selected,
        "rejected_candidates": rejected,
        "command_matrix": command_matrix,
        "timeout_policy": {
            "timeout_seconds": timeout_seconds,
            "process_tree_cleanup": True,
            "full_live_apb_retry": False,
        },
        "process_cleanup": {
            "required_on_timeout": True,
            "completed": all(command.get("status") != "stalled" or command.get("process_cleanup", {}).get("attempted") for command in command_matrix),
        },
        "stall_detected": stall_detected,
        "c1060_detected": c1060_detected,
        "live_apb_attempted": False,
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "product_matrix_result": "not_run",
        "cache_heuristic_used": False,
        "errors": errors,
        "warnings": warnings,
        "evidence_refs": _evidence_refs(command_matrix),
        "next_steps": _next_steps(selected=selected, stall_detected=stall_detected, c1060_detected=c1060_detected),
    }
    return report


def _inventory_candidates(
    roots: Iterable[Path],
    *,
    explicit_candidate: Path | None,
    engine_root: Path | None,
    project_path: Path | None,
) -> List[Dict[str, Any]]:
    paths: Dict[str, Path] = {}
    if explicit_candidate:
        paths[_norm_key(explicit_candidate)] = explicit_candidate
    for root in roots:
        if not root.exists():
            continue
        for name in ("AssetProcessorBatch.exe", "AssetProcessorBatch", "AssetProcessor.exe", "AssetProcessor"):
            for candidate in _safe_rglob(root, name):
                paths[_norm_key(candidate)] = candidate
    return sorted(
        [_candidate_payload(path, engine_root=engine_root, project_path=project_path) for path in paths.values()],
        key=lambda payload: (payload["selected_recommendation_rank"], payload["path"]),
    )


def _candidate_payload(path: Path, *, engine_root: Path | None, project_path: Path | None) -> Dict[str, Any]:
    exists = path.exists()
    is_file = exists and path.is_file()
    name = path.name
    lowered_name = name.lower()
    is_apb = lowered_name in APB_TOOL_NAMES
    is_asset_processor = lowered_name in ASSET_PROCESSOR_NAMES
    parent = path.parent
    nearby_project = _nearby_project_json(path)
    nearby_engine = _nearby_engine_json(path)
    selected_project_name = _read_project_name(project_path)
    nearby_project_name = _read_project_name(nearby_project.parent if nearby_project else None)
    under_engine = _is_relative_to(path, engine_root)
    under_project = _is_relative_to(path, project_path)
    remotecontrolhost = "remotecontrolhost" in str(path).lower()
    archived = any(part.lower() in {"_archive", "archive"} for part in path.parts) or "archive" in str(path).lower()
    project_name_mismatch = bool(nearby_project_name and selected_project_name and nearby_project_name != selected_project_name)
    matching_project = under_project or bool(nearby_project_name and nearby_project_name == selected_project_name)
    matching_engine = under_engine
    build_or_install = _is_build_or_install_path(path)
    reason, selectable = _candidate_reason(
        path=path,
        exists=exists,
        is_file=is_file,
        is_apb=is_apb,
        is_asset_processor=is_asset_processor,
        project_name_mismatch=project_name_mismatch,
        archived=archived,
        remotecontrolhost=remotecontrolhost,
        matching_project=matching_project,
        matching_engine=matching_engine,
    )
    score = _candidate_score(
        is_apb=is_apb,
        exists=exists,
        is_file=is_file,
        build_or_install=build_or_install,
        sibling_dlls_present=_has_sibling(parent, "*.dll"),
        nearby_engine=nearby_engine is not None,
        matching_project=matching_project,
        matching_engine=matching_engine,
        archived=archived,
        remotecontrolhost=remotecontrolhost,
        project_name_mismatch=project_name_mismatch,
    )
    if not selectable:
        score = min(score, 0)
    return {
        "path": str(path),
        "basename": name,
        "exists": exists,
        "is_file": is_file,
        "is_asset_processor_batch": is_apb,
        "is_rejected_asset_processor_substitute": is_asset_processor,
        "size_bytes": path.stat().st_size if is_file else 0,
        "last_modified": _mtime(path) if is_file else "",
        "parent_directory": str(parent),
        "sibling_dlls_present": _has_sibling(parent, "*.dll"),
        "sibling_config_files_present": _has_sibling(parent, "*.setreg") or _has_sibling(parent, "*.cfg") or _has_sibling(parent, "*.json"),
        "nearby_engine_json": str(nearby_engine) if nearby_engine else "",
        "nearby_project_json": str(nearby_project) if nearby_project else "",
        "nearby_project_name": nearby_project_name,
        "under_selected_engine_root": under_engine,
        "under_selected_project_path": under_project,
        "under_build_or_install_output": build_or_install,
        "remotecontrolhost_archive": remotecontrolhost and archived,
        "archived_or_copied": archived,
        "matching_engine_provenance": matching_engine,
        "matching_project_provenance": matching_project,
        "sha256": _sha256(path) if is_file else "",
        "provenance_score": score,
        "selected_recommendation_rank": -score,
        "status": "candidate" if selectable else "rejected",
        "reason": reason,
    }


def _candidate_reason(
    *,
    path: Path,
    exists: bool,
    is_file: bool,
    is_apb: bool,
    is_asset_processor: bool,
    project_name_mismatch: bool,
    archived: bool,
    remotecontrolhost: bool,
    matching_project: bool,
    matching_engine: bool,
) -> tuple[str, bool]:
    if not exists:
        return "candidate does not exist", False
    if not is_file:
        return "candidate is not a file", False
    if is_asset_processor:
        return "AssetProcessor.exe is not AssetProcessorBatch.exe and cannot be substituted", False
    if not is_apb:
        return "candidate basename is not AssetProcessorBatch.exe", False
    if project_name_mismatch:
        return "project_name mismatch between candidate provenance and selected MAXINE_GoldenCorpus project", False
    if remotecontrolhost and archived:
        return "archived RemoteControlHost APB lacks matching MAXINE_GoldenCorpus provenance", False
    if not (matching_project or matching_engine):
        return "candidate is not paired with the selected engine or project", False
    if matching_project:
        return "project-paired AssetProcessorBatch candidate", True
    return "engine-paired AssetProcessorBatch candidate", True


def _candidate_score(
    *,
    is_apb: bool,
    exists: bool,
    is_file: bool,
    build_or_install: bool,
    sibling_dlls_present: bool,
    nearby_engine: bool,
    matching_project: bool,
    matching_engine: bool,
    archived: bool,
    remotecontrolhost: bool,
    project_name_mismatch: bool,
) -> int:
    if not (is_apb and exists and is_file):
        return -500
    score = 10
    if matching_project:
        score += 120
    if matching_engine:
        score += 90
    if build_or_install:
        score += 20
    if sibling_dlls_present:
        score += 5
    if nearby_engine:
        score += 5
    if archived:
        score -= 120
    if remotecontrolhost:
        score -= 120
    if project_name_mismatch:
        score -= 300
    if not (matching_project or matching_engine):
        score -= 80
    return score


def _select_candidate(candidates: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    selectable = [candidate for candidate in candidates if candidate["status"] == "candidate" and candidate["provenance_score"] >= 80]
    if not selectable:
        return None
    return sorted(selectable, key=lambda candidate: (-int(candidate["provenance_score"]), candidate["path"]))[0]


def _run_diagnostic_matrix(
    *,
    diagnostic_candidate: Path,
    engine_root: Path | None,
    project_path: Path | None,
    timeout_seconds: int,
    env: Mapping[str, str],
    command_runner: Callable[..., Dict[str, Any]] | None,
    artifact_root: Path,
) -> List[Dict[str, Any]]:
    run_id = "apb-diagnostic-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = artifact_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix: List[Dict[str, Any]] = []
    cwd = str(project_path) if project_path else str(REPO_ROOT)
    diagnostic_env = dict(env)
    if engine_root:
        diagnostic_env["O3DE_ENGINE_ROOT"] = str(engine_root)
    if project_path:
        diagnostic_env["O3DE_PROJECT_PATH"] = str(project_path)
    diagnostic_env["ASSET_PROCESSOR_BATCH_EXECUTABLE"] = str(diagnostic_candidate)

    matrix.append(
        _normalize_diagnostic_command(
            _bounded_command(
                label="candidate_help",
                argv=[str(diagnostic_candidate), "--help"],
                cwd=cwd,
                env=diagnostic_env,
                timeout_seconds=timeout_seconds,
                output_dir=output_dir,
                command_runner=command_runner,
            )
        )
    )
    matrix.append(
        _normalize_diagnostic_command(
            _bounded_command(
                label="repo_readiness_wrapper",
                argv=[
                    sys.executable,
                    str(REPO_ROOT / "tools" / "o3de" / "asset_processor_batch.py"),
                    "--corpus",
                    str(REPO_ROOT / "examples" / "golden-corpus"),
                    "--check-local-readiness",
                    "--strict-integration",
                ],
                cwd=str(REPO_ROOT),
                env=diagnostic_env,
                timeout_seconds=min(timeout_seconds, 60),
                output_dir=output_dir,
                command_runner=command_runner,
            )
        )
    )
    return matrix


def _bounded_command(
    *,
    label: str,
    argv: List[str],
    cwd: str,
    env: Mapping[str, str],
    timeout_seconds: int,
    output_dir: Path,
    command_runner: Callable[..., Dict[str, Any]] | None,
) -> Dict[str, Any]:
    if command_runner is not None:
        return command_runner(label=label, argv=argv, cwd=cwd, env=env, timeout_seconds=timeout_seconds, output_dir=output_dir)
    stdout_path = output_dir / f"{label}.stdout.txt"
    stderr_path = output_dir / f"{label}.stderr.txt"
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=dict(env), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cleanup = {"attempted": False, "method": "", "return_code": None}
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        status = "pass" if proc.returncode == 0 else "fail"
        termination_reason = "exited"
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        cleanup = _terminate_process_tree(proc)
        stdout, stderr = proc.communicate(timeout=10)
        status = "stalled"
        termination_reason = "timeout"
        exit_code = None
    duration = round(time.monotonic() - started, 3)
    stdout_path.write_text(stdout or "", encoding="utf-8")
    stderr_path.write_text(stderr or "", encoding="utf-8")
    errors = [MXN_APB_DIAGNOSTIC_STALLED] if status == "stalled" else ([] if status == "pass" else [MXN_VALIDATION_TOOL_UNAVAILABLE])
    return {
        "label": label,
        "argv": _redacted_argv(argv),
        "cwd": cwd,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "timeout_seconds": timeout_seconds,
        "termination_reason": termination_reason,
        "process_cleanup": cleanup,
        "stdout_log_ref": _repo_relative(stdout_path),
        "stderr_log_ref": _repo_relative(stderr_path),
        "errors": errors,
        "warnings": [],
    }


def _normalize_diagnostic_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """Treat responsive unsupported help as signal, while keeping stalls/failures strict."""

    if command.get("label") != "candidate_help" or command.get("status") != "fail":
        return command
    if command.get("termination_reason") != "exited" or command.get("exit_code") is None:
        return command
    normalized = dict(command)
    warnings = list(normalized.get("warnings", []))
    if MXN_VALIDATION_TOOL_UNAVAILABLE not in warnings:
        warnings.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
    normalized["status"] = "pass"
    normalized["diagnostic_result"] = "responsive_nonzero_tolerated"
    normalized["termination_reason"] = "exited_nonzero_tolerated"
    normalized["errors"] = []
    normalized["warnings"] = warnings
    return normalized


def _terminate_process_tree(proc: subprocess.Popen[str]) -> Dict[str, Any]:
    cleanup = {"attempted": True, "method": "kill", "return_code": None}
    if platform.system().lower() == "windows":
        taskkill = subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            text=True,
            capture_output=True,
        )
        cleanup["method"] = "taskkill /T /F"
        cleanup["return_code"] = taskkill.returncode
        if taskkill.returncode == 0:
            return cleanup
    try:
        proc.kill()
        cleanup["return_code"] = 0
    except Exception:
        cleanup["return_code"] = 1
    return cleanup


def _collect_search_roots(
    search_roots: Iterable[Path | str] | None,
    *,
    env: Mapping[str, str],
    engine_root: Path | None,
    project_path: Path | None,
) -> List[Path]:
    roots: List[Path] = []
    explicit_roots = list(search_roots or [])
    for raw in explicit_roots:
        roots.append(_resolve_path(raw))
    for raw in (engine_root, project_path):
        if raw:
            roots.append(_resolve_path(raw))
    if explicit_roots:
        return _unique_paths([root for root in roots if root and root.exists()])
    roots.append(Path("C:/src/o3de"))
    roots.extend(_manifest_roots(env))
    user_profile = Path(env.get("USERPROFILE", "")) if env.get("USERPROFILE") else Path.home()
    for raw in [
        user_profile / ".o3de",
        user_profile / "O3DE",
        user_profile / "O3DE" / "Projects",
        user_profile / "O3de_GEMS_Research",
        user_profile / "O3de_GEMS_Research" / "o3de_ocV001-development",
    ]:
        roots.append(raw)
    return _unique_paths([root for root in roots if root and root.exists()])


def _manifest_roots(env: Mapping[str, str]) -> List[Path]:
    user_profile = Path(env.get("USERPROFILE", "")) if env.get("USERPROFILE") else Path.home()
    manifest = user_profile / ".o3de" / "o3de_manifest.json"
    if not manifest.exists():
        return []
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    roots: List[Path] = []
    for key in ("default_engines_folder", "default_projects_folder"):
        if payload.get(key):
            roots.append(Path(str(payload[key])))
    for key in ("engines", "projects", "external_subdirectories"):
        values = payload.get(key, [])
        if isinstance(values, list):
            roots.extend(Path(str(value)) for value in values)
    return roots


def _safe_rglob(root: Path, name: str) -> Iterable[Path]:
    try:
        for candidate in root.rglob(name):
            if candidate.is_file():
                yield candidate
    except (OSError, PermissionError):
        return


def _nearby_project_json(path: Path) -> Path | None:
    for parent in [path.parent, *path.parents]:
        candidate = parent / "project.json"
        if candidate.exists():
            return candidate
    return None


def _nearby_engine_json(path: Path) -> Path | None:
    for parent in [path.parent, *path.parents]:
        for candidate in (
            parent / "engine.json",
            parent / "o3de" / "cmake" / "engine.json",
            parent / "Cache" / "pc" / "engine.json",
        ):
            if candidate.exists():
                return candidate
    return None


def _read_project_name(project_path: Path | None) -> str:
    if not project_path:
        return ""
    project_json = project_path / "project.json"
    if not project_json.exists():
        return ""
    try:
        payload = json.loads(project_json.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    return str(payload.get("project_name", "")).strip() if isinstance(payload, Mapping) else ""


def _is_relative_to(path: Path, root: Path | None) -> bool:
    if not root:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
    except OSError:
        return False


def _is_build_or_install_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool({"build", "bin", "install"} & parts)


def _has_sibling(parent: Path, pattern: str) -> bool:
    try:
        return any(parent.glob(pattern))
    except OSError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first_apb_candidate(candidates: List[Dict[str, Any]]) -> Path | None:
    for candidate in candidates:
        if candidate.get("is_asset_processor_batch") and candidate.get("exists"):
            return Path(str(candidate["path"]))
    return None


def _candidate_warnings(candidates: List[Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    if any(candidate.get("remotecontrolhost_archive") for candidate in candidates):
        warnings.append(MXN_PROVENANCE_INCOMPLETE)
    if any(candidate.get("is_rejected_asset_processor_substitute") for candidate in candidates):
        warnings.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
    return warnings


def _candidate_errors(candidates: List[Dict[str, Any]]) -> List[str]:
    return []


def _command_errors(command_matrix: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for command in command_matrix:
        errors.extend(str(code) for code in command.get("errors", []))
    return errors


def _command_warnings(command_matrix: List[Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    for command in command_matrix:
        warnings.extend(str(code) for code in command.get("warnings", []))
    return warnings


def _diagnostic_status(
    *,
    selected: Dict[str, Any] | None,
    command_matrix: List[Dict[str, Any]],
    stall_detected: bool,
) -> str:
    if stall_detected:
        return "stalled"
    if command_matrix and any(command.get("status") == "fail" for command in command_matrix):
        return "fail"
    if selected is None:
        return "warn"
    return "pass"


def _command_mentions(command: Mapping[str, Any], needle: str) -> bool:
    for key in ("stdout", "stderr", "stdout_excerpt", "stderr_excerpt"):
        if needle.lower() in str(command.get(key, "")).lower():
            return True
    return False


def _evidence_refs(command_matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = [
        {
            "id": "apb-diagnostic-tool",
            "kind": "diagnostic_tool",
            "path": "tools/o3de/diagnose_asset_processor_batch.py",
        }
    ]
    for command in command_matrix:
        for key in ("stdout_log_ref", "stderr_log_ref"):
            if command.get(key):
                refs.append({"id": f"{command['label']}-{key}", "kind": "command_log", "path": command[key]})
    return refs


def _next_steps(*, selected: Dict[str, Any] | None, stall_detected: bool, c1060_detected: bool) -> List[str]:
    if c1060_detected:
        return ["Address O3DE build memory/toolchain/pagefile limits before rebuilding AssetProcessorBatch."]
    if stall_detected:
        return ["Use a project-paired AssetProcessorBatch build before retrying the full live golden corpus run."]
    if selected is None:
        return ["Produce or provide an AssetProcessorBatch.exe paired with C:/src/o3de and MAXINE_GoldenCorpus."]
    return ["Run readiness checks, then perform one bounded APB-only live retry in the next slice."]


def _redacted_argv(argv: Sequence[str]) -> List[str]:
    redacted: List[str] = []
    for value in argv:
        text = str(value)
        if any(marker in text.lower() for marker in ("token=", "password=", "secret=", "key=")):
            redacted.append("<redacted>")
        else:
            redacted.append(text)
    return redacted


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _resolve_optional_path(raw: Path | str | None) -> Path | None:
    if raw is None or str(raw).strip() == "":
        return None
    return _resolve_path(raw)


def _resolve_path(raw: Path | str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def _path_string(path: Path | None) -> str:
    return str(path) if path else ""


def _norm_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    result: List[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = _norm_key(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"APB diagnostic: {report['status']}")
    print(f"selected_engine_root: {report.get('selected_engine_root', '')}")
    print(f"selected_project_path: {report.get('selected_project_path', '')}")
    selected = report.get("selected_apb_candidate")
    print(f"selected_apb_candidate: {selected.get('path') if isinstance(selected, Mapping) else 'none'}")
    print(f"candidates: {len(report.get('apb_candidates', []))}")
    print(f"bounded_diagnostics: {str(bool(report.get('command_matrix'))).lower()}")
    print(f"stall_detected: {str(report.get('stall_detected', False)).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for step in report.get("next_steps", []):
        print(f"  - {step}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose AssetProcessorBatch candidate provenance and bounded stalls.")
    parser.add_argument("--inventory", action="store_true", help="Inventory APB candidates without executing them.")
    parser.add_argument("--candidate", default="", help="Specific AssetProcessorBatch.exe candidate to evaluate.")
    parser.add_argument("--project", default="", help="Selected O3DE project path.")
    parser.add_argument("--engine-root", default="", help="Selected O3DE engine root.")
    parser.add_argument("--search-root", action="append", default=[], help="Additional root to scan for APB candidates.")
    parser.add_argument("--golden-project-fixture", default=str(DEFAULT_GOLDEN_PROJECT_FIXTURE), help="Reserved for parity with APB tools.")
    parser.add_argument("--run-bounded-diagnostics", action="store_true", help="Run timeout-bound APB help/readiness diagnostics.")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout for each bounded diagnostic command.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_diagnostic_report(
        search_roots=args.search_root,
        engine_root=args.engine_root,
        project_path=args.project,
        candidate=args.candidate,
        run_bounded_diagnostics=args.run_bounded_diagnostics,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] in {"fail", "stalled"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
