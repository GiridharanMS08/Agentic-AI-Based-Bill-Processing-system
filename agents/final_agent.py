from __future__ import annotations

import json
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import text


class FinalAgent:
    CATEGORIES = ["Food", "Medical", "Travel", "Other"]

    def __init__(self, session_factory, output_dir):
        self.session_factory = session_factory
        self.output = Path(output_dir)
        self.output.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _format_bill_time(value) -> str | None:
        """Normalize MySQL TIME values returned by PyMySQL/SQLAlchemy.

        MySQL TIME columns may arrive as datetime.time, datetime.timedelta, or
        string values depending on the driver/dialect configuration.
        """
        if value is None:
            return None
        if isinstance(value, dt_time):
            return value.strftime("%H:%M")
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}"
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            parts = text_value.split(":")
            if len(parts) >= 2:
                return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            return text_value
        return str(value)

    def report_month(self, month_id: str) -> dict:
        db = self.session_factory()
        try:
            rows = db.execute(
                text(
                    "SELECT c.name AS category,b.bill_date,b.bill_time,b.provider_name,b.amount,b.currency,"
                    "b.bill_number,b.payment_mode,b.source_file FROM bills b "
                    "JOIN categories c ON c.category_id=b.category_id "
                    "WHERE DATE_FORMAT(b.bill_date,'%Y-%m')=:month_id "
                    "ORDER BY c.name,b.bill_date,b.bill_time,b.bill_id"
                ),
                {"month_id": month_id},
            ).mappings().all()
        finally:
            db.close()

        report = {
            "month": month_id,
            "categories": {},
            "grand_total": Decimal("0.00"),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

        for category in self.CATEGORIES:
            category_rows = [row for row in rows if row["category"] == category]
            total = sum((Decimal(str(row["amount"] or "0")) for row in category_rows), Decimal("0.00"))
            bills = [
                {
                    "provider": row["provider_name"],
                    "date": row["bill_date"].isoformat() if row["bill_date"] else None,
                    "time": self._format_bill_time(row["bill_time"]),
                    "amount": Decimal(str(row["amount"] or "0.00")),
                    "bill_number": row["bill_number"],
                    "payment_mode": row["payment_mode"],
                    "source_file": row["source_file"],
                }
                for row in category_rows
            ]
            report["categories"][category] = {
                "bill_count": len(bills),
                "total_amount": total.quantize(Decimal("0.01")),
                "currency": category_rows[0]["currency"] if category_rows else "INR",
                "bills": bills,
            }
            report["grand_total"] += total

        json_path = self.output / f"{month_id}_report.json"
        json_path.write_text(json.dumps(report, default=str, indent=2, ensure_ascii=False), encoding="utf-8")
        for category in self.CATEGORIES:
            pd.DataFrame(report["categories"][category]["bills"], columns=["provider", "date", "time", "amount", "bill_number", "payment_mode", "source_file"]).to_csv(
                self.output / f"{month_id}_{category.lower()}_table.csv", index=False
            )
        return report

    def regenerate_all(self):
        db = self.session_factory()
        try:
            months = db.execute(
                text("SELECT DISTINCT DATE_FORMAT(bill_date,'%Y-%m') AS month_id FROM bills WHERE bill_date IS NOT NULL ORDER BY month_id")
            ).scalars().all()
        finally:
            db.close()
        return [self.report_month(month) for month in months]
