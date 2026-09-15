from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


class ExtractionAgent:
    name = "Extraction Agent"

    @staticmethod
    def local_extract(text: str) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        def first_match(patterns):
            for line in lines:
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
            return None

        provider = first_match([r"^(?:provider|merchant|restaurant|store|vendor)\s*[:#-]\s*(.+)$"])
        if not provider and lines:
            provider = lines[0][:200]

        bill_number = first_match([
            r"(?:invoice|bill|receipt)\s*(?:no|number|#)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]{2,})",
            r"(?:invoice|bill|receipt)\s*[:#-]\s*([A-Z0-9][A-Z0-9/-]{2,})",
        ])
        payment = first_match([r"(?:payment|paid via|mode)\s*[:#-]\s*(.+)$"])

        currency = "INR" if re.search(r"(?:₹|\bINR\b|\bRs\.?\b|\bRu(?:pees)?\b)", text, re.I) else None
        for code in ("USD", "EUR", "GBP"):
            if re.search(rf"\b{code}\b", text, re.I):
                currency = code
                break

        bill_date = None
        date_patterns = [
            r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b",
            r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b",
        ]
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                try:
                    if len(match.groups()) == 3 and len(match.group(1)) == 4:
                        bill_date = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date().isoformat()
                    else:
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        if year < 70:
                            year += 2000
                        elif year < 100:
                            year += 1900
                        bill_date = datetime(year, month, day).date().isoformat()
                    break
                except ValueError:
                    continue
            if bill_date:
                break

        bill_time = None
        match = re.search(r"\b(\d{1,2}:\d{2})(?:\s*(AM|PM))?\b", text, re.I)
        if match:
            try:
                source = match.group(1) + (f" {match.group(2).upper()}" if match.group(2) else "")
                bill_time = datetime.strptime(source, "%I:%M %p" if match.group(2) else "%H:%M").strftime("%H:%M")
            except ValueError:
                pass

        amount = None
        amount_patterns = [
            r"(?:grand\s*total|total\s*(?:amount|due|payable)?|amount\s*paid|net\s*amount)\s*[:=]?\s*[₹$€£A-Za-z. ]*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            r"(?:₹|\bRs\.?\b)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    amount = Decimal(match.group(1).replace(",", "")).quantize(Decimal("0.01"))
                    break
                except InvalidOperation:
                    continue

        return {
            "provider_name": provider,
            "bill_date": bill_date,
            "bill_time": bill_time,
            "amount": amount,
            "currency": currency or "INR",
            "bill_number": bill_number,
            "payment_mode": payment,
        }

    def run(self, text: str) -> dict:
        return self.local_extract(text)
