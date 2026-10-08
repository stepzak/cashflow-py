from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from src.dates import generate_schedule
from src.models import CashFlow, Deal, PrincipalPayment, RateSpec
from src.principal import _round_money, build_principal_schedule
from src.rates import full_period_rate


def build_cashflows(deal: Deal) -> tuple[CashFlow, ...]:
    principal_schedule = build_principal_schedule(deal)
    principal_by_date: dict[date, Decimal] = defaultdict(Decimal)
    for payment in principal_schedule:
        principal_by_date[payment.date] += payment.amount

    main_interest_dates = _interest_payment_dates(
        deal,
        deal.rate_spec,
        principal_schedule,
        explicit_dates=deal.interest_payment_dates,
    )

    sub_spec = deal.sub_rate_spec
    if sub_spec is None:
        sub_interest_dates: set[date] = set()
        sub_accrual_start = None
    else:
        sub_interest_dates = _interest_payment_dates(
            deal,
            sub_spec,
            principal_schedule,
        )
        sub_accrual_start = _rate_accrual_start(deal, sub_spec)

    event_dates = sorted(
        set(principal_by_date)
        | main_interest_dates
        | sub_interest_dates
        | {deal.maturity_date}
    )

    balance = deal.outstanding_principal
    main_accrued_interest = deal.accrued_interest or Decimal(0)
    sub_accrued_interest = Decimal(0)
    accrual_start = deal.report_date
    main_interest_period_start = deal.report_date
    sub_interest_period_start = sub_accrual_start
    result: list[CashFlow] = []

    for event_date in event_dates:
        main_period_rate = full_period_rate(
            deal,
            accrual_start,
            event_date,
            rate_spec=deal.rate_spec,
        )
        main_accrued_interest += balance * main_period_rate

        if (
            sub_spec is not None
            and sub_accrual_start is not None
            and event_date > sub_accrual_start
        ):
            sub_period_start = max(accrual_start, sub_accrual_start)
            sub_period_rate = full_period_rate(
                deal,
                sub_period_start,
                event_date,
                rate_spec=sub_spec,
            )
            sub_accrued_interest += balance * sub_period_rate

        interest_cf = Decimal(0)
        paid_period_starts: list[date] = []

        if event_date in main_interest_dates:
            interest_cf += _round_money(main_accrued_interest)
            main_accrued_interest = Decimal(0)
            paid_period_starts.append(main_interest_period_start)
            main_interest_period_start = event_date

        if event_date in sub_interest_dates:
            interest_cf += _round_money(sub_accrued_interest)
            sub_accrued_interest = Decimal(0)
            if sub_interest_period_start is not None:
                paid_period_starts.append(sub_interest_period_start)
            sub_interest_period_start = event_date

        principal_cf = principal_by_date.get(event_date, Decimal(0))
        balance_before = balance
        balance_after = _round_money(balance_before - principal_cf)

        if paid_period_starts:
            cashflow_interest_start = min(paid_period_starts)
            cashflow_interest_end = event_date
        else:
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


def _interest_payment_dates(
    deal: Deal,
    rate_spec: RateSpec,
    principal_schedule: Sequence[PrincipalPayment],
    *,
    explicit_dates: Sequence[date] = (),
) -> set[date]:
    if explicit_dates:
        payment_dates = {
            payment_date
            for payment_date in explicit_dates
            if deal.report_date < payment_date <= deal.maturity_date
        }
    elif rate_spec.payment_rule is not None:
        payment_dates = set(
            generate_schedule(
                rate_spec.payment_rule,
                after_date=deal.report_date,
                end_date=deal.maturity_date,
                include_end_date=True,
            )
        )
    else:
        payment_dates = {
            payment.date
            for payment in principal_schedule
        }

    payment_dates.add(deal.maturity_date)
    return payment_dates


def _rate_accrual_start(
    deal: Deal,
    rate_spec: RateSpec,
) -> date:
    if (
        rate_spec.payment_rule is not None
        and rate_spec.payment_rule.start_date is not None
    ):
        return max(deal.report_date, rate_spec.payment_rule.start_date)
    return deal.report_date
