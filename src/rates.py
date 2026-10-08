from datetime import date
from decimal import Decimal

from src.dates import year_fraction
from src.models import Deal


def fixed_period_rate(
    deal: Deal,
    period_start: date,
    period_end: date,
) -> Decimal:
    if deal.rate_spec.rate_type != "FIXED": raise ValueError

    fraction = year_fraction(period_start, period_end, deal.day_count)
    return deal.interest_rate * fraction

def fixed_period_rates(
    deal: Deal,
    payment_dates: tuple[date, ...],
) -> tuple[Decimal, ...]:
    previous_date = deal.report_date
    l = []
    for payment_date in payment_dates:
        if payment_date <= previous_date:
            raise ValueError(
                "payment dates must be strictly increasing"
            )

        l.append(fixed_period_rate(deal, previous_date, payment_date))
        previous_date = payment_date
    return tuple(l)