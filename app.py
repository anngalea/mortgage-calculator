from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from display_helpers import metric_value
from exports import excel_export, ledger_csv, monthly_summary_csv, rounded_frame
from models import MortgageInput, Overpayment, ProjectionSettings, RatePeriod
from mortgage_engine import project_with_baseline
from public_warning import PUBLIC_WARNING_TEXT
from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, DEFAULT_SETTINGS
from scenario_planner import (
    DEFAULT_COMPARISON_AMOUNT,
    calculate_half_time_repayment,
    generate_overpayment_scenarios,
)


st.set_page_config(page_title="Mortgage Overpayment Planner", layout="wide")

INPUT_VERSION = "2026_05_30_bank_balance"


def money(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"€{float(value):,.2f}"


def parse_rate_schedule(frame: pd.DataFrame) -> list[RatePeriod]:
    rates: list[RatePeriod] = []
    for _, row in frame.dropna(how="all").iterrows():
        if pd.isna(row.get("Effective Date")) or pd.isna(row.get("Annual Rate %")):
            continue
        effective = pd.to_datetime(row["Effective Date"]).date()
        rate = float(row["Annual Rate %"]) / 100
        notes = "" if pd.isna(row.get("Notes", "")) else str(row.get("Notes", ""))
        rates.append(RatePeriod(effective, rate, notes))
    return sorted(rates, key=lambda item: item.effective_date)


def parse_overpayments(frame: pd.DataFrame) -> list[Overpayment]:
    overpayments: list[Overpayment] = []
    for _, row in frame.dropna(how="all").iterrows():
        if pd.isna(row.get("Date")) or pd.isna(row.get("Amount")):
            continue
        payment_date = pd.to_datetime(row["Date"]).date()
        amount = float(row["Amount"])
        description = "" if pd.isna(row.get("Description", "")) else str(row.get("Description", ""))
        if amount > 0:
            overpayments.append(Overpayment(payment_date, amount, description))
    return sorted(overpayments, key=lambda item: item.date)


st.title("Mortgage Overpayment Planner")
st.caption(
    "A date-aware projection for scheduled payments, recurring overpayments, and dated lump sums."
)
st.warning(PUBLIC_WARNING_TEXT)

with st.sidebar:
    st.header("Mortgage Setup")
    original_amount = st.number_input(
        "Original mortgage amount",
        min_value=0.0,
        value=DEFAULT_MORTGAGE.original_amount,
        step=1000.0,
        format="%.2f",
        key=f"original_amount_{INPUT_VERSION}",
    )
    start_date = st.date_input(
        "Original start date",
        value=DEFAULT_MORTGAGE.start_date,
        key=f"start_date_{INPUT_VERSION}",
    )
    original_term_years = st.number_input(
        "Original term in years",
        min_value=1,
        max_value=60,
        value=DEFAULT_MORTGAGE.original_term_years,
        key=f"original_term_years_{INPUT_VERSION}",
    )
    current_balance = st.number_input(
        "Current outstanding balance",
        min_value=0.0,
        value=DEFAULT_MORTGAGE.current_balance,
        step=1000.0,
        format="%.2f",
        key=f"current_balance_{INPUT_VERSION}",
    )
    current_payment = st.number_input(
        "Current monthly payment",
        min_value=0.0,
        value=DEFAULT_MORTGAGE.current_monthly_payment,
        step=10.0,
        format="%.2f",
        key=f"current_payment_{INPUT_VERSION}",
    )
    next_payment_date = st.date_input(
        "Next scheduled payment date",
        value=DEFAULT_MORTGAGE.next_payment_date,
        key=f"next_payment_date_{INPUT_VERSION}",
    )
    advanced_payment_day = st.toggle(
        "Advanced payment day",
        value=False,
        key=f"advanced_payment_day_{INPUT_VERSION}",
    )
    payment_day = 1
    if advanced_payment_day:
        payment_day = st.number_input(
            "Payment day of month",
            min_value=1,
            max_value=28,
            value=1,
            key=f"payment_day_{INPUT_VERSION}",
        )
    else:
        st.text_input("Payment day of month", value="1", disabled=True, key=f"payment_day_locked_{INPUT_VERSION}")
    current_rate = st.number_input(
        "Current interest rate %",
        min_value=0.0,
        value=DEFAULT_MORTGAGE.current_rate * 100,
        step=0.05,
        format="%.3f",
        key=f"current_rate_{INPUT_VERSION}",
    )
    inflation_rate = st.number_input(
        "Inflation rate %",
        min_value=0.0,
        value=0.0,
        step=0.25,
        format="%.2f",
        key=f"inflation_rate_{INPUT_VERSION}",
    )

st.warning(
    "Actual lender figures may differ because banks can use their own day-count, posting, compounding, and rounding rules.",
    icon="⚠️",
)

mortgage = MortgageInput(
    original_amount=original_amount,
    start_date=start_date,
    original_term_years=int(original_term_years),
    current_balance=current_balance,
    current_monthly_payment=current_payment,
    next_payment_date=next_payment_date,
    payment_day=int(payment_day),
    current_rate=current_rate / 100,
    inflation_rate=inflation_rate / 100,
)

setup_tab, rates_tab, overpayments_tab, auto_tab, dashboard_tab, ledger_tab, charts_tab, exports_tab = st.tabs(
    [
        "Scenario",
        "Interest Rates",
        "Overpayments",
        "Auto Scenarios",
        "Dashboard",
        "Ledger",
        "Charts",
        "Downloads",
    ]
)

with setup_tab:
    col1, col2, col3 = st.columns(3)
    with col1:
        interest_mode_label = st.radio(
            "Interest calculation",
            ["Daily simple interest", "Monthly approximation"],
            index=0,
        )
    with col2:
        payment_mode_label = st.radio(
            "Payment recalculation",
            ["Use current payment until next rate reset", "Recalculate immediately"],
            index=0,
        )
    with col3:
        recalculate_on_rate_change = st.toggle("Recalculate at future rate changes", value=True)
        include_historical = st.toggle("Include historical overpayments", value=False)

with rates_tab:
    default_rates = pd.DataFrame(
        [
            {
                "Effective Date": rate.effective_date,
                "Annual Rate %": rate.annual_rate * 100,
                "Notes": rate.notes,
            }
            for rate in DEFAULT_RATE_SCHEDULE
        ]
    )
    rate_frame = st.data_editor(
        default_rates,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Effective Date": st.column_config.DateColumn("Effective Date"),
            "Annual Rate %": st.column_config.NumberColumn("Annual Rate %", min_value=0.0),
        },
    )
    rate_schedule = parse_rate_schedule(rate_frame)
    if not rate_schedule:
        st.error("Add at least one interest-rate row.")
    elif all(rate.effective_date > next_payment_date for rate in rate_schedule):
        st.warning("No rate exists on or before the next payment date.")

with overpayments_tab:
    col1, col2, col3 = st.columns(3)
    with col1:
        monthly_overpayment = st.number_input(
            "Monthly recurring overpayment", min_value=0.0, value=0.0, step=50.0, format="%.2f"
        )
    with col2:
        recurring_start = st.date_input(
            "Recurring start date", value=DEFAULT_SETTINGS.monthly_overpayment_start or next_payment_date
        )
    with col3:
        use_recurring_end = st.toggle("Use recurring end date", value=False)
        recurring_end = None
        if use_recurring_end:
            recurring_end = st.date_input("Recurring end date", value=recurring_start)

    overpayment_frame = st.data_editor(
        pd.DataFrame(columns=["Date", "Amount", "Description"]),
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Date": st.column_config.DateColumn("Date"),
            "Amount": st.column_config.NumberColumn("Amount", min_value=0.0),
        },
    )
    overpayments = parse_overpayments(overpayment_frame)
    for item in overpayments:
        if item.date.day == payment_day:
            st.info(f"{item.date}: same-day overpayments are processed after the scheduled payment.")
        elif item.date >= next_payment_date:
            st.info(f"{item.date}: overpayment is treated as a principal-only event on that date.")

settings = ProjectionSettings(
    interest_mode="daily" if interest_mode_label == "Daily simple interest" else "monthly",
    payment_mode=(
        "use_current_until_reset"
        if payment_mode_label == "Use current payment until next rate reset"
        else "recalculate_immediately"
    ),
    recalculate_on_rate_change=recalculate_on_rate_change,
    monthly_overpayment=monthly_overpayment,
    monthly_overpayment_start=recurring_start,
    monthly_overpayment_end=recurring_end,
    include_historical_events=include_historical,
    advanced_payment_day=advanced_payment_day,
)

baseline_result, scenario_result = project_with_baseline(
    mortgage, rate_schedule, overpayments, settings
)

for warning in scenario_result.warnings:
    st.warning(warning)

with auto_tab:
    st.subheader("Automatic overpayment scenarios")
    amount_to_compare = st.number_input(
        "Amount to compare",
        min_value=0.0,
        value=DEFAULT_COMPARISON_AMOUNT,
        step=500.0,
        format="%.2f",
        key=f"auto_amount_{INPUT_VERSION}",
    )
    auto_comparison = generate_overpayment_scenarios(
        mortgage,
        rate_schedule,
        settings,
        amount=amount_to_compare,
    )
    best_auto = auto_comparison.best

    if best_auto:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Best option", best_auto.name)
        metric_cols[1].metric("Interest saved", money(best_auto.interest_saved))
        metric_cols[2].metric("Months saved", best_auto.months_saved)
        metric_cols[3].metric("Payoff date", metric_value(best_auto.payoff_date))

    scenario_rows = pd.DataFrame(
        [
            {
                "Scenario": item.name,
                "What this does": item.description,
                "Payoff Date": item.payoff_date,
                "Months Saved": item.months_saved,
                "Interest Saved": item.interest_saved,
                "Total Interest": item.total_interest,
                "Total Extra Paid": item.total_extra_paid,
            }
            for item in auto_comparison.scenarios
        ]
    )
    st.dataframe(rounded_frame(scenario_rows), width="stretch")

    if not scenario_rows.empty:
        chart_rows = scenario_rows.melt(
            id_vars="Scenario",
            value_vars=["Interest Saved", "Months Saved"],
            var_name="Measure",
            value_name="Value",
        )
        st.plotly_chart(
            px.bar(
                chart_rows,
                x="Scenario",
                y="Value",
                color="Measure",
                barmode="group",
                title="Savings by automatic scenario",
            ),
            width="stretch",
        )

    st.subheader("Repay in half the time")
    half_time_plan = calculate_half_time_repayment(mortgage, rate_schedule, settings)
    half_cols = st.columns(4)
    half_cols[0].metric("Target months", half_time_plan.target_months)
    half_cols[1].metric("Monthly payment needed", money(half_time_plan.monthly_payment_required))
    half_cols[2].metric("Extra per month needed", money(half_time_plan.monthly_overpayment_required))
    half_cols[3].metric("Payoff date", metric_value(half_time_plan.payoff_date))

    half_cols = st.columns(3)
    half_cols[0].metric("Interest saved", money(half_time_plan.interest_saved))
    half_cols[1].metric("Months saved", half_time_plan.months_saved)
    half_cols[2].metric("Total extra paid", money(half_time_plan.total_extra_paid))

with dashboard_tab:
    dashboard = scenario_result.dashboard
    metric_cols = st.columns(4)
    metric_cols[0].metric("Projected payoff date", metric_value(dashboard.get("Projected payoff date")))
    metric_cols[1].metric(
        "Remaining scheduled payments",
        metric_value(dashboard.get("Remaining scheduled payments", 0)),
    )
    metric_cols[2].metric(
        "Interest saved",
        money(dashboard.get("Interest saved versus baseline", 0.0)),
    )
    metric_cols[3].metric("Months saved", dashboard.get("Months saved versus baseline", 0))

    metric_cols = st.columns(4)
    metric_cols[0].metric("Starting balance", money(dashboard.get("Starting balance used")))
    metric_cols[1].metric(
        "Total interest", money(dashboard.get("Total interest from projection start"))
    )
    metric_cols[2].metric(
        "Total extra overpayments", money(dashboard.get("Total extra overpayments"))
    )
    metric_cols[3].metric(
        "Balance at fixed-rate expiry",
        money(dashboard.get("Balance at initial fixed-rate expiry")),
    )
    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Original total monthly payments",
        metric_value(dashboard.get("Original total monthly payments")),
    )
    metric_cols[1].metric(
        "Contractual maturity date",
        metric_value(dashboard.get("Contractual maturity date")),
    )

with ledger_tab:
    st.subheader("Transaction Ledger")
    st.dataframe(rounded_frame(scenario_result.ledger), width="stretch")
    st.subheader("Monthly Summary")
    st.dataframe(rounded_frame(scenario_result.monthly_summary), width="stretch")

with charts_tab:
    if scenario_result.ledger.empty:
        st.info("No projection rows available yet.")
    else:
        scenario_ledger = scenario_result.ledger.copy()
        baseline_ledger = baseline_result.ledger.copy()
        scenario_ledger["Scenario"] = "Selected"
        baseline_ledger["Scenario"] = "Baseline"
        comparison = pd.concat([baseline_ledger, scenario_ledger], ignore_index=True)

        st.plotly_chart(
            px.line(
                comparison,
                x="Date",
                y="Closing Balance",
                color="Scenario",
                title="Outstanding balance over time",
            ),
            width="stretch",
        )
        monthly = scenario_result.monthly_summary.copy()
        st.plotly_chart(
            px.bar(monthly, x="Month", y="Interest", title="Interest paid over time"),
            width="stretch",
        )
        principal_interest = monthly[["Month", "Interest", "Principal Reduction"]].melt(
            id_vars="Month", var_name="Component", value_name="Amount"
        )
        st.plotly_chart(
            px.bar(
                principal_interest,
                x="Month",
                y="Amount",
                color="Component",
                title="Principal vs interest by month",
            ),
            width="stretch",
        )

with exports_tab:
    notes = [
        "Same-day ordering: interest accrues first, then scheduled payment, recurring overpayment, lump-sum overpayment, and rate changes for future accrual.",
        "Displayed and exported figures are rounded to 2 decimals; internal calculations keep full precision.",
    ]
    st.download_button(
        "Download Excel workbook",
        data=excel_export(scenario_result, mortgage, rate_schedule, overpayments, notes),
        file_name="mortgage_projection.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Download transaction ledger CSV",
        data=ledger_csv(scenario_result),
        file_name="transaction_ledger.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download monthly summary CSV",
        data=monthly_summary_csv(scenario_result),
        file_name="monthly_summary.csv",
        mime="text/csv",
    )
