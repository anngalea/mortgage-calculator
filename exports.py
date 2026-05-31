from __future__ import annotations

from dataclasses import asdict
from io import BytesIO

import pandas as pd

from models import MortgageInput, Overpayment, ProjectionResult, RatePeriod


def rounded_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].round(2)
    return result


def ledger_csv(result: ProjectionResult) -> bytes:
    return rounded_frame(result.ledger).to_csv(index=False).encode("utf-8")


def monthly_summary_csv(result: ProjectionResult) -> bytes:
    return rounded_frame(result.monthly_summary).to_csv(index=False).encode("utf-8")


def excel_export(
    result: ProjectionResult,
    mortgage: MortgageInput,
    rate_schedule: list[RatePeriod],
    overpayments: list[Overpayment],
    notes: list[str] | None = None,
) -> bytes:
    output = BytesIO()
    notes = notes or []
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dashboard = pd.DataFrame(
            [{"Metric": key, "Value": value} for key, value in result.dashboard.items()]
        )
        dashboard.to_excel(writer, sheet_name="Dashboard Summary", index=False)

        inputs = pd.DataFrame(
            [{"Input": key, "Value": value} for key, value in asdict(mortgage).items()]
        )
        inputs.to_excel(writer, sheet_name="Inputs", index=False)

        rates = pd.DataFrame(
            [
                {
                    "Effective Date": item.effective_date,
                    "Annual Rate %": item.annual_rate * 100,
                    "Notes": item.notes,
                }
                for item in rate_schedule
            ]
        )
        rates.to_excel(writer, sheet_name="Interest Rate Schedule", index=False)

        overpayment_rows = pd.DataFrame(
            [
                {
                    "Date": item.date,
                    "Amount": item.amount,
                    "Description": item.description,
                }
                for item in overpayments
            ]
        )
        overpayment_rows.to_excel(writer, sheet_name="Overpayments", index=False)

        rounded_frame(result.ledger).to_excel(writer, sheet_name="Transaction Ledger", index=False)
        rounded_frame(result.monthly_summary).to_excel(
            writer, sheet_name="Monthly Summary", index=False
        )

        all_notes = result.warnings + notes
        pd.DataFrame({"Notes and Warnings": all_notes}).to_excel(
            writer, sheet_name="Notes and Warnings", index=False
        )
    return output.getvalue()

