USE bill_analyzer;
CREATE OR REPLACE VIEW v_weekly_expense_report AS
SELECT YEARWEEK(b.bill_date,3) iso_week_num, DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY) week_start_date, DATE_ADD(DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY),INTERVAL 6 DAY) week_end_date, c.name category, COUNT(*) bill_count, CAST(SUM(b.amount) AS DECIMAL(14,2)) total_amount, b.currency
FROM bills b JOIN categories c ON c.category_id=b.category_id WHERE b.bill_date IS NOT NULL GROUP BY YEARWEEK(b.bill_date,3),week_start_date,week_end_date,c.name,b.currency
UNION ALL
SELECT YEARWEEK(b.bill_date,3), DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY), DATE_ADD(DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY),INTERVAL 6 DAY), 'Grand Total', COUNT(*), CAST(SUM(b.amount) AS DECIMAL(14,2)), b.currency
FROM bills b WHERE b.bill_date IS NOT NULL GROUP BY YEARWEEK(b.bill_date,3), DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY), DATE_ADD(DATE_SUB(b.bill_date,INTERVAL WEEKDAY(b.bill_date) DAY),INTERVAL 6 DAY), b.currency;

CREATE OR REPLACE VIEW v_monthly_expense_report AS
SELECT DATE_FORMAT(b.bill_date,'%Y-%m') month_id,c.name category,COUNT(*) bill_count,CAST(SUM(b.amount) AS DECIMAL(14,2)) total_amount,b.currency
FROM bills b JOIN categories c ON c.category_id=b.category_id WHERE b.bill_date IS NOT NULL GROUP BY DATE_FORMAT(b.bill_date,'%Y-%m'),c.name,b.currency
UNION ALL
SELECT DATE_FORMAT(b.bill_date,'%Y-%m'),'Grand Total',COUNT(*),CAST(SUM(b.amount) AS DECIMAL(14,2)),b.currency
FROM bills b WHERE b.bill_date IS NOT NULL GROUP BY DATE_FORMAT(b.bill_date,'%Y-%m'),b.currency;
