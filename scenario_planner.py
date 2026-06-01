from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil

from models import MortgageInput, Overpayment, ProjectionResult, ProjectionSettings, RatePeriod
from mortgage_engine import add_months, project_mortgage, sort_rates


DEFAULT_COMPARISON_AMOUNT = 12_000.0


@dataclass(frozen=True)
class AutomaticScenario:
    name: str
    description: str
    overpayments: list[Overpayment]
    result: ProjectionResult
    payoff_date: date | None
    months_saved: int
    interest_saved: float
    total_interest: float
    total_extra_paid: float


@dataclass(frozen=True)
class ScenarioComparison:
    amount: float
    baseline: ProjectionResult
    scenarios: list[AutomaticScenario]
    best: AutomaticScenario | None


@dataclass(frozen=True)
class HalfTimeRepaymentPlan:
    baseline_months: int
    target_months: int
    monthly_payment_required: float
    monthly_overpayment_required: float
    result: ProjectionResult
    payoff_date: date | None
    months_saved: int
    interest_saved: float
    total_interest: float
    total_extra_paid: float


def comparison_settings(settings: ProjectionSettings) -> ProjectionSettings:
    return ProjectionSettings(
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


def first_future_rate_change(mortgage: MortgageInput, rate_schedule: list[RatePeriod]) -> RatePeriod | None:
    future_rates = [
        rate
        for rate in sort_rates(rate_schedule)
        if rate.effective_date > mortgage.next_payment_date
    ]
    if not future_rates:
        return None
    return future_rates[0]


def monthly_dates(start_date: date, end_date: date) -> list[date]:
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date = add_months(current_date, 1)
    return dates


def instalment_overpayments(start_date: date, end_date: date, amount: float) -> list[Overpayment]:
    dates = monthly_dates(start_date, end_date)
    if not dates:
        return []
    instalment_amount = amount / len(dates)
    return [
        Overpayment(payment_date, instalment_amount, "Automatic monthly scenario")
        for payment_date in dates
    ]


def scenario_from_overpayments(
    name: str,
    description: str,
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    settings: ProjectionSettings,
    baseline: ProjectionResult,
    overpayments: list[Overpayment],
) -> AutomaticScenario:
    result = project_mortgage(mortgage, rate_schedule, overpayments, settings)
    baseline_interest = float(baseline.dashboard["Total interest from projection start"] or 0.0)
    scenario_interest = float(result.dashboard["Total interest from projection start"] or 0.0)
    baseline_months = int(baseline.dashboard["Months remaining"] or 0)
    scenario_months = int(result.dashboard["Months remaining"] or 0)
    return AutomaticScenario(
        name=name,
        description=description,
        overpayments=overpayments,
        result=result,
        payoff_date=result.dashboard["Projected payoff date"],
        months_saved=baseline_months - scenario_months,
        interest_saved=baseline_interest - scenario_interest,
        total_interest=scenario_interest,
        total_extra_paid=float(result.dashboard["Total extra overpayments"] or 0.0),
    )


def best_scenario(scenarios: list[AutomaticScenario]) -> AutomaticScenario | None:
    if not scenarios:
        return None
    return max(scenarios, key=lambda scenario: (scenario.interest_saved, scenario.months_saved))


def project_with_monthly_extra(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    settings: ProjectionSettings,
    monthly_extra: float,
) -> ProjectionResult:
    scenario_settings = ProjectionSettings(
        interest_mode=settings.interest_mode,
        payment_mode=settings.payment_mode,
        recalculate_on_rate_change=settings.recalculate_on_rate_change,
        monthly_overpayment=monthly_extra,
        monthly_overpayment_start=mortgage.next_payment_date,
        monthly_overpayment_end=None,
        include_historical_events=settings.include_historical_events,
        advanced_payment_day=settings.advanced_payment_day,
        max_projection_years=settings.max_projection_years,
    )
    return project_mortgage(mortgage, rate_schedule, [], scenario_settings)


def result_months(result: ProjectionResult) -> int:
    return int(result.dashboard["Months remaining"] or 0)


def round_up_to_cent(value: float) -> float:
    return ceil(value * 100) / 100


def calculate_half_time_repayment(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    settings: ProjectionSettings,
) -> HalfTimeRepaymentPlan:
    settings = comparison_settings(settings)
    baseline = project_mortgage(mortgage, rate_schedule, [], settings)
    baseline_months = result_months(baseline)
    target_months = max(1, ceil(baseline_months / 2))
    baseline_interest = float(baseline.dashboard["Total interest from projection start"] or 0.0)

    low = 0.0
    high = max(mortgage.current_monthly_payment, mortgage.current_balance)
    high_result = project_with_monthly_extra(mortgage, rate_schedule, settings, high)
    while result_months(high_result) > target_months:
        high *= 2
        high_result = project_with_monthly_extra(mortgage, rate_schedule, settings, high)

    for _ in range(50):
        midpoint = (low + high) / 2
        result = project_with_monthly_extra(mortgage, rate_schedule, settings, midpoint)
        if result_months(result) <= target_months:
            high = midpoint
            high_result = result
        else:
            low = midpoint

    monthly_extra = round_up_to_cent(high)
    final_result = project_with_monthly_extra(mortgage, rate_schedule, settings, monthly_extra)
    while result_months(final_result) > target_months:
        monthly_extra = round(monthly_extra + 0.01, 2)
        final_result = project_with_monthly_extra(mortgage, rate_schedule, settings, monthly_extra)

    scenario_interest = float(final_result.dashboard["Total interest from projection start"] or 0.0)
    scenario_months = result_months(final_result)
    return HalfTimeRepaymentPlan(
        baseline_months=baseline_months,
        target_months=target_months,
        monthly_payment_required=mortgage.current_monthly_payment + monthly_extra,
        monthly_overpayment_required=monthly_extra,
        result=final_result,
        payoff_date=final_result.dashboard["Projected payoff date"],
        months_saved=baseline_months - scenario_months,
        interest_saved=baseline_interest - scenario_interest,
        total_interest=scenario_interest,
        total_extra_paid=float(final_result.dashboard["Total extra overpayments"] or 0.0),
    )


def generate_overpayment_scenarios(
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    settings: ProjectionSettings,
    amount: float = DEFAULT_COMPARISON_AMOUNT,
) -> ScenarioComparison:
    amount = float(amount)
    settings = comparison_settings(settings)
    baseline = project_mortgage(mortgage, rate_schedule, [], settings)
    now_date = mortgage.next_payment_date + timedelta(days=1)
    rate_change = first_future_rate_change(mortgage, rate_schedule)
    rate_change_payment_date = (
        rate_change.effective_date + timedelta(days=1)
        if rate_change
        else now_date
    )

    definitions = [
        (
            "Pay now",
            "Pay the full amount now.",
            [Overpayment(now_date, amount, "Automatic scenario: pay now")],
        ),
        (
            "Pay when the rate increases",
            "Pay the full amount when the next rate increase starts.",
            [Overpayment(rate_change_payment_date, amount, "Automatic scenario: rate increase")],
        ),
        (
            "Spread it monthly to the rate increase",
            "Split the amount into equal monthly overpayments until the rate increase.",
            instalment_overpayments(now_date, rate_change_payment_date, amount),
        ),
    ]
    scenarios = [
        scenario_from_overpayments(
            name,
            description,
            mortgage,
            rate_schedule,
            settings,
            baseline,
            overpayments,
        )
        for name, description, overpayments in definitions
    ]
    return ScenarioComparison(
        amount=amount,
        baseline=baseline,
        scenarios=scenarios,
        best=best_scenario(scenarios),
    )
