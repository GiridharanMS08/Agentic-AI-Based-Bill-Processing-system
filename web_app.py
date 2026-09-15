from __future__ import annotations

import html
import logging
import threading
import time
import webbrowser
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from agents.final_agent import FinalAgent
from agents.supervisor import SupervisorAgent
from app_config import settings
from db_layer import SessionLocal, db_health, sync_categories

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_MB = 10

app = FastAPI(title="Agentic AI Bill Processor", version="1.0.0")


def logger() -> logging.Logger:
    path = Path(settings.OUTPUT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("bill_agent.web")
    if log.handlers:
        return log
    log.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    fh = logging.FileHandler(path / "bill_agent_web.log", encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(sh)
    log.addHandler(fh)
    return log


LOG = logger()


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def money(value: Decimal | str | int | float | None) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):.2f}"


def query_dashboard() -> dict:
    db = SessionLocal()
    try:
        bills = db.execute(
            text(
                "SELECT b.bill_id,b.bill_date,b.bill_time,b.provider_name,b.amount,b.currency,"
                "b.bill_number,b.payment_mode,b.source_file,c.name AS category "
                "FROM bills b JOIN categories c ON c.category_id=b.category_id "
                "ORDER BY b.bill_date DESC,b.bill_id DESC"
            )
        ).mappings().all()

        categories = db.execute(
            text(
                "SELECT c.name AS category, COUNT(b.bill_id) AS bill_count, "
                "COALESCE(SUM(b.amount),0) AS total_amount "
                "FROM categories c LEFT JOIN bills b ON b.category_id=c.category_id "
                "WHERE c.is_active=1 GROUP BY c.category_id,c.name ORDER BY c.category_id"
            )
        ).mappings().all()

        weekly = db.execute(
            text(
                "SELECT w.week_id,w.week_start_date,w.week_end_date,c.name AS category,"
                "w.bill_count,w.total_amount,w.currency,w.generated_at "
                "FROM weekly_summary w JOIN categories c ON c.category_id=w.category_id "
                "ORDER BY w.week_id DESC,c.category_id"
            )
        ).mappings().all()

        monthly = db.execute(
            text(
                "SELECT m.month_id,c.name AS category,m.bill_count,m.total_amount,m.currency,m.generated_at "
                "FROM monthly_summary m JOIN categories c ON c.category_id=m.category_id "
                "ORDER BY m.month_id DESC,c.category_id"
            )
        ).mappings().all()

        db_summary = db.execute(
            text(
                "SELECT COUNT(*) AS bill_count,COALESCE(SUM(amount),0) AS total_amount,"
                "MIN(bill_date) AS min_date,MAX(bill_date) AS max_date FROM bills"
            )
        ).mappings().one()
        return {
            "bills": bills,
            "categories": categories,
            "weekly": weekly,
            "monthly": monthly,
            "db_summary": db_summary,
        }
    finally:
        db.close()


def render_table(headers: Iterable[str], rows: Iterable[Iterable[object]], empty: str = "No data yet") -> str:
    rows = list(rows)
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    if not rows:
        body = f'<tr><td colspan="{len(list(headers))}" class="empty">{esc(empty)}</td></tr>'
    else:
        body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'


def format_time(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%H:%M")
        except Exception:
            pass
    return str(v)[:5]


def _date_text(value) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _currency_totals(rows):
    totals = {}
    for row in rows:
        cur = row.get("currency") or "INR"
        totals[cur] = totals.get(cur, Decimal("0.00")) + Decimal(str(row.get("total_amount") or "0.00"))
    return totals


def dashboard_html(message: str | None = None) -> str:
    data = query_dashboard()
    s = data["db_summary"]
    message_html = f'<div class="notice">{esc(message)}</div>' if message else ""

    # Category Summary: always show every active category, including zero-bill categories.
    category_cards = []
    for r in data["categories"]:
        category_cards.append(
            f'''<div class="category-card">
                <div class="category-name">{esc(r["category"])}</div>
                <div class="category-count">{esc(r["bill_count"])}</div>
                <div class="category-meta">bills</div>
                <div class="category-total">{esc(money(r["total_amount"]))}</div>
                <div class="category-meta">total amount</div>
            </div>'''
        )

    bills_rows = []
    for r in data["bills"]:
        bills_rows.append((
            esc(_date_text(r["bill_date"])),
            esc(format_time(r["bill_time"])),
            esc(r["category"]),
            esc(r["provider_name"]),
            esc(money(r["amount"])),
            esc(r["currency"]),
            esc(r["payment_mode"]),
            esc(r["source_file"]),
        ))

    # Weekly/monthly: hide zero-count rows and group by period behind left disclosure arrows.
    weekly_groups = {}
    for r in data["weekly"]:
        if int(r["bill_count"] or 0) > 0:
            weekly_groups.setdefault(r["week_id"], []).append(r)

    monthly_groups = {}
    for r in data["monthly"]:
        if int(r["bill_count"] or 0) > 0:
            monthly_groups.setdefault(r["month_id"], []).append(r)

    def render_period_groups(groups, weekly=False):
        if not groups:
            return '<div class="empty-panel">No periods with bills yet.</div>'

        blocks = []
        for period, rows in groups.items():
            total_count = sum(int(r["bill_count"] or 0) for r in rows)
            currencies = _currency_totals(rows)
            totals_text = " · ".join(
                f"{cur} {money(amount)}" for cur, amount in currencies.items()
            )
            if weekly:
                start = _date_text(rows[0]["week_start_date"])
                end = _date_text(rows[0]["week_end_date"])
                heading = f"{period} · {start} → {end}"
            else:
                heading = period

            detail_rows = []
            for r in rows:
                detail_rows.append(
                    f'''<tr>
                        <td>{esc(r["category"])}</td>
                        <td class="num">{esc(r["bill_count"])}</td>
                        <td class="num">{esc(money(r["total_amount"]))}</td>
                        <td>{esc(r["currency"])}</td>
                    </tr>'''
                )

            blocks.append(
                f'''<details class="period-details">
                    <summary>
                        <span class="period-title">{esc(heading)}</span>
                        <span class="period-stats">{total_count} bill(s) · {esc(totals_text)}</span>
                    </summary>
                    <div class="period-content">
                        <table class="compact-table">
                            <thead><tr><th>Category</th><th>Bills</th><th>Total Amount</th><th>Currency</th></tr></thead>
                            <tbody>{"".join(detail_rows)}</tbody>
                        </table>
                    </div>
                </details>'''
            )
        return "".join(blocks)

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agentic AI Bill Processor</title>
<style>
:root{{--bg:#f5f7fb;--card:#fff;--text:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#2563eb;--success:#166534}}
*{{box-sizing:border-box}}
body{{font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text);margin:0}}
.wrap{{max-width:1400px;margin:0 auto;padding:28px}}
.hero{{background:#0f172a;color:#fff;border-radius:18px;padding:26px 30px;margin-bottom:22px}}
.hero h1{{margin:0 0 8px;font-size:30px}} .hero p{{margin:0;color:#cbd5e1}}
.upload{{background:var(--card);border:2px dashed #94a3b8;border-radius:18px;padding:22px;margin-bottom:22px}}
input[type=file]{{display:block;margin:12px 0;font-size:16px;max-width:100%}}
button{{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:12px 20px;font-size:15px;cursor:pointer}}
button:hover{{background:#1d4ed8}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}}
.card{{background:var(--card);border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(15,23,42,.06)}}
.stat{{font-size:28px;font-weight:700;margin-top:6px}}
section{{background:var(--card);border-radius:14px;padding:20px;margin:18px 0;overflow:auto}}
h2{{margin-top:0;font-size:21px}}
table{{width:100%;border-collapse:collapse;min-width:700px}}
th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}}
th{{background:#f8fafc;position:sticky;top:0}}
.empty{{text-align:center;color:var(--muted)}}
.notice{{background:#dcfce7;border:1px solid #86efac;color:var(--success);padding:12px 14px;border-radius:10px;margin-bottom:16px}}
.small{{color:var(--muted);font-size:13px}} .required{{color:#b91c1c}}
.category-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:10px;min-width:900px}}
.category-card{{border:1px solid var(--line);border-radius:14px;padding:18px;background:linear-gradient(180deg,#fff,#f8fafc)}}
.category-name{{font-size:16px;font-weight:700;margin-bottom:10px}}
.category-count{{font-size:30px;font-weight:800;line-height:1}}
.category-total{{font-size:20px;font-weight:700;margin-top:14px}}
.category-meta{{font-size:12px;color:var(--muted);margin-top:4px}}
.period-details{{border:1px solid var(--line);border-radius:12px;margin:10px 0;overflow:hidden;background:#fff}}
.period-details summary{{list-style:none;cursor:pointer;padding:15px 18px;display:flex;align-items:center;gap:14px;background:#f8fafc;font-weight:600}}
.period-details summary::-webkit-details-marker{{display:none}}
.period-details summary::before{{content:'›';font-size:24px;line-height:1;transform:rotate(0deg);transition:transform .15s ease;color:var(--accent)}}
.period-details[open] summary::before{{transform:rotate(90deg)}}
.period-title{{flex:1}}
.period-stats{{font-size:13px;color:var(--muted);font-weight:500;text-align:right}}
.period-content{{padding:0 14px 14px}}
.compact-table{{min-width:560px;margin-top:12px}}
.compact-table th,.compact-table td{{padding:9px 10px}}
.num{{text-align:right}}
.empty-panel{{padding:16px;border:1px dashed #cbd5e1;border-radius:10px;color:var(--muted)}}
@media(max-width:1100px){{.category-grid{{grid-template-columns:repeat(2,1fr);min-width:0}}}}
@media(max-width:900px){{.stats{{grid-template-columns:1fr}}.wrap{{padding:14px}}.category-grid{{grid-template-columns:1fr;min-width:0}}.period-details summary{{align-items:flex-start;flex-wrap:wrap}}.period-stats{{width:100%;text-align:left;padding-left:38px}}}}
</style></head><body><div class="wrap">
<div class="hero"><h1>Agentic AI Bill Processor</h1><p>Upload JPG/JPEG/PNG bill photos. Multiple photos can be processed together, categorized automatically, stored in MySQL, and summarized.</p></div>
{message_html}
<div class="upload"><h2>Upload Bill Photos</h2><form action="/upload" method="post" enctype="multipart/form-data">
<input type="file" name="files" accept=".jpg,.jpeg,.png,image/jpeg,image/png" multiple required>
<div class="small"><span class="required">Photos only:</span> JPG, JPEG, PNG. Multiple bills from different categories can be selected at once.</div>
<br><button type="submit">Process Bills</button></form></div>
<div class="stats"><div class="card">Total Bills<div class="stat">{esc(s['bill_count'])}</div></div><div class="card">Total Amount<div class="stat">{esc(money(s['total_amount']))}</div><div class="small">Database total</div></div><div class="card">Date Range<div class="stat" style="font-size:18px">{esc(s['min_date'] or '—')} → {esc(s['max_date'] or '—')}</div></div></div>
<section><h2>Category Summary</h2><div class="category-grid">{"".join(category_cards)}</div></section>
<section><h2>All Bills</h2>{render_table(['Date','Time','Category','Provider','Amount','Currency','Payment','Source File'], bills_rows)}</section>
<section><h2>Weekly Summary</h2>{render_period_groups(weekly_groups, weekly=True)}</section>
<section><h2>Monthly Summary</h2>{render_period_groups(monthly_groups, weekly=False)}</section>
</div></body></html>"""
@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    if not db_health():
        return HTMLResponse("<h2>MySQL connection failed. Check config/db_config.env and MySQL.</h2>", status_code=503)
    sync_categories()
    return HTMLResponse(dashboard_html())


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    if not files:
        return HTMLResponse(dashboard_html("No files selected."), status_code=400)

    Path(settings.INPUT_DIR).mkdir(parents=True, exist_ok=True)
    supervisor = SupervisorAgent(settings, SessionLocal, LOG)
    processed = 0
    succeeded = 0
    rejected = 0
    failed = 0
    messages = []

    for upload in files:
        original_name = Path(upload.filename or "").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            rejected += 1
            messages.append(f"{original_name}: rejected — photos only (JPG/JPEG/PNG)")
            continue
        content = await upload.read()
        if not content:
            rejected += 1
            messages.append(f"{original_name}: rejected — empty file")
            continue
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            rejected += 1
            messages.append(f"{original_name}: rejected — file exceeds {MAX_UPLOAD_MB} MB")
            continue

        destination = Path(settings.INPUT_DIR) / original_name
        # Keep the user-visible source filename stable for DB reporting/deduplication.
        destination.write_bytes(content)
        processed += 1
        try:
            result = supervisor.run_file(destination)
            if result.get("error"):
                rejected += 1
                messages.append(f"{original_name}: rejected — {result.get('error')}")
            else:
                succeeded += 1
                category = result.get("category", "Other")
                bill_id = result.get("stored_bill_id")
                if result.get("was_duplicate"):
                    messages.append(f"{original_name}: already stored (bill #{bill_id}, {category})")
                else:
                    messages.append(f"{original_name}: stored as {category} (bill #{bill_id})")
        except Exception as exc:
            failed += 1
            LOG.exception("Upload processing failed for %s", original_name)
            messages.append(f"{original_name}: processing failed — {exc}")

    # Regenerate durable JSON/CSV reports from the database after the batch.
    FinalAgent(SessionLocal, settings.OUTPUT_DIR).regenerate_all()
    summary = f"Processed {processed} photo(s): {succeeded} stored/duplicate, {rejected} rejected, {failed} failed. " + " | ".join(messages[:12])
    return HTMLResponse(dashboard_html(summary))


@app.get("/health")
def health() -> dict:
    return {"status": "ok" if db_health() else "degraded", "mysql": db_health()}


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000/")


if __name__ == "__main__":
    import uvicorn

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=False, access_log=True)
