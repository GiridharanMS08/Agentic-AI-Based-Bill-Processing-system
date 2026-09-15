# Agentic AI Bill Processor — Browser + MySQL

A local-first multi-agent bill processing application for students. Upload multiple **JPG/JPEG/PNG bill photos** in a browser. RapidOCR runs locally, Gemini corrects the preliminary extraction, validation and categorization follow, then MySQL stores the bill and Python refreshes weekly/monthly/category summaries.

## Browser flow

`Browser upload (multiple photos) -> RapidOCR -> Local Extraction -> Gemini correction -> Validation -> Categorization -> MySQL -> Python Decimal aggregation -> Browser tables + JSON/CSV`

The normal production entry point is `run.bat`. It starts the local FastAPI server and automatically opens the browser. The browser accepts multiple JPG/JPEG/PNG photos in one submission; TXT/PDF/WebP inputs are not accepted.

### Agents

- Supervisor Agent — LangGraph orchestration and retries
- OCR Agent — RapidOCR locally
- Extraction Agent — local rule-based parsing
- Gemini Extraction Agent — every local extraction is sent to Gemini when the API is enabled
- Validation Agent — hard validation gate
- Categorization Agent — config-driven keywords with Gemini fallback for ambiguous cases
- DB Storage Agent — MySQL transaction and source-file dedupe
- Aggregation Agent — Python `Decimal` weekly/monthly summaries
- Final Agent — DB-backed JSON/CSV reports

## First-time setup

1. Install Python 3.11+ and MySQL 8+.
2. Run `run.bat` once.
3. When prompted, edit `config/db_config.env` with your MySQL credentials and Gemini API key.
4. Run `run.bat` again.
5. Your browser opens at `http://127.0.0.1:8000`.

## Browser input

Only these file types are accepted:

- `.jpg`
- `.jpeg`
- `.png`

You can select multiple photos at once. The categorization agent automatically assigns Food, Medical, Travel, or Other based on the bill.

## Reports in browser

After upload the browser displays data queried from MySQL:

- Category Summary
- All Bills
- Weekly Summary
- Monthly Summary

The Final Agent also writes durable JSON and CSV files under `output/`.

## Past month

Run:

`venv\\Scripts\\python.exe main.py --regenerate-month 2026-09`

This reads MySQL only and regenerates the JSON report without OCR.

## Notes on Gemini usage

RapidOCR is local and free. Gemini is used after local extraction to correct the structured fields before validation. Set `GEMINI_ENABLED=false` to run without the API; then validation will use the local extraction only.
