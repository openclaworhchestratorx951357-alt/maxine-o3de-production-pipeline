"""Mixamo optional/manual policy validation."""

from __future__ import annotations

from typing import Any, Dict

from tools.validation.results import ValidationResult


def validate_mixamo_policy(manifest: Dict[str, Any], *, offline: bool = True) -> ValidationResult:
    result = ValidationResult()
    mixamo = manifest.get("mixamo")
    if not isinstance(mixamo, dict):
        return result

    if mixamo.get("automation_attempted") is True and offline:
        result.add_error(
            "MXN_EXTERNAL_SERVICE_BLOCKED",
            "Offline/no-external-services mode blocks Mixamo or Adobe automation attempts.",
        )
        return result

    if mixamo.get("external_service_optional") is not True:
        result.add_error("MXN_EXTERNAL_SERVICE_BLOCKED", "Mixamo must be classified as an optional external service.")

    status = str(mixamo.get("status", "")).strip()
    if status == "pending_manual":
        result.add_pending_manual(
            "MXN_MIXAMO_PENDING_MANUAL",
            "Mixamo handoff is pending manual action; local outputs must be preserved and hash-tracked before release.",
        )
        if not mixamo.get("manual_action_required_at_utc"):
            result.add_error("MXN_PROVENANCE_INCOMPLETE", "Mixamo pending-manual handoff requires manual_action_required_at_utc.")
    elif status in {"not_used", "complete", ""}:
        return result
    else:
        result.add_error("MXN_EXTERNAL_SERVICE_BLOCKED", f"Unsupported Mixamo policy status: {status}")
    return result
