# Mortgage Overpayment Planner

A local Streamlit app for projecting an existing EUR repayment mortgage with date-aware overpayments.

The app replaces a spreadsheet-style month table with an event ledger. Scheduled payments happen on the 1st of each month, and extra payments can happen on the same day or on any other date.

## Install

This project uses `uv` for Python environment management.

```bash
UV_CACHE_DIR="$PWD/.uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" .tools/bin/uv sync --dev
```

## Run The App

For the easiest option on macOS, double-click `calculator.command` in Finder.

From this folder:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" .tools/bin/uv run streamlit run app.py
```

In Visual Studio Code, open this folder, use the terminal, and run the same command.

## Run Tests

```bash
UV_CACHE_DIR="$PWD/.uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" .tools/bin/uv run pytest
```

## Date-Aware Logic

The default calculation uses daily simple interest:

```text
interest = opening balance * annual rate * days elapsed / 365
```

For each event date, the engine processes items in this order:

1. Interest accrual up to the event date.
2. Scheduled payment.
3. Monthly recurring overpayment.
4. Lump-sum overpayment.
5. Rate-change handling for future accrual.

An overpayment on the 1st of the month is applied after the scheduled payment. An overpayment on the 2nd or later is a separate principal-only event and reduces the balance immediately, which lowers later daily interest.

## Outputs

The app shows:

- Dashboard metrics.
- Chronological transaction ledger.
- Monthly amortisation summary.
- Balance and interest charts.
- Excel workbook download.
- CSV downloads for the ledger and monthly summary.

## Known Limitations

The model excludes fees, property value, equity modelling, and bank offer comparison. Actual lender figures may differ because banks can use different day-count conventions, compounding rules, payment posting rules, and rounding policies.
