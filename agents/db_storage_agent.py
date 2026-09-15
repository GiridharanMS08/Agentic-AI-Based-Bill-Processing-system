from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


class DBStorageAgent:
    name = "DB Storage Agent"

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def run(self, state):
        db = self.session_factory()
        try:
            extracted = state["extracted"]
            bill_number = extracted.get("bill_number")

            # No file hashing. Dedupe by source file + bill number when both are present.
            # If a bill number is absent, the source file itself is treated as the run identity.
            if bill_number:
                existing = db.execute(
                    text("SELECT bill_id FROM bills WHERE source_file=:source_file AND bill_number=:bill_number LIMIT 1"),
                    {"source_file": state["source_file"], "bill_number": bill_number},
                ).scalar()
            else:
                existing = db.execute(
                    text("SELECT bill_id FROM bills WHERE source_file=:source_file AND bill_number IS NULL LIMIT 1"),
                    {"source_file": state["source_file"]},
                ).scalar()

            if existing:
                return {**state, "stored_bill_id": int(existing), "was_duplicate": True}

            category_id = db.execute(
                text("SELECT category_id FROM categories WHERE name=:name AND is_active=1 LIMIT 1"),
                {"name": state["category"]},
            ).scalar()
            if not category_id:
                raise ValueError(f"Unknown category: {state['category']}")

            params = {
                "category_id": category_id,
                "provider_name": extracted.get("provider_name"),
                "bill_date": extracted.get("bill_date"),
                "bill_time": extracted.get("bill_time"),
                "amount": extracted.get("amount"),
                "currency": extracted.get("currency") or "INR",
                "bill_number": bill_number,
                "payment_mode": extracted.get("payment_mode"),
                "source_file": state["source_file"],
                "ocr_confidence": state["ocr_confidence"],
                "notes": " | ".join(state.get("validation_notes", [])),
            }
            try:
                result = db.execute(
                    text(
                        "INSERT INTO bills(category_id,provider_name,bill_date,bill_time,amount,currency,"
                        "bill_number,payment_mode,source_file,ocr_confidence,notes) "
                        "VALUES(:category_id,:provider_name,:bill_date,:bill_time,:amount,:currency,:bill_number,"
                        ":payment_mode,:source_file,:ocr_confidence,:notes)"
                    ),
                    params,
                )
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = db.execute(
                    text("SELECT bill_id FROM bills WHERE source_file=:source_file ORDER BY bill_id DESC LIMIT 1"),
                    {"source_file": state["source_file"]},
                ).scalar()
                if not existing:
                    raise
                return {**state, "stored_bill_id": int(existing), "was_duplicate": True}

            return {**state, "stored_bill_id": int(result.lastrowid), "was_duplicate": False}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
