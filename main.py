import argparse
import csv
import sys
from collections.abc import Iterable
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO

from src.cashflow import build_cashflows
from src.discounting import cbr_zero_coupon_curve, discount_cashflow
from src.models import Deal, DiscountedCashFlow
from src.parser import parse_deals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("data/deals.csv"),
    )
    parser.add_argument("--deal-id", type=int)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def select_deals(
    deals: Iterable[Deal],
    deal_id: int | None,
) -> list[Deal]:
    selected = [
        deal
        for deal in deals
        if deal_id is None or deal.deal_id == deal_id
    ]
    if deal_id is not None and not selected:
        raise ValueError(f"deal_id={deal_id} not found")
    return selected


def write_cashflows(
    deals: Iterable[Deal],
    destination: TextIO,
) -> None:
    writer = csv.writer(destination, delimiter=";")
    writer.writerow(
        (
            "deal_id",
            "cashflow_date",
            "currency",
            "interest_period_start",
            "interest_period_end",
            "principal_cf",
            "interest_cf",
            "balance_before",
            "balance_after",
            "discount_factor",
            "discounted_principal_cf",
            "discounted_interest_cf",
            "present_value",
        )
    )

    for deal in deals:
        curve = cbr_zero_coupon_curve(deal.report_date)
        for cashflow in build_cashflows(deal):
            writer.writerow(
                cashflow_row(
                    discount_cashflow(cashflow, curve)
                )
            )


def cashflow_row(
    discounted_cashflow: DiscountedCashFlow,
) -> tuple[object, ...]:
    cashflow = discounted_cashflow.cashflow
    return (
        cashflow.deal_id,
        cashflow.cashflow_date.isoformat(),
        cashflow.currency,
        cashflow.interest_period_start.isoformat(),
        cashflow.interest_period_end.isoformat(),
        cashflow.principal_cf,
        cashflow.interest_cf,
        cashflow.balance_before,
        cashflow.balance_after,
        discounted_cashflow.discount_factor,
        discounted_cashflow.discounted_principal_cf,
        discounted_cashflow.discounted_interest_cf,
        discounted_cashflow.present_value,
    )


def main() -> None:
    args = parse_args()
    try:
        deals = select_deals(parse_deals(args.input), args.deal_id)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error

    destination = (
        args.output.open("w", encoding="utf-8", newline="")
        if args.output is not None
        else nullcontext(sys.stdout)
    )
    with destination as stream:
        write_cashflows(deals, stream)


if __name__ == "__main__":
    main()
