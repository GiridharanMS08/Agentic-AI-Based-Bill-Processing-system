from decimal import Decimal

from agents.extraction_agent import ExtractionAgent
from agents.validation_agent import ValidationAgent


def test_local_extraction():
    text = """SARAVANA BHAVAN\nBill No: SB-10234\nDate: 15/09/2026\nTime: 01:25 PM\nTotal: Rs 450.00\nPayment: UPI"""
    e = ExtractionAgent.local_extract(text)
    assert e["provider_name"] == "SARAVANA BHAVAN"
    assert e["bill_date"] == "2026-09-15"
    assert e["bill_time"] == "13:25"
    assert e["amount"] == Decimal("450.00")
    assert e["bill_number"] == "SB-10234"
    assert e["payment_mode"] == "UPI"


def test_validation_accepts_clean_record():
    e = {
        "provider_name": "Test Store",
        "bill_date": "2026-09-10",
        "bill_time": "10:20",
        "amount": Decimal("100.00"),
        "currency": "INR",
        "bill_number": "B-1",
        "payment_mode": "UPI",
    }
    status, notes = ValidationAgent().run(e, Decimal("95"))
    assert status == "valid"
    assert notes == ["All validation checks passed."]


def test_format_bill_time_handles_mysql_timedelta():
    from datetime import timedelta
    from agents.final_agent import FinalAgent

    assert FinalAgent._format_bill_time(timedelta(hours=13, minutes=25)) == "13:25"


def test_format_bill_time_handles_datetime_time():
    from datetime import time
    from agents.final_agent import FinalAgent

    assert FinalAgent._format_bill_time(time(9, 7)) == "09:07"
