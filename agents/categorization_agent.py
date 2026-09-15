from __future__ import annotations

import json
from pathlib import Path


class CategorizationAgent:
    name = "Categorization Agent"

    def __init__(self, path: str, gemini=None):
        self.categories = json.loads(Path(path).read_text(encoding="utf-8"))
        self.gemini = gemini

    def run(self, extracted: dict, text: str) -> str:
        haystack = (
            " ".join(str(extracted.get(key) or "") for key in ("provider_name", "bill_number", "payment_mode"))
            + " " + text
        ).lower()
        scores = {
            category: sum(1 for keyword in keywords if keyword.lower() in haystack)
            for category, keywords in self.categories.items()
            if category != "Other"
        }
        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best
        if self.gemini and self.gemini.enabled:
            try:
                return self.gemini.categorize(extracted, text, list(self.categories))
            except Exception:
                pass
        return "Other"
