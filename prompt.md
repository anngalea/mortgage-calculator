# Codex Prompt: Build a Date-Aware Mortgage Overpayment Planner in Streamlit

Use this prompt in Codex to create a complete Python/Streamlit project.

---

## Role and Goal

You are building a personal mortgage management app for an existing EUR repayment mortgage. The app must replace a fragile Excel-based model with a reliable, testable Python calculation engine and a Streamlit user interface.

The main reason for using Python is that the mortgage calculation is date-aware and event-based. Scheduled mortgage payments are due on the 1st of every month. Extra overpayments may happen on the same day or on any other day. The app must treat these cases differently and must not rely on a static month-by-month amortisation table.

The finished project should be runnable locally in Visual Studio Code with:

```bash
streamlit run app.py
```

The app should let the user enter mortgage details, future interest-rate assumptions, monthly overpayment assumptions, and dated lump-sum overpayments. It should calculate a chronological transaction ledger, dashboard results, charts, and downloadable Excel/CSV outputs.

---

## Key Mortgage Facts to Preload

Preload the app with the following default assumptions, while allowing the user to edit them in the interface.

### Original mortgage structure

- Currency: EUR
- Mortgage type: repayment mortgage, capital plus interest
- Loan 1 original amount: €297,000
- Loan 2 original amount: €18,800
- Combined original mortgage amount: €315,800
- Original start date: 1 November 2024
- Original term: 33 years total
- Initial interest rate: 1.00% p.a. for the first 4 years
- Later interest rate: 2.80% p.a. for the remaining 29 years

### Current working model assumptions

- Current outstanding balance: €302,068
- Current monthly payment: €938
- Actual next scheduled payment date: 1 June 2026
- Scheduled payment day: 1st day of every month
- Inflation rate: optional; default to 0.00%
- Fee modelling: excluded
- Equity/property value modelling: excluded
- Bank offer comparison: excluded

---

## Critical Domain Rule: Date-Aware Payments

The app must model transaction dates correctly.

### Scheduled monthly payment

The scheduled payment is due on the 1st of each month.

On a scheduled payment date:

1. Calculate interest accrued since the previous event date or previous scheduled payment date, depending on the chosen interest method.
2. Apply the scheduled monthly payment first to interest due.
3. Apply the remaining part of the scheduled payment to principal.
4. If the scheduled payment exceeds the remaining balance plus accrued interest, cap the final payment so the balance does not go below zero.

### Extra overpayment on the 1st of the month

If an extra overpayment is made on the same date as a scheduled monthly payment:

1. Process the scheduled payment first.
2. The scheduled payment settles the interest due first.
3. Then apply the extra overpayment entirely to principal.

This should be represented clearly in the transaction ledger, either as two events on the same date or as one row with separate columns for scheduled payment and extra principal.

### Extra overpayment after the 1st of the month

If an extra overpayment is made on any date after the scheduled monthly payment date, such as 2 June 2026:

1. Treat it as a separate principal-only payment on that date.
2. It should reduce the balance immediately.
3. It should reduce the interest charged at the next scheduled payment because interest accrues on a lower balance after the overpayment date.

### Multiple events on the same date

If there are multiple events on the same date, process them in this order:

1. Interest accrual up to the event date, if needed.
2. Scheduled payment.
3. Monthly recurring overpayment attached to the scheduled payment, if configured.
4. Lump-sum overpayment.
5. Rate-change event, only for future accruals, unless the effective date is explicitly intended to apply from the beginning of that day.

Document the exact ordering in code comments and in the user-facing help text.

---

## Interest Calculation Approach

Implement the engine so that the interest calculation approach is explicit and configurable.

Default approach:

- Use daily simple interest between events.
- Annual interest rate divided by 365.
- Interest for a period = opening balance × annual rate × days elapsed / 365.
- Round displayed values to 2 decimal places, but keep internal calculations at full precision until final outputs.

Also support a simpler monthly approximation mode:

- Monthly interest = opening balance × annual rate / 12.
- Use this mode only if selected by the user.

The app should default to daily interest because the user's overpayment timing question depends on whether overpayments are made on 1 June or 2 June.

Add a visible warning that actual bank calculations may differ because lenders can use their own day-count conventions, compounding conventions, payment posting rules, or rounding rules.

---

## Method A: Recalculate Payment at Interest Rate Changes

The model should assume Method A: when an interest rate changes, the mortgage payment is recalculated based on:

- Remaining balance at the rate-change date
- Remaining term
- New interest rate

However, the user also provided a current monthly payment of €938. The app should support both of these behaviours:

1. **Use current payment until next rate reset** — default.
2. **Recalculate payment immediately** using remaining balance, rate, and remaining term.

When a future rate change occurs, recalculate the scheduled monthly payment unless the user disables this option.

The recalculated payment formula for a repayment mortgage should be implemented carefully:

```text
payment = balance * monthly_rate / (1 - (1 + monthly_rate) ** -remaining_months)
```

If the monthly rate is 0, use:

```text
payment = balance / remaining_months
```

---

## Required Project Structure

Create the following project structure:

```text
mortgage-planner/
├── app.py
├── mortgage_engine.py
├── models.py
├── exports.py
├── sample_data.py
├── tests/
│   ├── test_engine_basic.py
│   ├── test_date_aware_overpayments.py
│   ├── test_rate_changes.py
│   └── test_exports.py
├── requirements.txt
├── README.md
└── .gitignore
```

### `app.py`

Streamlit interface.

Must include:

- Page title and explanation.
- Sidebar or setup section for core mortgage inputs.
- Editable interest-rate schedule.
- Editable lump-sum overpayment table.
- Monthly recurring overpayment input.
- Scenario controls.
- Dashboard metrics.
- Transaction ledger table.
- Monthly summary/amortisation table.
- Charts.
- Download buttons for Excel and CSV.

Use `st.data_editor` for editable tables where appropriate.

### `mortgage_engine.py`

Pure calculation engine with no Streamlit imports.

Must include:

- Main projection function.
- Interest accrual function.
- Payment recalculation function.
- Event ordering logic.
- Date handling helpers.
- Validation logic.

The engine must return Pandas DataFrames or typed objects that the UI and export functions consume.

### `models.py`

Typed data structures.

Use dataclasses or Pydantic. Dataclasses are acceptable and keep dependencies simpler.

Suggested structures:

- `MortgageInput`
- `RatePeriod`
- `Overpayment`
- `ProjectionSettings`
- `LedgerEntry`
- `ProjectionResult`

### `exports.py`

Export functions.

Must support:

- Excel export using `openpyxl` or Pandas ExcelWriter.
- CSV export for transaction ledger.
- CSV export for monthly summary.

Excel output should include at least:

- Dashboard Summary
- Inputs
- Interest Rate Schedule
- Overpayments
- Transaction Ledger
- Monthly Amortisation Summary
- Notes and Warnings

### `sample_data.py`

Preloaded default data based on the user's mortgage facts above.

### `tests/`

Pytest suite for the calculation engine.

Tests are essential. Do not skip them.

---

## Streamlit UI Requirements

Use a simple, clean, non-technical interface.

### Page 1 or Section 1: Mortgage Setup

Fields:

- Original mortgage amount
- Mortgage start date
- Original term in years
- Current outstanding balance
- Current monthly payment
- Next scheduled payment date
- Payment day of month, default and locked to 1 unless advanced mode is enabled
- Current interest rate
- Optional inflation rate, default 0.00%
- Interest calculation mode: daily or monthly approximation
- Payment recalculation mode:
  - Use current payment until next rate reset
  - Recalculate immediately

### Page 2 or Section 2: Interest Rate Schedule

Editable table:

| Effective Date | Annual Rate % | Notes |
|---|---:|---|
| 2024-11-01 | 1.00 | Initial rate |
| 2028-11-01 | 2.80 | Post-initial-rate assumption |

Validation:

- Dates must be valid.
- Rates must be non-negative.
- Schedule must be sorted chronologically or automatically sorted.
- Warn if no rate exists on or before the next payment date.

### Page 3 or Section 3: Overpayment Planner

Inputs:

- Monthly recurring overpayment amount.
- Start date for recurring overpayment.
- Optional end date for recurring overpayment.
- Editable lump-sum table.

Lump-sum table columns:

| Date | Amount | Description |
|---|---:|---|

Validation:

- Dates cannot be before the next payment date unless user explicitly chooses to include historical events.
- Amounts must be positive.
- Warn when an overpayment is entered on the 1st of the month, explaining that it will be processed after the scheduled payment but on the same date.
- Warn when an overpayment is entered on the 2nd or later, explaining it is treated as a principal-only event on that date.

### Page 4 or Section 4: Dashboard

Show metrics:

- Starting balance used in projection.
- Next scheduled payment date.
- Current scheduled monthly payment.
- Projected payoff date.
- Months remaining.
- Total scheduled payments remaining.
- Total extra overpayments.
- Total interest from projection start.
- Total amount paid from projection start.
- Interest saved versus baseline with no overpayments.
- Months saved versus baseline with no overpayments.
- Balance at initial fixed-rate expiry, if applicable.

### Page 5 or Section 5: Ledger and Amortisation

Show two tables:

#### Transaction Ledger

Chronological event-level table:

| Date | Event Type | Opening Balance | Rate % | Days Since Prior Event | Interest Accrued | Scheduled Payment | Scheduled Principal | Scheduled Interest | Extra Principal | Closing Balance | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|

#### Monthly Summary

Month-level table:

| Month | Opening Balance | Interest | Scheduled Payments | Extra Principal | Total Paid | Principal Reduction | Closing Balance |
|---|---:|---:|---:|---:|---:|---:|---:|

Important: dashboard outputs and monthly summary must be derived from the same transaction ledger, not from separate logic.

### Page 6 or Section 6: Charts

Include charts for:

- Outstanding balance over time.
- Interest paid over time.
- Principal vs interest by month.
- Baseline vs selected overpayment scenario.

Use Plotly or Streamlit-native charts.

---

## Required Calculation Behaviour

### Baseline and selected scenario

The app must always calculate two projections:

1. Baseline: no overpayments.
2. Selected scenario: monthly and lump-sum overpayments included.

Dashboard savings are calculated as:

```text
interest_saved = baseline_total_interest - scenario_total_interest
months_saved = baseline_months_to_payoff - scenario_months_to_payoff
```

### Projection termination

Projection ends when:

- Closing balance reaches zero, or
- A safety cap is reached.

Use a maximum projection horizon of 60 years from the projection start to prevent infinite loops. If the mortgage is not paid off by then, return a warning.

### Negative balance prevention

Never allow the balance to go below zero.

For the final event:

- Reduce the scheduled payment or overpayment as needed.
- Mark the row as final payoff.
- Closing balance must be exactly zero or within a very small tolerance treated as zero.

### Rounding

Use full precision internally.

Round only for display and export.

Add tests for rounding edge cases.

---

## Validation and Warnings

The app should warn the user when:

- Current balance is missing or zero.
- Current monthly payment is too low to cover interest.
- No valid interest rate applies to the projection start date.
- Interest-rate schedule is empty.
- Overpayment dates are before the next payment date.
- Overpayment amount is greater than the outstanding balance.
- The mortgage does not pay off within the projection horizon.
- The final payment differs significantly from the regular payment.
- The model result may not match the lender due to bank-specific rounding or posting rules.

---

## Test Cases to Implement

Use pytest. The tests must run with:

```bash
pytest
```

### Test 1: No overpayments

Input:

- Starting balance: 302,068
- Current payment: 938
- Next payment date: 2026-06-01
- Rate: 1.00%
- No overpayments

Expected:

- Ledger starts on 2026-06-01.
- First event is a scheduled payment.
- Closing balance is less than opening balance.
- Total interest is positive.
- No negative balances.

### Test 2: Overpayment on payment date

Input:

- Same as above.
- Lump-sum overpayment: €5,000 on 2026-06-01.

Expected:

- Scheduled payment is processed first.
- Extra €5,000 is applied to principal.
- Closing balance after 2026-06-01 is approximately baseline closing balance minus €5,000.
- Interest for that scheduled date is not avoided by the same-day overpayment.

### Test 3: Overpayment on next day

Input:

- Same as above.
- Lump-sum overpayment: €5,000 on 2026-06-02.

Expected:

- 2026-06-01 scheduled payment is processed normally.
- 2026-06-02 event applies €5,000 to principal.
- July interest is lower than it would be without the 2 June overpayment.

### Test 4: Compare 1 June vs 2 June overpayment

Input:

- Scenario A: €5,000 overpayment on 2026-06-01.
- Scenario B: €5,000 overpayment on 2026-06-02.

Expected:

- The ledger should show different event timing.
- The balances immediately after all June events may be similar, but accrued interest for later periods should reflect the exact dates.
- The app must not merge both cases into an identical monthly-only treatment unless monthly approximation mode is selected.

### Test 5: Rate change

Input:

- Rate changes from 1.00% to 2.80% on 2028-11-01.

Expected:

- Rate applied before the effective date is 1.00%.
- Rate applied on and after the effective date is 2.80%.
- Scheduled payment is recalculated at the rate change if recalculation mode is enabled.

### Test 6: Export

Expected:

- Excel export creates a workbook in memory.
- Workbook contains Dashboard Summary, Transaction Ledger, and Monthly Summary sheets.
- CSV export returns non-empty data.

---

## README Requirements

Create a `README.md` explaining:

1. What the app does.
2. How to install Python dependencies.
3. How to run in Visual Studio Code.
4. How to run tests.
5. How the date-aware overpayment logic works.
6. Known limitations.
7. How to export results.

Include commands:

```bash
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run app:

```bash
streamlit run app.py
```

Run tests:

```bash
pytest
```

---

## Dependencies

Use the following dependencies unless there is a strong reason to change them:

```text
streamlit
pandas
numpy
python-dateutil
openpyxl
plotly
pytest
```

Avoid unnecessary heavy dependencies.

---

## Coding Standards

- Keep calculation logic separate from UI logic.
- No Streamlit imports in `mortgage_engine.py`.
- Use clear function names and type hints.
- Use docstrings for important functions.
- Include inline comments for date-aware payment ordering.
- Avoid hard-coded magic numbers except documented defaults.
- Prefer deterministic functions for testability.
- Make the app understandable for a non-expert mortgage holder.

---

## Acceptance Criteria

The task is complete when:

1. `streamlit run app.py` launches a usable mortgage planner.
2. The app is preloaded with the user's mortgage defaults.
3. The app correctly distinguishes between overpayments made on the 1st of the month and overpayments made on later dates.
4. Dashboard outputs, transaction ledger, monthly summary, charts, and exports all derive from the same calculation result.
5. Changing the current outstanding balance immediately changes the ledger and all dashboard outputs.
6. The app can export Excel and CSV results.
7. The test suite passes with `pytest`.
8. The README provides clear Visual Studio Code setup instructions.
9. The app includes warnings about lender-specific posting, rounding, and interest calculation differences.

---

## Important Limitation to State in the App

This app is a planning model. It is not a legal or financial statement from the bank. The lender's actual balance may differ because of fees, insurance, posting cut-off times, non-365-day day-count conventions, rate reset rules, rounding, or lender-specific allocation rules. The user should reconcile the model periodically against official mortgage statements.

---

## Final Instruction to Codex

Build the complete project now. Prioritise correctness of the date-aware transaction engine and tests over visual polish. After implementation, run the tests, fix failures, and provide a concise summary of the files created and any assumptions made.
