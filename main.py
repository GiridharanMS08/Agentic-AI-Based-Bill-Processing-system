from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from agents.final_agent import FinalAgent
from agents.supervisor import SupervisorAgent
from app_config import settings
from db_layer import SessionLocal, database_summary, db_health, sync_categories


def configure_logging() -> logging.Logger:
    log_file = Path(settings.OUTPUT_DIR) / "bill_agent.log"
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("bill_agent")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def process_all(logger: logging.Logger) -> None:
    supervisor = SupervisorAgent(settings, SessionLocal, logger)
    final = FinalAgent(SessionLocal, settings.OUTPUT_DIR)
    input_dir = Path(settings.INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    allowed = {".png", ".jpg", ".jpeg"}
    files = [p for p in sorted(input_dir.iterdir()) if p.is_file() and p.suffix.lower() in allowed]
    files = files[: settings.MAX_FILES_PER_RUN]

    processed = 0
    succeeded = 0
    rejected = 0
    failed = 0

    for path in files:
        processed += 1
        try:
            result = supervisor.run_file(path)
            status = result.get("validation_status", "unknown")
            if result.get("error"):
                rejected += 1
            else:
                succeeded += 1
            logger.info(
                "[Supervisor Agent] file=%s result=%s category=%s bill_id=%s duplicate=%s gemini_calls=%s",
                path.name,
                status,
                result.get("category"),
                result.get("stored_bill_id"),
                result.get("was_duplicate"),
                result.get("gemini_calls", 0),
            )
        except Exception:
            failed += 1
            logger.exception("[Supervisor Agent] file=%s result=failed", path.name)

    reports = final.regenerate_all()
    print(f"Processed={processed} succeeded={succeeded} rejected={rejected} failed={failed}")
    print(f"Monthly reports regenerated={len(reports)}")

    for report in reports:
        print(f"\n=== {report['month']} ===")
        for category in final.CATEGORIES:
            category_data = report["categories"][category]
            print(f"{category}: {category_data['bill_count']} bills | Total {category_data['currency']} {category_data['total_amount']}")
            if category_data["bills"]:
                frame = pd.DataFrame(category_data["bills"])[["date", "time", "provider", "amount"]]
                print(frame.to_string(index=False))

    summary = database_summary()
    logger.info("[Final Agent] database_summary=%s", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Production multi-agent bill processor")
    parser.add_argument("--regenerate-month", help="Regenerate one YYYY-MM report from MySQL only")
    args = parser.parse_args()

    logger = configure_logging()
    if not db_health():
        logger.error("Database connection failed. Check MySQL and config/db_config.env")
        return 2

    sync_categories()
    if args.regenerate_month:
        FinalAgent(SessionLocal, settings.OUTPUT_DIR).report_month(args.regenerate_month)
        print(f"Generated output/{args.regenerate_month}_report.json from MySQL only.")
        return 0

    process_all(logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
