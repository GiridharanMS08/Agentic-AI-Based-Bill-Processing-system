from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


class GeminiAgent:
    name = "Gemini Extraction Agent"

    def __init__(self, settings):
        self.settings = settings
        self.enabled = bool(settings.GEMINI_ENABLED and settings.GEMINI_API_KEY)
        self.log = logging.getLogger("bill_agent.gemini")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if self.enabled else None

    @staticmethod
    def _json_from_text(text_value: str) -> dict[str, Any]:
        text_value = (text_value or "").strip()
        if text_value.startswith("```"):
            text_value = text_value.strip("`")
            if text_value.lstrip().startswith("json"):
                text_value = text_value.lstrip()[4:].strip()
        start, end = text_value.find("{"), text_value.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Gemini did not return a JSON object")
        value = json.loads(text_value[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("Gemini response is not a JSON object")
        return value

    def _call(self, contents: list[Any]) -> dict[str, Any]:
        if not self.enabled or self.client is None:
            raise RuntimeError("Gemini API is not configured")
        last_exc: Exception | None = None
        for attempt in range(1, self.settings.GEMINI_MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.settings.GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                return self._json_from_text(response.text)
            except Exception as exc:  # provider exceptions vary by SDK version
                last_exc = exc
                self.log.warning("Gemini call failed (attempt %s/%s): %s", attempt, self.settings.GEMINI_MAX_RETRIES, exc)
                if attempt < self.settings.GEMINI_MAX_RETRIES:
                    time.sleep(self.settings.GEMINI_RETRY_SECONDS * attempt)
        raise RuntimeError(f"Gemini request failed after retries: {last_exc}")

    def correct_extraction(self, local_data: dict[str, Any], ocr_text: str, file_bytes: bytes, filename: str) -> dict[str, Any]:
        suffix = Path(filename).suffix.lower()
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }.get(suffix)
        prompt = f"""
You are the Bill Extraction Agent. A local OCR engine has already extracted text and a rule-based parser produced a preliminary record.
Correct the record using the document and OCR text. Do not invent missing values. Preserve null for information that is genuinely unavailable.
Return ONLY JSON with exactly these keys:
provider_name, bill_date, bill_time, amount, currency, bill_number, payment_mode
Rules:
- bill_date must be YYYY-MM-DD or null.
- bill_time must be HH:MM (24-hour) or null.
- amount must be a numeric JSON value or null.
- currency should be an ISO-like code such as INR, USD, EUR or null.
- Correct obvious OCR errors when the document supports the correction.
- The total/amount should be the final payable bill amount, not a subtotal or tax, when the document makes that distinction.

PRELIMINARY RECORD:
{json.dumps(local_data, default=str, ensure_ascii=False)}

OCR TEXT:
{ocr_text[:16000]}
""".strip()
        contents: list[Any] = [prompt]
        if mime:
            contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))
        return self._call(contents)

    def validate_correction(self, extracted: dict[str, Any], validation_notes: list[str], ocr_text: str) -> dict[str, Any]:
        prompt = f"""
You are a bill validation agent. Review the extracted bill fields and validation findings.
Return ONLY JSON with the same seven bill fields.
Correct a value only when the OCR/context clearly supports it. Never invent data.

EXTRACTED:
{json.dumps(extracted, default=str, ensure_ascii=False)}

VALIDATION FINDINGS:
{json.dumps(validation_notes, ensure_ascii=False)}

OCR:
{ocr_text[:12000]}
""".strip()
        return self._call([prompt])

    def categorize(self, bill: dict[str, Any], ocr_text: str, categories: list[str]) -> str:
        prompt = f"""
Classify this bill into exactly one category from: {', '.join(categories)}.
Return ONLY JSON: {{"category":"<category>"}}.
Use the provider, bill content, and OCR text. If uncertain choose Other.

BILL:
{json.dumps(bill, default=str, ensure_ascii=False)}
OCR:
{ocr_text[:8000]}
""".strip()
        data = self._call([prompt])
        value = str(data.get("category", "Other"))
        return value if value in categories else "Other"
