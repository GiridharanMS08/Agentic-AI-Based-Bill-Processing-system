from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    source_file: str
    file_bytes: bytes
    ocr_text: str
    ocr_confidence: Decimal
    local_extracted: dict[str, Any]
    extracted: dict[str, Any]
    category: str
    validation_status: str
    validation_notes: list[str]
    stored_bill_id: int | None
    was_duplicate: bool
    affected_weeks: list[str]
    affected_months: list[str]
    gemini_used: bool
    gemini_calls: int
    error: str | None
