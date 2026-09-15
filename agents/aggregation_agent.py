from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import text


class AggregationAgent:
    name = 'Aggregation Agent'

    def __init__(self, SF):
        self.SF = SF

    @staticmethod
    def _week_bounds(d: date):
        start = d - timedelta(days=d.weekday())
        return start, start + timedelta(days=6)

    def _refresh_month(self, db, month_id: str):
        bills = db.execute(text("""
            SELECT category_id, amount, currency
            FROM bills
            WHERE bill_date IS NOT NULL
              AND DATE_FORMAT(bill_date, '%Y-%m') = :month_id
        """), {'month_id': month_id}).mappings().all()
        categories = db.execute(text("SELECT category_id FROM categories WHERE is_active=1 ORDER BY category_id")).scalars().all()
        # Intentionally aggregate in local Python using Decimal.
        totals = {int(cid): {'count': 0, 'amount': Decimal('0.00'), 'currency': 'INR'} for cid in categories}
        for r in bills:
            cid = int(r['category_id'])
            if cid not in totals:
                totals[cid] = {'count': 0, 'amount': Decimal('0.00'), 'currency': 'INR'}
            totals[cid]['count'] += 1
            totals[cid]['amount'] += Decimal(str(r['amount'] or 0))
            totals[cid]['currency'] = r['currency'] or totals[cid]['currency']
        db.execute(text('DELETE FROM monthly_summary WHERE month_id=:m'), {'m': month_id})
        for cid, v in totals.items():
            db.execute(text("""
                INSERT INTO monthly_summary(month_id,category_id,bill_count,total_amount,currency,generated_at)
                VALUES(:m,:c,:n,:a,:cur,NOW())
            """), {'m': month_id, 'c': cid, 'n': v['count'], 'a': v['amount'].quantize(Decimal('0.01')), 'cur': v['currency']})

    def _refresh_week(self, db, week_id: str):
        year, week = week_id.split('-W')
        try:
            anchor = date.fromisocalendar(int(year), int(week), 1)
        except ValueError:
            return
        start, end = self._week_bounds(anchor)
        bills = db.execute(text("""
            SELECT category_id, amount, currency
            FROM bills
            WHERE bill_date IS NOT NULL
              AND YEARWEEK(bill_date,3) = :iso_week
        """), {'iso_week': int(year) * 100 + int(week)}).mappings().all()
        categories = db.execute(text("SELECT category_id FROM categories WHERE is_active=1 ORDER BY category_id")).scalars().all()
        # Intentionally aggregate in local Python using Decimal.
        totals = {int(cid): {'count': 0, 'amount': Decimal('0.00'), 'currency': 'INR'} for cid in categories}
        for r in bills:
            cid = int(r['category_id'])
            if cid not in totals:
                totals[cid] = {'count': 0, 'amount': Decimal('0.00'), 'currency': 'INR'}
            totals[cid]['count'] += 1
            totals[cid]['amount'] += Decimal(str(r['amount'] or 0))
            totals[cid]['currency'] = r['currency'] or totals[cid]['currency']
        db.execute(text('DELETE FROM weekly_summary WHERE week_id=:w'), {'w': week_id})
        for cid, v in totals.items():
            db.execute(text("""
                INSERT INTO weekly_summary(week_id,week_start_date,week_end_date,category_id,bill_count,total_amount,currency,generated_at)
                VALUES(:w,:ws,:we,:c,:n,:a,:cur,NOW())
            """), {
                'w': week_id, 'ws': start, 'we': end, 'c': cid,
                'n': v['count'], 'a': v['amount'].quantize(Decimal('0.01')), 'cur': v['currency']
            })

    def run(self, s):
        bill_date = s['extracted'].get('bill_date')
        if not bill_date:
            s['affected_weeks'] = []
            s['affected_months'] = []
            return s
        d = date.fromisoformat(str(bill_date))
        iso = d.isocalendar()
        week_id = f'{iso.year}-W{iso.week:02d}'
        month_id = d.strftime('%Y-%m')
        db = self.SF()
        try:
            self._refresh_week(db, week_id)
            self._refresh_month(db, month_id)
            db.commit()
            s['affected_weeks'] = [week_id]
            s['affected_months'] = [month_id]
            return s
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
