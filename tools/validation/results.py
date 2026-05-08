"""Small result objects shared by production-readiness validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


FAIL_STATUSES = {"fail"}
WARN_STATUSES = {"warn", "pending_manual"}


@dataclass
class ValidationResult:
    status: str = "pass"
    messages: List[str] = field(default_factory=list)
    error_codes: List[str] = field(default_factory=list)
    warning_codes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def add_error(self, code: str, message: str) -> None:
        if code not in self.error_codes:
            self.error_codes.append(code)
        self.messages.append(message)
        self.status = "fail"

    def add_warning(self, code: str, message: str) -> None:
        if code not in self.warning_codes:
            self.warning_codes.append(code)
        self.messages.append(message)
        if self.status != "fail":
            self.status = "warn"

    def add_pending_manual(self, code: str, message: str) -> None:
        if code not in self.warning_codes:
            self.warning_codes.append(code)
        self.messages.append(message)
        if self.status != "fail":
            self.status = "pending_manual"

    def merge(self, other: "ValidationResult") -> None:
        for code in other.error_codes:
            if code not in self.error_codes:
                self.error_codes.append(code)
        for code in other.warning_codes:
            if code not in self.warning_codes:
                self.warning_codes.append(code)
        self.messages.extend(other.messages)
        self.details.update(other.details)
        self.status = combine_statuses([self.status, other.status])

    def to_payload(self, **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": self.status,
            "error_codes": self.error_codes,
            "warning_codes": self.warning_codes,
            "messages": self.messages,
        }
        if self.details:
            payload["details"] = self.details
        payload.update(extra)
        return payload


def combine_statuses(statuses: Iterable[str]) -> str:
    normalized = [str(status).strip() for status in statuses if str(status).strip()]
    if any(status in FAIL_STATUSES for status in normalized):
        return "fail"
    if "pending_manual" in normalized:
        return "pending_manual"
    if any(status in WARN_STATUSES for status in normalized):
        return "warn"
    return "pass"
