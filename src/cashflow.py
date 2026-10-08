from collections import defaultdict
from datetime import date
from decimal import Decimal

from src.dates import generate_schedule
from src.models import CashFlow, Deal
from src.principal import build_principal_schedule, _round_money
from src.rates import fixed_period_rate


def build_cashflows(deal: Deal) -> tuple[CashFlow, ...]:
    principal_schedule = build_principal_schedule(deal)
    principal_by_date: dict[date, Decimal] = defaultdict(Decimal)
    for pay in principal_schedule:
        principal_by_date[pay.date] += pay.amount

    if deal.interest_payment_dates:
        interest_dates = {
            payment_date
            for payment_date in deal.interest_payment_dates
            if deal.report_date < payment_date <= deal.maturity_date
        }

    elif deal.rate_spec.payment_rule is not None:
        interest_dates = set(
            generate_schedule(
                deal.rate_spec.payment_rule,
                after_date=deal.report_date,
                end_date=deal.maturity_date,
                include_end_date=True,
            )
        )

    else:
        interest_dates = {
            payment.date
            for payment in principal_schedule
        }

    interest_dates.add(deal.maturity_date)

    event_dates = sorted(
        set(principal_by_date)
        | set(interest_dates)
        | {deal.maturity_date}
    )

    balance = deal.outstanding_principal
    accrued_interest = deal.accrued_interest or Decimal(0)

    accrual_start = deal.report_date
    interest_period_start = deal.report_date

    result = []

    for event_date in event_dates:
        period_rate = fixed_period_rate(
            deal,
            accrual_start,
            event_date,
        )

        accrued_interest += balance * period_rate
        principal_cf = principal_by_date.get(
            event_date,
            Decimal(0),
        )
        balance_before = balance
        balance_after = balance_before - principal_cf

        balance_after = _round_money(balance_after)
        if event_date in interest_dates:
            interest_cf = _round_money(accrued_interest)
            accrued_interest = Decimal(0)

            cashflow_interest_start = interest_period_start
            cashflow_interest_end = event_date
            interest_period_start = event_date
        else:
            interest_cf = Decimal(0)

            cashflow_interest_start = event_date
            cashflow_interest_end = event_date

        result.append(
            CashFlow(
                deal_id=deal.deal_id,
                cashflow_date=event_date,
                currency=deal.currency,

                interest_period_start=cashflow_interest_start,
                interest_period_end=cashflow_interest_end,

                principal_cf=principal_cf,
                interest_cf=interest_cf,

                balance_before=balance_before,
                balance_after=balance_after,
            )
        )
        balance = balance_after
        accrual_start = event_date

    return tuple(result)