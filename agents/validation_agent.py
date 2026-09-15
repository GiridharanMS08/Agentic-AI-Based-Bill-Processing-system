from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class ValidationAgent:
    name = "Validation Agent"
    REQUIRED = ("provider_name", "bill_date", "amount")

    @staticmethod
    def normalize(extracted: dict) -> dict:
        result = dict(extracted)
        if result.get("provider_name"):
            result["provider_name"] = str(result["provider_name"]).strip()[:255]
        if result.get("currency"):
            result["currency"] = str(result["currency"]).upper().strip()[:10]
        if result.get("payment_mode"):
            result["payment_mode"] = str(result["payment_mode"]).strip()[:50]
        if result.get("bill_number"):
            result["bill_number"] = str(result["bill_number"]).strip()[:100]
        if result.get("amount") not in (None, ""):
            result["amount"] = Decimal(str(result["amount"])).quantize(Decimal("0.01"))
        if result.get("bill_date"):
            result["bill_date"] = date.fromisoformat(str(result["bill_date"])).isoformat()
        if result.get("bill_time"):
            result["bill_time"] = datetime.strptime(str(result["bill_time"]), "%H:%M").strftime("%H:%M")
        return result

    def run(self, extracted: dict, confidence: Decimal) -> tuple[str, list[str]]:
        notes: list[str] = []
        try:
            e = self.normalize(extracted)
        except (ValueError, InvalidOperation, TypeError) as exc:
            return "invalid", [f"normalization failed: {exc}"]

        missing = [field for field in self.REQUIRED if e.get(field) in (None, "")]
        notes.extend(f"{field} missing" for field in missing)

        amount = e.get("amount")
        if amount is not None and amount < Decimal("0"):
            notes.append("amount cannot be negative")
        if amount is not None and amount > Decimal("100000000"):
            notes.append("amount exceeds configured sanity limit")
        if e.get("bill_date") and date.fromisoformat(e["bill_date"]) > date.today():
            notes.append("bill_date is in the future")
        if confidence < Decimal("45"):
            notes.append("OCR confidence below 45%")

        hard_errors = [x for x in notes if "missing" in x or "failed" in x or "cannot" in x or "exceeds" in x]
        if hard_errors:
            return "invalid", notes
        if notes:
            return "warning", notes
        return "valid", ["All validation checks passed."]
