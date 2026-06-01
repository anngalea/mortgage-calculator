from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

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
