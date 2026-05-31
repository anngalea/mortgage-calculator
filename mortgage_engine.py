from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from math import isclose

import pandas as pd

from models import (
    LedgerEntry,
    MortgageInput,
    Overpayment,
    ProjectionResult,
    ProjectionSettings,
    RatePeriod,
)

ZERO_TOLERANCE = 0.005


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, days_in_month(year, month))
    return date(year, month, day)


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def scheduled_date_for_month(year: int, month: int, payment_day: int) -> date:
    return date(year, month, min(payment_day, days_in_month(year, month)))


def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def original_total_payments(mortgage: MortgageInput) -> int:
    return mortgage.original_term_years * 12


def contractual_maturity_date(mortgage: MortgageInput) -> date:
    return add_months(mortgage.start_date, original_total_payments(mortgage)) - timedelta(days=1)


def contractual_last_payment_date(mortgage: MortgageInput) -> date:
    return scheduled_date_for_month(
        contractual_maturity_date(mortgage).year,
        contractual_maturity_date(mortgage).month,
        mortgage.payment_day,
    )


def remaining_scheduled_payments(mortgage: MortgageInput, as_of: date) -> int:
    elapsed_months = months_between(mortgage.start_date, as_of)
    return max(0, original_total_payments(mortgage) - elapsed_months)


def sort_rates(rate_schedule: list[RatePeriod]) -> list[RatePeriod]:
    return sorted(rate_schedule, key=lambda rate: rate.effective_date)


def rate_for_date(rate_schedule: list[RatePeriod], event_date: date) -> float | None:
    applicable = [rate for rate in sort_rates(rate_schedule) if rate.effective_date <= event_date]
    if not applicable:
        return None
    return applicable[-1].annual_rate


def rate_changes_on(rate_schedule: list[RatePeriod], event_date: date) -> list[RatePeriod]:
    return [rate for rate in sort_rates(rate_schedule) if rate.effective_date == event_date]


def accrue_interest(
    balance: float,
    annual_rate: float,
    days_elapsed: int,
    interest_mode: str,
    is_scheduled_event: bool,
) -> float:
    if balance <= 0 or annual_rate <= 0:
        return 0.0
    if interest_mode == "monthly" and is_scheduled_event:
        return balance * annual_rate / 12
    if interest_mode == "monthly":
        return 0.0
    return balance * annual_rate * days_elapsed / 365


def recalculate_payment(balance: float, annual_rate: float, remaining_months: int) -> float:
    if remaining_months <= 0:
        return balance
    monthly_rate = annual_rate / 12
    if isclose(monthly_rate, 0.0, abs_tol=1e-12):
        return balance / remaining_months
    return balance * monthly_rate / (1 - (1 + monthly_rate) ** -remaining_months)


def validate_inputs(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    overpayments: list[Overpayment],
    settings: ProjectionSettings,
) -> list[str]:
    warnings: list[str] = []
    if mortgage.current_balance <= 0:
        warnings.append("Current balance is missing or zero.")
    if mortgage.current_monthly_payment <= 0:
        warnings.append("Current monthly payment is missing or zero.")
    if not rate_schedule:
        warnings.append("Interest-rate schedule is empty.")
    elif rate_for_date(rate_schedule, mortgage.next_payment_date) is None:
        warnings.append("No valid interest rate applies to the projection start date.")
    if any(rate.annual_rate < 0 for rate in rate_schedule):
        warnings.append("Interest rates must be non-negative.")
    for overpayment in overpayments:
        if overpayment.amount <= 0:
            warnings.append(f"Overpayment on {overpayment.date} must be positive.")
        if overpayment.date < mortgage.next_payment_date and not settings.include_historical_events:
            warnings.append(f"Overpayment on {overpayment.date} is before the next payment date.")
        if overpayment.amount > mortgage.current_balance:
            warnings.append(f"Overpayment on {overpayment.date} is greater than the outstanding balance.")
        if overpayment.date.day == mortgage.payment_day:
            warnings.append(
                f"Overpayment on {overpayment.date} is processed after the scheduled payment on the same date."
            )
        elif overpayment.date > mortgage.next_payment_date:
            warnings.append(
                f"Overpayment on {overpayment.date} is a principal-only event on that date."
            )

    current_rate = rate_for_date(rate_schedule, mortgage.next_payment_date) or mortgage.current_rate
    monthly_interest = mortgage.current_balance * current_rate / 12
    if mortgage.current_monthly_payment <= monthly_interest:
        warnings.append("Current monthly payment may be too low to cover monthly interest.")
    warnings.append(
        "Actual lender figures may differ because banks can use their own day-count, posting, compounding, and rounding rules."
    )
    return warnings


def project_mortgage(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    overpayments: list[Overpayment] | None = None,
    settings: ProjectionSettings | None = None,
) -> ProjectionResult:
    overpayments = overpayments or []
    settings = settings or ProjectionSettings()
    warnings = validate_inputs(mortgage, rate_schedule, overpayments, settings)

    rates = sort_rates(rate_schedule)
    applicable_start_rate = rate_for_date(rates, mortgage.next_payment_date)
    if applicable_start_rate is None:
        applicable_start_rate = mortgage.current_rate

    balance = float(mortgage.current_balance)
    scheduled_payment_amount = float(mortgage.current_monthly_payment)
    if settings.payment_mode == "recalculate_immediately":
        scheduled_payment_amount = recalculate_payment(
            balance,
            applicable_start_rate,
            remaining_term_months(mortgage, mortgage.next_payment_date),
        )

    overpayments_by_date: dict[date, list[Overpayment]] = {}
    for overpayment in overpayments:
        if overpayment.date < mortgage.next_payment_date and not settings.include_historical_events:
            continue
        overpayments_by_date.setdefault(overpayment.date, []).append(overpayment)

    entries: list[LedgerEntry] = []
    previous_event_date = mortgage.next_payment_date
    next_payment_date = mortgage.next_payment_date
    final_contractual_payment_date = contractual_last_payment_date(mortgage)
    horizon_date = add_months(mortgage.next_payment_date, settings.max_projection_years * 12)
    payoff_date: date | None = None

    while balance > ZERO_TOLERANCE and next_payment_date <= horizon_date:
        candidate_dates = [next_payment_date]
        candidate_dates.extend(d for d in overpayments_by_date if previous_event_date <= d <= next_payment_date)
        candidate_dates.extend(
            rate.effective_date
            for rate in rates
            if previous_event_date <= rate.effective_date <= next_payment_date
        )
        event_dates = sorted(set(candidate_dates))

        for event_date in event_dates:
            if event_date < mortgage.next_payment_date:
                continue
            if balance <= ZERO_TOLERANCE:
                break

            is_scheduled = event_date == next_payment_date
            rate = rate_for_date(rates, previous_event_date) or applicable_start_rate
            days_elapsed = 0 if event_date == previous_event_date else (event_date - previous_event_date).days
            opening_balance = balance
            interest = accrue_interest(
                opening_balance,
                rate,
                days_elapsed,
                settings.interest_mode,
                is_scheduled,
            )
            scheduled_payment = 0.0
            scheduled_principal = 0.0
            scheduled_interest = 0.0
            extra_principal = 0.0
            notes: list[str] = []

            # Same-date ordering is intentional: accrue interest, scheduled payment,
            # recurring overpayment, lump-sum overpayment, then rate changes for future accrual.
            if is_scheduled:
                amount_due = opening_balance + interest
                if event_date >= final_contractual_payment_date:
                    scheduled_payment = amount_due
                    notes.append("Final contractual payment clears remaining balance.")
                else:
                    scheduled_payment = min(scheduled_payment_amount, amount_due)
                scheduled_interest = min(interest, scheduled_payment)
                scheduled_principal = max(0.0, scheduled_payment - scheduled_interest)
                balance = max(0.0, opening_balance - scheduled_principal)
                if scheduled_payment < scheduled_payment_amount and balance <= ZERO_TOLERANCE:
                    notes.append("Final scheduled payment capped at remaining balance.")

                recurring = recurring_overpayment_for_date(event_date, settings, mortgage.payment_day)
                if recurring > 0 and balance > ZERO_TOLERANCE:
                    applied = min(recurring, balance)
                    balance -= applied
                    extra_principal += applied
                    notes.append("Recurring overpayment applied after scheduled payment.")

            if event_date in overpayments_by_date and balance > ZERO_TOLERANCE:
                requested = sum(item.amount for item in overpayments_by_date[event_date])
                applied = min(requested, balance)
                balance -= applied
                extra_principal += applied
                descriptions = [item.description for item in overpayments_by_date[event_date] if item.description]
                if descriptions:
                    notes.append("; ".join(descriptions))
                if applied < requested:
                    notes.append("Overpayment capped at remaining balance.")

            if balance <= ZERO_TOLERANCE:
                balance = 0.0
                payoff_date = event_date
                notes.append("Final payoff.")

            changes = rate_changes_on(rates, event_date)
            if changes and event_date != mortgage.next_payment_date:
                notes.append(f"Rate changes to {changes[-1].annual_rate * 100:.2f}% for future accrual.")
            if changes and settings.recalculate_on_rate_change and event_date >= mortgage.next_payment_date:
                new_rate = changes[-1].annual_rate
                scheduled_payment_amount = recalculate_payment(
                    balance,
                    new_rate,
                    remaining_scheduled_payments(mortgage, add_months(event_date, 1)),
                )
                notes.append("Scheduled payment recalculated for rate change.")

            event_type_parts = []
            if is_scheduled:
                event_type_parts.append("Scheduled payment")
            if extra_principal:
                event_type_parts.append("Overpayment")
            if changes and not is_scheduled and not extra_principal:
                event_type_parts.append("Rate change")
            event_type = " + ".join(event_type_parts) or "Event"

            if scheduled_payment or extra_principal or changes:
                entries.append(
                    LedgerEntry(
                        date=event_date,
                        event_type=event_type,
                        opening_balance=opening_balance,
                        rate=rate,
                        days_since_prior_event=days_elapsed,
                        interest_accrued=interest,
                        scheduled_payment=scheduled_payment,
                        scheduled_principal=scheduled_principal,
                        scheduled_interest=scheduled_interest,
                        extra_principal=extra_principal,
                        closing_balance=balance,
                        notes=" ".join(notes),
                    )
                )

            previous_event_date = event_date

        if balance <= ZERO_TOLERANCE:
            break
        next_payment_date = add_months(next_payment_date, 1)

    if balance > ZERO_TOLERANCE:
        warnings.append("The mortgage does not pay off within the projection horizon.")
    if entries and entries[-1].scheduled_payment and entries[-1].scheduled_payment < mortgage.current_monthly_payment * 0.75:
        warnings.append("The final scheduled payment is significantly lower than the regular payment.")

    ledger = ledger_to_frame(entries)
    monthly_summary = build_monthly_summary(ledger)
    dashboard = build_dashboard(mortgage, ledger, monthly_summary, payoff_date)
    return ProjectionResult(ledger=ledger, monthly_summary=monthly_summary, dashboard=dashboard, warnings=warnings)


def recurring_overpayment_for_date(
    event_date: date,
    settings: ProjectionSettings,
    payment_day: int,
) -> float:
    if settings.monthly_overpayment <= 0:
        return 0.0
    if event_date.day != payment_day:
        return 0.0
    if settings.monthly_overpayment_start and event_date < settings.monthly_overpayment_start:
        return 0.0
    if settings.monthly_overpayment_end and event_date > settings.monthly_overpayment_end:
        return 0.0
    return settings.monthly_overpayment


def remaining_term_months(mortgage: MortgageInput, as_of: date) -> int:
    return max(1, remaining_scheduled_payments(mortgage, as_of))


def ledger_to_frame(entries: list[LedgerEntry]) -> pd.DataFrame:
    columns = [
        "Date",
        "Event Type",
        "Opening Balance",
        "Rate %",
        "Days Since Prior Event",
        "Interest Accrued",
        "Scheduled Payment",
        "Scheduled Principal",
        "Scheduled Interest",
        "Extra Principal",
        "Closing Balance",
        "Notes",
    ]
    if not entries:
        return pd.DataFrame(columns=columns)
    rows = []
    for entry in entries:
        data = asdict(entry)
        rows.append(
            {
                "Date": data["date"],
                "Event Type": data["event_type"],
                "Opening Balance": data["opening_balance"],
                "Rate %": data["rate"] * 100,
                "Days Since Prior Event": data["days_since_prior_event"],
                "Interest Accrued": data["interest_accrued"],
                "Scheduled Payment": data["scheduled_payment"],
                "Scheduled Principal": data["scheduled_principal"],
                "Scheduled Interest": data["scheduled_interest"],
                "Extra Principal": data["extra_principal"],
                "Closing Balance": data["closing_balance"],
                "Notes": data["notes"],
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_monthly_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Month",
        "Opening Balance",
        "Interest",
        "Scheduled Payments",
        "Extra Principal",
        "Total Paid",
        "Principal Reduction",
        "Closing Balance",
    ]
    if ledger.empty:
        return pd.DataFrame(columns=columns)
    frame = ledger.copy()
    frame["Month"] = pd.to_datetime(frame["Date"]).dt.to_period("M").astype(str)
    grouped_rows = []
    for month, group in frame.groupby("Month", sort=True):
        opening = float(group.iloc[0]["Opening Balance"])
        closing = float(group.iloc[-1]["Closing Balance"])
        scheduled = float(group["Scheduled Payment"].sum())
        extra = float(group["Extra Principal"].sum())
        interest = float(group["Interest Accrued"].sum())
        grouped_rows.append(
            {
                "Month": month,
                "Opening Balance": opening,
                "Interest": interest,
                "Scheduled Payments": scheduled,
                "Extra Principal": extra,
                "Total Paid": scheduled + extra,
                "Principal Reduction": opening - closing,
                "Closing Balance": closing,
            }
        )
    return pd.DataFrame(grouped_rows, columns=columns)


def build_dashboard(
    mortgage: MortgageInput,
    ledger: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    payoff_date: date | None,
) -> dict[str, float | int | str | date | None]:
    total_interest = 0.0 if ledger.empty else float(ledger["Interest Accrued"].sum())
    total_scheduled = 0.0 if ledger.empty else float(ledger["Scheduled Payment"].sum())
    total_extra = 0.0 if ledger.empty else float(ledger["Extra Principal"].sum())
    total_paid = total_scheduled + total_extra
    months_remaining = len(monthly_summary)
    fixed_expiry_balance = None
    if not ledger.empty:
        expiry_rows = ledger[pd.to_datetime(ledger["Date"]).dt.date <= date(2028, 11, 1)]
        if not expiry_rows.empty:
            fixed_expiry_balance = float(expiry_rows.iloc[-1]["Closing Balance"])
    return {
        "Starting balance used": mortgage.current_balance,
        "Next scheduled payment date": mortgage.next_payment_date,
        "Current scheduled monthly payment": mortgage.current_monthly_payment,
        "Projected payoff date": payoff_date,
        "Months remaining": months_remaining,
        "Remaining scheduled payments": months_remaining,
        "Total scheduled payment amount remaining": total_scheduled,
        "Total extra overpayments": total_extra,
        "Total interest from projection start": total_interest,
        "Total amount paid from projection start": total_paid,
        "Balance at initial fixed-rate expiry": fixed_expiry_balance,
        "Original total monthly payments": original_total_payments(mortgage),
        "Contractual maturity date": contractual_maturity_date(mortgage),
    }


def project_with_baseline(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    overpayments: list[Overpayment],
    settings: ProjectionSettings,
) -> tuple[ProjectionResult, ProjectionResult]:
    baseline_settings = ProjectionSettings(
        interest_mode=settings.interest_mode,
        payment_mode=settings.payment_mode,
        recalculate_on_rate_change=settings.recalculate_on_rate_change,
        monthly_overpayment=0.0,
        monthly_overpayment_start=settings.monthly_overpayment_start,
        monthly_overpayment_end=settings.monthly_overpayment_end,
        include_historical_events=settings.include_historical_events,
        advanced_payment_day=settings.advanced_payment_day,
        max_projection_years=settings.max_projection_years,
    )
    baseline = project_mortgage(mortgage, rate_schedule, [], baseline_settings)
    scenario = project_mortgage(mortgage, rate_schedule, overpayments, settings)
    baseline_interest = baseline.dashboard["Total interest from projection start"] or 0.0
    scenario_interest = scenario.dashboard["Total interest from projection start"] or 0.0
    baseline_months = baseline.dashboard["Months remaining"] or 0
    scenario_months = scenario.dashboard["Months remaining"] or 0
    scenario.dashboard["Interest saved versus baseline"] = float(baseline_interest) - float(scenario_interest)
    scenario.dashboard["Months saved versus baseline"] = int(baseline_months) - int(scenario_months)
    return baseline, scenario
