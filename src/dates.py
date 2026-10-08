import calendar
import re
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from src.models import ScheduleRule


_PERIOD_PATTERN = re.compile(r"(?P<count>[1-9]\d*)(?P<unit>[MD])")


def get_correct_date(day_num: int, dt: date) -> date:
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    if day_num == -1:
        day = last_day
    elif 1 <= day_num <= 31:
        day = min(day_num, last_day)
    else:
        raise ValueError(f"invalid day number: {day_num}")
    return date(dt.year, dt.month, day)


def parse_period(period: str) -> relativedelta:
    match = _PERIOD_PATTERN.fullmatch(period)
    if match is None:
        raise ValueError(f"unsupported period: {period!r}")

    count = int(match.group("count"))
    if match.group("unit") == "M":
        return relativedelta(months=count)
    return relativedelta(days=count)


def generate_schedule(
    rule: ScheduleRule,
    after_date: date,
    end_date: date,
    *,
    include_end_date: bool,
) -> tuple[date, ...]:
    if end_date <= after_date:
        return ()
    if rule.period is None:
        raise ValueError("schedule period is required")
    if rule.period == "ENDDATE":
        return (end_date,)
    if rule.start_date is None:
        raise ValueError(f"start date is required for period {rule.period!r}")

    match = _PERIOD_PATTERN.fullmatch(rule.period)
    if match is None:
        raise ValueError(f"unsupported period: {rule.period!r}")
    count = int(match.group("count"))

    if match.group("unit") == "M":
        dates = _generate_monthly_dates(
            anchor=rule.start_date,
            month_step=count,
            day_num=rule.day_num,
            after_date=after_date,
            end_date=end_date,
        )
    else:
        if rule.day_num is not None:
            raise ValueError("day_num is not supported for day periods")
        dates = _generate_daily_dates(
            anchor=rule.start_date,
            day_step=count,
            after_date=after_date,
            end_date=end_date,
        )

    if include_end_date and (not dates or dates[-1] != end_date):
        dates.append(end_date)
    return tuple(dates)


def _generate_monthly_dates(
    *,
    anchor: date,
    month_step: int,
    day_num: int | None,
    after_date: date,
    end_date: date,
) -> list[date]:
    requested_day = anchor.day if day_num is None else day_num
    if requested_day != -1 and not 1 <= requested_day <= 31:
        raise ValueError(f"invalid day number: {requested_day}")

    result: list[date] = []
    month_offset = 0
    while True:
        month = anchor + relativedelta(months=month_offset)
        candidate = get_correct_date(requested_day, month)
        if candidate > end_date:
            break
        if candidate >= anchor and candidate > after_date:
            result.append(candidate)
        month_offset += month_step
    return result


def _generate_daily_dates(
    *,
    anchor: date,
    day_step: int,
    after_date: date,
    end_date: date,
) -> list[date]:
    result: list[date] = []
    candidate = anchor
    while candidate <= end_date:
        if candidate > after_date:
            result.append(candidate)
        candidate += timedelta(days=day_step)
    return result

def year_fraction(start_date: date, end_date: date, convention: str) -> Decimal:
    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date")

    if end_date == start_date:
        return Decimal(0)

    if convention == "ACT/365":
        days = (end_date - start_date).days
        return Decimal(days) / Decimal(365)
    if convention not in {"ACT/ACT", "ACT/ACT ISDA"}:
        raise ValueError(f"unsupported day-count convention: {convention!r}")

    result = Decimal(0)
    period_start = start_date
    while period_start < end_date:
        next_year = date(period_start.year + 1, 1, 1)
        period_end = min(end_date, next_year)
        actual_days = (period_end - period_start).days
        days_in_year = 366 if calendar.isleap(period_start.year) else 365
        result += Decimal(actual_days) / Decimal(days_in_year)
        period_start = period_end
    return result
