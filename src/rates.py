from datetime import date
from decimal import Decimal

from src.dates import generate_schedule, year_fraction
from src.models import Deal, RateSpec


def fixed_period_rate(
    deal: Deal,
    period_start: date,
    period_end: date,
) -> Decimal:
    if deal.rate_spec.rate_type != "FIXED":
        raise ValueError("fixed period rate requires a FIXED rate")
    return full_period_rate(deal, period_start, period_end)


def fixed_period_rates(
    deal: Deal,
    payment_dates: tuple[date, ...],
) -> tuple[Decimal, ...]:
    previous_date = deal.report_date
    result: list[Decimal] = []

    for payment_date in payment_dates:
        if payment_date <= previous_date:
            raise ValueError("payment dates must be strictly increasing")
        result.append(fixed_period_rate(deal, previous_date, payment_date))
        previous_date = payment_date

    return tuple(result)


def float_annual_rate(
    rate_spec: RateSpec,
    indicator_rate: Decimal,
) -> Decimal:
    coefficient = rate_spec.coefficient
    if coefficient is None:
        coefficient = Decimal(1)

    annual_rate = rate_spec.interest_rate + coefficient * indicator_rate
    return _apply_limits(rate_spec, annual_rate)


def repricing_dates_until(
    deal: Deal,
    end_date: date,
    *,
    rate_spec: RateSpec | None = None,
) -> tuple[date, ...]:
    spec = rate_spec or deal.rate_spec
    explicit_dates = {
        repricing_date
        for repricing_date in spec.repricing_dates
        if deal.report_date < repricing_date <= end_date
    }

    if spec.repricing_rule is not None and spec.repricing_rule.period is not None:
        generated = generate_schedule(
            spec.repricing_rule,
            after_date=deal.report_date,
            end_date=end_date,
            include_end_date=False,
        )
    else:
        generated = ()

    return tuple(sorted(explicit_dates | set(generated)))


def annual_rate_on(
    deal: Deal,
    effective_date: date,
    *,
    proj_indicator_rate: Decimal = Decimal("0.08"),
    rate_spec: RateSpec | None = None,
) -> Decimal:
    spec = rate_spec or deal.rate_spec
    scheduled_rate = _scheduled_rate_on(deal, spec, effective_date)
    if scheduled_rate is not None:
        return _apply_limits(spec, scheduled_rate)

    if spec.rate_type == "FIXED":
        return _apply_limits(spec, spec.interest_rate)
    if spec.rate_type != "FLOAT":
        raise ValueError(f"unsupported rate type: {spec.rate_type!r}")

    was_repriced = bool(
        repricing_dates_until(
            deal,
            effective_date,
            rate_spec=spec,
        )
    )
    if not was_repriced and spec.indicator_rate is not None:
        indicator_rate = spec.indicator_rate
    else:
        indicator_rate = proj_indicator_rate

    return float_annual_rate(spec, indicator_rate)


def full_period_rate(
    deal: Deal,
    period_start: date,
    period_end: date,
    *,
    projected_indicator_rate: Decimal = Decimal("0.08"),
    rate_spec: RateSpec | None = None,
) -> Decimal:
    if period_end < period_start:
        raise ValueError("period_end cannot be earlier than period_start")
    if period_end == period_start:
        return Decimal(0)

    spec = rate_spec or deal.rate_spec
    boundaries = {
        repricing_date
        for repricing_date in repricing_dates_until(
            deal,
            period_end,
            rate_spec=spec,
        )
        if period_start < repricing_date < period_end
    }
    boundaries.update(
        item.date
        for item in (*spec.rate_schedule, *spec.fixed_rate_schedule)
        if period_start < item.date < period_end
    )
    segment_dates = (period_start, *sorted(boundaries), period_end)

    result = Decimal(0)
    for segment_start, segment_end in zip(
        segment_dates,
        segment_dates[1:],
        strict=False,
    ):
        annual_rate = annual_rate_on(
            deal,
            segment_start,
            proj_indicator_rate=projected_indicator_rate,
            rate_spec=spec,
        )
        fraction = year_fraction(
            segment_start,
            segment_end,
            deal.day_count,
        )
        result += annual_rate * fraction

    return result


def _scheduled_rate_on(
    deal: Deal,
    rate_spec: RateSpec,
    effective_date: date,
) -> Decimal | None:
    applicable_rates = [
        item
        for item in (
            *rate_spec.rate_schedule,
            *rate_spec.fixed_rate_schedule,
        )
        if item.date <= effective_date
    ]
    if not applicable_rates:
        return None

    latest_rate = max(applicable_rates, key=lambda item: item.date)
    if rate_spec.rate_type == "FLOAT":
        later_repricing_exists = any(
            repricing_date > latest_rate.date
            for repricing_date in repricing_dates_until(
                deal,
                effective_date,
                rate_spec=rate_spec,
            )
        )
        if later_repricing_exists:
            return None

    return latest_rate.rate


def _apply_limits(
    rate_spec: RateSpec,
    annual_rate: Decimal,
) -> Decimal:
    if rate_spec.floor is not None:
        annual_rate = max(annual_rate, rate_spec.floor)
    if rate_spec.cap is not None:
        annual_rate = min(annual_rate, rate_spec.cap)
    return annual_rate
