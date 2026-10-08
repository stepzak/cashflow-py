from collections.abc import Sequence
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.dates import generate_schedule
from src.models import Deal, PrincipalPayment


_CURRENCY_QUANTUM = Decimal("0.01")

def build_principal_schedule(deal: Deal) -> tuple[PrincipalPayment, ...]:
    if deal.outstanding_principal == 0:
        return ()

    if deal.principal_payments:
        return reconcile_explicit_payments(deal)

    if deal.discriminator == "SIMPLE":
        return (
            PrincipalPayment(
                date=deal.maturity_date,
                amount=deal.outstanding_principal,
            ),
        )

    if deal.discriminator == "RGM":
        payment_dates = principal_payment_dates(deal)
        return build_regular_principal_schedule(
            deal.outstanding_principal,
            payment_dates,
        )

    if deal.discriminator == "ANN":
        raise NotImplementedError("ANN requires period rates")

    raise ValueError(f"unsupported discriminator: {deal.discriminator!r}")


def principal_payment_dates(deal: Deal) -> tuple[date, ...]:
    if deal.principal_rule is None:
        return (deal.maturity_date,)
    return generate_schedule(
        deal.principal_rule,
        after_date=deal.report_date,
        end_date=deal.maturity_date,
        include_end_date=True,
    )


def build_regular_principal_schedule(
    principal: Decimal,
    payment_dates: Sequence[date],
) -> tuple[PrincipalPayment, ...]:
    if principal == 0:
        return ()
    if not payment_dates:
        raise ValueError("at least one payment date is required")

    direction = _direction(principal)
    remaining = _round_money(abs(principal))
    regular_amount = _round_money(remaining / len(payment_dates))
    result: list[PrincipalPayment] = []

    for index, payment_date in enumerate(payment_dates):
        if index == len(payment_dates) - 1:
            amount = remaining
        else:
            amount = min(regular_amount, remaining)
        amount = _round_money(amount)
        if amount != 0:
            result.append(
                PrincipalPayment(
                    date=payment_date,
                    amount=amount * direction,
                )
            )
        remaining = _round_money(remaining - amount)

    return tuple(result)


def reconcile_explicit_payments(deal: Deal) -> tuple[PrincipalPayment, ...]:
    direction = _direction(deal.outstanding_principal)
    grouped: dict[date, Decimal] = {}

    for payment in deal.principal_payments:
        if payment.date <= deal.report_date:
            continue
        if payment.date > deal.maturity_date:
            raise ValueError(
                f"principal payment date {payment.date} is after maturity "
                f"{deal.maturity_date}"
            )

        payment_magnitude = payment.amount * direction
        if payment_magnitude < 0:
            raise ValueError(
                "principal payment has a sign opposite to the balance on "
                f"{payment.date}: {payment.amount}"
            )
        grouped[payment.date] = (
            grouped.get(payment.date, Decimal(0)) + payment_magnitude
        )

    remaining = _round_money(abs(deal.outstanding_principal))
    result: list[PrincipalPayment] = []

    for payment_date, requested_amount in sorted(grouped.items()):
        if remaining == 0:
            break
        requested_amount = _round_money(requested_amount)
        amount = min(requested_amount, remaining)
        if amount > 0:
            result.append(
                PrincipalPayment(
                    date=payment_date,
                    amount=amount * direction,
                )
            )
            remaining = _round_money(remaining - amount)

    if remaining > 0:
        residual = remaining * direction
        if result and result[-1].date == deal.maturity_date:
            last_payment = result[-1]
            result[-1] = PrincipalPayment(
                date=last_payment.date,
                amount=_round_money(last_payment.amount + residual),
            )
        else:
            result.append(
                PrincipalPayment(
                    date=deal.maturity_date,
                    amount=residual,
                )
            )

    return tuple(result)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)


def _direction(value: Decimal) -> Decimal:
    return Decimal(-1) if value < 0 else Decimal(1)
