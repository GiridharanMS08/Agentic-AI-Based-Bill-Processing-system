DROP PROCEDURE IF EXISTS sp_refresh_weekly_summary;
DROP PROCEDURE IF EXISTS sp_refresh_monthly_summary;

CREATE PROCEDURE sp_refresh_weekly_summary(IN p_week_id VARCHAR(8))
BEGIN
  DELETE FROM weekly_summary WHERE week_id=p_week_id;

  INSERT INTO weekly_summary(
    week_id,
    week_start_date,
    week_end_date,
    category_id,
    bill_count,
    total_amount,
    currency,
    generated_at
  )
  SELECT
    p_week_id,
    MIN(DATE_SUB(bill_date,INTERVAL WEEKDAY(bill_date) DAY)),
    MAX(DATE_ADD(DATE_SUB(bill_date,INTERVAL WEEKDAY(bill_date) DAY),INTERVAL 6 DAY)),
    category_id,
    COUNT(*),
    CAST(SUM(amount) AS DECIMAL(14,2)),
    currency,
    NOW()
  FROM bills
  WHERE bill_date IS NOT NULL
    AND YEARWEEK(bill_date,3)=CAST(REPLACE(p_week_id,'-W','') AS UNSIGNED)
  GROUP BY category_id, currency;
END;

CREATE PROCEDURE sp_refresh_monthly_summary(IN p_month_id CHAR(7))
BEGIN
  DELETE FROM monthly_summary WHERE month_id=p_month_id;

  INSERT INTO monthly_summary(
    month_id,
    category_id,
    bill_count,
    total_amount,
    currency,
    generated_at
  )
  SELECT
    p_month_id,
    category_id,
    COUNT(*),
    CAST(SUM(amount) AS DECIMAL(14,2)),
    currency,
    NOW()
  FROM bills
  WHERE bill_date IS NOT NULL
    AND DATE_FORMAT(bill_date,'%Y-%m')=p_month_id
  GROUP BY category_id, currency;
END;
