#!/usr/bin/env python3
"""Offline diagnostics for the local O3DE AssetProcessorBatch build environment."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE_ROOT = Path("C:/src/o3de")
DEFAULT_PROJECT_PATH = Path.home() / "O3DE" / "Projects" / "MAXINE_GoldenCorpus"
DEFAULT_BUILD_DIR = DEFAULT_ENGINE_ROOT / "build" / "windows"
DEFAULT_ALTERNATE_BUILD_DIR = DEFAULT_ENGINE_ROOT / "build" / "maxine_apb_profile"
MXN_VALIDATION_TOOL_UNAVAILABLE = "MXN_VALIDATION_TOOL_UNAVAILABLE"
MXN_PROVENANCE_INCOMPLETE = "MXN_PROVENANCE_INCOMPLETE"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"


def build_environment_report(
    *,
    engine_root: Path | str = DEFAULT_ENGINE_ROOT,
    project_path: Path | str = DEFAULT_PROJECT_PATH,
    build_dir: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = env if env is not None else os.environ
    engine = _resolve_path(engine_root)
    project = _resolve_path(project_path)
    build = _resolve_path(build_dir) if build_dir else engine / "build" / "windows"
    cache = _read_cmake_cache(build / "CMakeCache.txt")
    third_party = _path_from_cache_or_env(cache, "LY_3RDPARTY_PATH", env.get("LY_3RDPARTY_PATH", ""))
    apb_output = _find_apb_output(build)
    engine_report = _engine_report(engine)
    project_report = _project_report(project)
    cmake_report = _cmake_report(cache)
    visual_studio_report = _visual_studio_report(cache, env)
    windows_sdk_report = _windows_sdk_report(cache, env)
    third_party_report = _path_report(third_party)
    build_report = _build_dir_report(build, cache, apb_output)
    memory_report = _memory_report()
    disk_report = _disk_report(engine, build)

    errors: list[str] = []
    warnings: list[str] = []
    messages: list[str] = []
    if not engine_report["valid"]:
        errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
        messages.append("O3DE engine root is missing required engine markers.")
    if not project_report["valid"]:
        errors.append(MXN_PATH_UNSAFE)
        messages.append("Selected project path does not declare project_name=MAXINE_GoldenCorpus.")
    if not cmake_report["cache_present"]:
        errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
        messages.append("CMakeCache.txt is missing from the selected build directory.")
    if not visual_studio_report["msvc_tools_present"]:
        errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
        messages.append("MSVC cl.exe/link.exe were not found from cache or the current environment.")
    if not third_party_report["exists"]:
        errors.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
        messages.append("LY_3RDPARTY_PATH is missing or does not exist.")
    if not build_report["asset_processor_batch_target_present"]:
        warnings.append(MXN_PROVENANCE_INCOMPLETE)
        messages.append("AssetProcessorBatch target metadata was not found in the selected build directory.")
    if not apb_output["exists"]:
        warnings.append(MXN_VALIDATION_TOOL_UNAVAILABLE)
        messages.append("Project-paired AssetProcessorBatch.exe has not been produced yet.")

    status = "fail" if errors else "warn" if warnings else "pass"
    return {
        "schema_version": "1.0.0",
        "report_type": "maxine_o3de_apb_build_environment",
        "generated_at": _utc_now(),
        "status": status,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "is_64bit_process": sys.maxsize > 2**32,
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "selected_engine_root": str(engine),
        "selected_project_path": str(project),
        "selected_project_name": project_report["project_name"],
        "build_directory": str(build),
        "alternate_build_directory": str(DEFAULT_ALTERNATE_BUILD_DIR),
        "engine": engine_report,
        "project": project_report,
        "cmake": cmake_report,
        "visual_studio": visual_studio_report,
        "windows_sdk": windows_sdk_report,
        "ly_3rdparty_path": third_party_report,
        "build_dir": build_report,
        "asset_processor_batch_output": apb_output,
        "memory": memory_report,
        "disk": disk_report,
        "recommended_build_command": [
            "cmake",
            "--build",
            str(build),
            "--target",
            "AssetProcessorBatch",
            "--config",
            "profile",
            "--parallel",
            "1",
            "--",
            "/m:1",
            "/nodeReuse:false",
            "/v:m",
        ],
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "errors": _unique(errors),
        "warnings": _unique(warnings),
        "messages": messages,
        "next_steps": _next_steps(status=status, apb_exists=apb_output["exists"], build_dir=build),
    }


def _engine_report(engine: Path) -> Dict[str, Any]:
    markers = {
        "engine_json": engine / "engine.json",
        "o3de_bat": engine / "scripts" / "o3de.bat",
        "o3de_py": engine / "scripts" / "o3de.py",
        "gems": engine / "Gems",
        "code": engine / "Code",
        "cmake": engine / "cmake",
    }
    present = {key: path.exists() for key, path in markers.items()}
    return {
        "path": str(engine),
        "exists": engine.exists(),
        "markers": present,
        "valid": bool(engine.exists() and present["engine_json"] and (present["o3de_bat"] or present["o3de_py"])),
    }


def _project_report(project: Path) -> Dict[str, Any]:
    project_json = project / "project.json"
    payload: Dict[str, Any] = {}
    if project_json.exists():
        try:
            payload = json.loads(project_json.read_text(encoding="utf-8-sig"))
        except Exception:
            payload = {}
    name = str(payload.get("project_name", "")).strip()
    return {
        "path": str(project),
        "project_json": str(project_json),
        "exists": project.exists(),
        "project_json_exists": project_json.exists(),
        "project_name": name,
        "valid": bool(project.exists() and project_json.exists() and name == "MAXINE_GoldenCorpus"),
    }


def _read_cmake_cache(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")) or "=" not in stripped:
            continue
        key_type, value = stripped.split("=", 1)
        key = key_type.split(":", 1)[0]
        values[key] = value
    return values


def _cmake_report(cache: Mapping[str, str]) -> Dict[str, Any]:
    cmake_path = shutil.which("cmake") or ""
    version = ""
    if cmake_path:
        try:
            result = subprocess.run([cmake_path, "--version"], text=True, capture_output=True, timeout=10)
            version = (result.stdout.splitlines() or [""])[0].strip()
        except Exception:
            version = ""
    return {
        "path": cmake_path,
        "available": bool(cmake_path),
        "version": version,
        "cache_present": bool(cache),
        "generator": cache.get("CMAKE_GENERATOR", ""),
        "generator_instance": cache.get("CMAKE_GENERATOR_INSTANCE", ""),
        "generator_platform": cache.get("CMAKE_GENERATOR_PLATFORM", ""),
        "generator_toolset": cache.get("CMAKE_GENERATOR_TOOLSET", ""),
        "configuration_types": cache.get("CMAKE_CONFIGURATION_TYPES", ""),
        "install_prefix": cache.get("CMAKE_INSTALL_PREFIX", ""),
        "unity_build": cache.get("LY_UNITY_BUILD", ""),
        "source_dir": cache.get("O3DE_SOURCE_DIR", cache.get("CMAKE_HOME_DIRECTORY", "")),
    }


def _visual_studio_report(cache: Mapping[str, str], env: Mapping[str, str]) -> Dict[str, Any]:
    cl_path = _first_existing(
        cache.get("CMAKE_CXX_COMPILER", ""),
        env.get("CXX", ""),
        shutil.which("cl") or "",
        _default_msvc_tool("cl.exe"),
    )
    link_path = _first_existing(
        cache.get("CMAKE_LINKER", ""),
        shutil.which("link") or "",
        _default_msvc_tool("link.exe"),
    )
    vcvars = _first_existing(
        _path_join(cache.get("CMAKE_GENERATOR_INSTANCE", ""), "VC", "Auxiliary", "Build", "vcvars64.bat"),
        _path_join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft Visual Studio", "2022", "BuildTools", "VC", "Auxiliary", "Build", "vcvars64.bat"),
    )
    vswhere = _first_existing(
        _path_join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft Visual Studio", "Installer", "vswhere.exe"),
        _path_join(os.environ.get("ProgramFiles", ""), "Microsoft Visual Studio", "Installer", "vswhere.exe"),
    )
    installation_path = cache.get("CMAKE_GENERATOR_INSTANCE", "")
    return {
        "installation_path": installation_path,
        "vswhere_path": vswhere,
        "vcvars64_path": vcvars,
        "cl_path": cl_path,
        "link_path": link_path,
        "msvc_tools_present": bool(cl_path and link_path),
        "x64_hosted": "hostx64" in cl_path.lower() if cl_path else False,
        "developer_prompt_active": bool(env.get("VSCMD_ARG_TGT_ARCH") or env.get("VCINSTALLDIR")),
        "vctools_version": env.get("VCToolsVersion", ""),
    }


def _windows_sdk_report(cache: Mapping[str, str], env: Mapping[str, str]) -> Dict[str, Any]:
    sdk_version = env.get("WindowsSDKVersion", "") or cache.get("CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION", "")
    sdk_dir = env.get("WindowsSdkDir", "") or _path_join(os.environ.get("ProgramFiles(x86)", ""), "Windows Kits", "10")
    return {
        "version": sdk_version,
        "path": sdk_dir,
        "exists": bool(sdk_dir and Path(sdk_dir).exists()),
    }


def _path_from_cache_or_env(cache: Mapping[str, str], key: str, fallback: str) -> str:
    raw = cache.get(key, "") or fallback
    return raw.replace("@LY_3RDPARTY_PATH@", cache.get("LY_3RDPARTY_PATH", ""))


def _path_report(raw: str) -> Dict[str, Any]:
    path = _resolve_path(raw) if raw else None
    return {
        "path": str(path) if path else "",
        "present": bool(raw),
        "exists": bool(path and path.exists()),
    }


def _build_dir_report(build: Path, cache: Mapping[str, str], apb_output: Mapping[str, Any]) -> Dict[str, Any]:
    target_files = [
        build / "Code" / "Tools" / "AssetProcessor" / "AssetProcessorBatch.vcxproj",
        build / "runtime_dependencies" / "profile" / "AssetProcessorBatch.cmake",
    ]
    recent_logs = sorted((REPO_ROOT / "artifacts" / "o3de-integration" / "setup").glob("build*AssetProcessorBatch*.txt")) if (REPO_ROOT / "artifacts" / "o3de-integration" / "setup").exists() else []
    c1060_detected = False
    for log in recent_logs[-8:]:
        try:
            if "C1060" in log.read_text(encoding="utf-8", errors="replace"):
                c1060_detected = True
                break
        except Exception:
            continue
    return {
        "path": str(build),
        "exists": build.exists(),
        "cache_path": str(build / "CMakeCache.txt"),
        "cache_present": bool(cache),
        "generator": cache.get("CMAKE_GENERATOR", ""),
        "asset_processor_batch_target_present": any(path.exists() for path in target_files),
        "asset_processor_batch_output_exists": bool(apb_output.get("exists")),
        "bin_profile_exists": (build / "bin" / "profile").exists(),
        "historical_c1060_detected": c1060_detected,
    }


def _find_apb_output(build: Path) -> Dict[str, Any]:
    candidates = [
        build / "bin" / "profile" / "AssetProcessorBatch.exe",
        build / "bin" / "debug" / "AssetProcessorBatch.exe",
        build / "bin" / "release" / "AssetProcessorBatch.exe",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return {"path": str(candidate), "exists": True, "size_bytes": candidate.stat().st_size}
    expected = candidates[0]
    return {"path": str(expected), "exists": False, "size_bytes": 0}


def _memory_report() -> Dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"available": False, "summary": "Windows memory/pagefile details unavailable on this platform."}
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return {"available": False, "summary": "PowerShell unavailable."}
    command = (
        "$os=Get-CimInstance Win32_OperatingSystem; "
        "$pf=Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{"
        "total_physical_kib=$os.TotalVisibleMemorySize;"
        "free_physical_kib=$os.FreePhysicalMemory;"
        "total_virtual_kib=$os.TotalVirtualMemorySize;"
        "free_virtual_kib=$os.FreeVirtualMemory;"
        "pagefiles=@($pf|ForEach-Object{[pscustomobject]@{name=$_.Name;allocated_mb=$_.AllocatedBaseSize;current_mb=$_.CurrentUsage;peak_mb=$_.PeakUsage}})"
        "} | ConvertTo-Json -Depth 5"
    )
    try:
        result = subprocess.run([powershell, "-NoProfile", "-Command", command], text=True, capture_output=True, timeout=20)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return {"available": False, "summary": "Could not query memory/pagefile details."}


def _disk_report(engine: Path, build: Path) -> Dict[str, Any]:
    roots = {"engine_drive": engine.anchor or str(engine), "build_drive": build.anchor or str(build)}
    report: Dict[str, Any] = {}
    for key, root in roots.items():
        try:
            usage = shutil.disk_usage(root)
            report[key] = {"root": root, "free_bytes": usage.free, "total_bytes": usage.total}
        except Exception:
            report[key] = {"root": root, "free_bytes": 0, "total_bytes": 0}
    return report


def _next_steps(*, status: str, apb_exists: bool, build_dir: Path) -> list[str]:
    if apb_exists:
        return [
            "Run APB inventory and bounded diagnostics against the produced AssetProcessorBatch.exe.",
            "Keep the full live golden corpus APB retry in the next slice unless bounded diagnostics prove it is safe.",
        ]
    if status == "fail":
        return [
            "Fix the missing build prerequisite reported above before running the APB target build.",
            "Do not run live APB until the build-environment report is pass or warn only for missing APB output.",
        ]
    return [
        f"Build only the AssetProcessorBatch target from {build_dir} with profile config and parallelism 1.",
        "Preserve build logs under artifacts/o3de-integration/setup/ and do not commit raw logs.",
    ]


def _resolve_path(path: Path | str) -> Path:
    return Path(str(path)).expanduser()


def _first_existing(*values: str) -> str:
    for value in values:
        if value and Path(value).exists():
            return str(Path(value))
    return ""


def _default_msvc_tool(name: str) -> str:
    root = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft Visual Studio" / "2022" / "BuildTools" / "VC" / "Tools" / "MSVC"
    if not root.exists():
        return ""
    for candidate in sorted(root.glob(f"*/bin/Hostx64/x64/{name}"), reverse=True):
        if candidate.exists():
            return str(candidate)
    return ""


def _path_join(base: str, *parts: str) -> str:
    if not base:
        return ""
    return str(Path(base).joinpath(*parts))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def print_text_report(report: Mapping[str, Any]) -> None:
    print(f"O3DE APB build environment: {report['status']}")
    print(f"engine_root: {report['selected_engine_root']}")
    print(f"project_path: {report['selected_project_path']}")
    print(f"build_directory: {report['build_directory']}")
    print(f"cmake_generator: {report['cmake'].get('generator', '')}")
    print(f"msvc_tools_present: {str(report['visual_studio'].get('msvc_tools_present', False)).lower()}")
    print(f"ly_3rdparty_path_exists: {str(report['ly_3rdparty_path'].get('exists', False)).lower()}")
    print(f"asset_processor_batch_output: {report['asset_processor_batch_output'].get('path', '')}")
    print(f"asset_processor_batch_output_exists: {str(report['asset_processor_batch_output'].get('exists', False)).lower()}")
    for code in report.get("errors", []):
        print(f"  error: {code}")
    for code in report.get("warnings", []):
        print(f"  warning: {code}")
    for message in report.get("messages", []):
        print(f"  - {message}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect local O3DE APB build prerequisites without running APB or Editor.")
    parser.add_argument("--engine-root", default=str(DEFAULT_ENGINE_ROOT), help="Selected O3DE engine root.")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_PATH), help="Controlled MAXINE_GoldenCorpus project path.")
    parser.add_argument("--build-dir", default="", help="Existing or alternate O3DE build directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    parser.add_argument("--output", default="", help="Optional JSON report output path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_environment_report(
        engine_root=args.engine_root,
        project_path=args.project,
        build_dir=args.build_dir or None,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
