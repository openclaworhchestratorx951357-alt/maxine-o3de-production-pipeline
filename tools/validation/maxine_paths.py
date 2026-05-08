"""Centralized path normalization and publication path safety for MAXINE."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, List


MXN_INPUT_MISSING = "MXN_INPUT_MISSING"
MXN_PATH_UNSAFE = "MXN_PATH_UNSAFE"


@dataclass(frozen=True)
class PathResult:
    ok: bool
    raw_path: str
    normalized_path: str = ""
    absolute_path: Path | None = None
    relative_path: str = ""
    error_code: str = ""
    message: str = ""


def resolve_repo_root(start: Path | None = None) -> Path:
    base = (start or Path(__file__)).resolve()
    for candidate in [base, *base.parents]:
        if (candidate / ".git").exists() or (candidate / "schemas").exists():
            return candidate
    return Path(__file__).resolve().parents[2]


def resolve_project_root(repo_root: Path | None = None) -> Path:
    root = (repo_root or resolve_repo_root()).resolve()
    projects = root / "Projects"
    if projects.exists():
        return projects.resolve()
    return root


def normalize_path_text(raw_path: str | Path) -> str:
    text = str(raw_path).strip().replace("\\", "/")
    while "//" in text and not text.startswith("//"):
        text = text.replace("//", "/")
    return text


def _is_windows_absolute(raw: str) -> bool:
    return bool(PureWindowsPath(raw).drive)


def _is_relative(raw: str) -> bool:
    return not Path(raw).is_absolute() and not _is_windows_absolute(raw)


def _within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _to_relative_text(path: Path, root: Path) -> str:
    return normalize_path_text(path.resolve().relative_to(root.resolve()))


def project_relative_path(raw_path: str | Path, project_root: Path | None = None) -> PathResult:
    raw = str(raw_path).strip()
    normalized = normalize_path_text(raw)
    root = (project_root or resolve_project_root()).resolve()

    if not raw:
        return PathResult(
            ok=False,
            raw_path=raw,
            normalized_path=normalized,
            error_code=MXN_INPUT_MISSING,
            message="Path value is empty.",
        )

    if _is_relative(raw):
        posix = PurePosixPath(normalized)
        if posix.is_absolute() or ".." in posix.parts:
            return PathResult(
                ok=False,
                raw_path=raw,
                normalized_path=normalized,
                error_code=MXN_PATH_UNSAFE,
                message="Relative project paths cannot be absolute or contain parent traversal.",
            )
        return PathResult(
            ok=True,
            raw_path=raw,
            normalized_path=normalized,
            absolute_path=(root / Path(*posix.parts)).resolve(),
            relative_path=normalized,
        )

    candidate = Path(raw).resolve()
    if not _within(candidate, root):
        return PathResult(
            ok=False,
            raw_path=raw,
            normalized_path=normalized,
            absolute_path=candidate,
            error_code=MXN_PATH_UNSAFE,
            message=f"Path resolves outside approved project root: {root}",
        )
    return PathResult(
        ok=True,
        raw_path=raw,
        normalized_path=normalized,
        absolute_path=candidate,
        relative_path=_to_relative_text(candidate, root),
    )


def validate_publication_path(
    raw_path: str | Path,
    approved_roots: Iterable[Path],
    *,
    must_exist: bool = False,
) -> PathResult:
    raw = str(raw_path).strip()
    normalized = normalize_path_text(raw)
    roots: List[Path] = [root.resolve() for root in approved_roots]
    if not raw:
        return PathResult(False, raw, normalized, error_code=MXN_INPUT_MISSING, message="Path value is empty.")

    candidate = Path(raw)
    if _is_relative(raw):
        candidate = roots[0] / Path(*PurePosixPath(normalized).parts)
    candidate = candidate.resolve()

    matching_root = next((root for root in roots if _within(candidate, root)), None)
    if matching_root is None:
        return PathResult(
            ok=False,
            raw_path=raw,
            normalized_path=normalized,
            absolute_path=candidate,
            error_code=MXN_PATH_UNSAFE,
            message="Publication path is outside approved roots.",
        )
    if must_exist and not candidate.exists():
        return PathResult(
            ok=False,
            raw_path=raw,
            normalized_path=normalized,
            absolute_path=candidate,
            relative_path=_to_relative_text(candidate, matching_root),
            error_code=MXN_INPUT_MISSING,
            message="Required publication path does not exist.",
        )
    return PathResult(
        ok=True,
        raw_path=raw,
        normalized_path=normalized,
        absolute_path=candidate,
        relative_path=_to_relative_text(candidate, matching_root),
    )
