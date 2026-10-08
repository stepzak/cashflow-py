import csv
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.models import DatedRate, Deal, PrincipalPayment, RateSpec, ScheduleRule


def parse_optional[T](value: str, converter: Callable[[str], T]) -> T | None:
    value = value.strip()
    if not value:
        return None
    return converter(value)


def parse_date(value: str) -> date:
    value = value.strip()
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported date format: {value!r}")


def parse_decimal(value: str) -> Decimal:
    return Decimal(value.strip())


def parse_bool(value: str) -> bool:
    value = value.strip()
    if value == "1":
        return True
    if value == "0":
        return False
    raise ValueError(f"expected 0 or 1, got {value!r}")


def parse_schedule_rule(
    row: dict[str, str],
    *,
    start_column: str,
    period_column: str,
    day_column: str,
) -> ScheduleRule | None:
    raw_values = (
        row[start_column],
        row[period_column],
        row[day_column],
    )
    if not any(value.strip() for value in raw_values):
        return None

    return ScheduleRule(
        start_date=parse_optional(row[start_column], parse_date),
        period=parse_optional(row[period_column], str),
        day_num=parse_optional(row[day_column], int),
    )


def parse_date_schedule(value: str) -> tuple[date, ...]:
    value = value.strip()
    if not value:
        return ()
    return tuple(parse_date(item) for item in value.split())


def parse_dated_rates(value: str) -> tuple[DatedRate, ...]:
    value = value.strip()
    if not value:
        return ()

    result: list[DatedRate] = []
    for item in value.split():
        try:
            raw_date, raw_rate = item.split(",", maxsplit=1)
        except ValueError as error:
            raise ValueError(f"invalid dated rate: {item!r}") from error
        result.append(
            DatedRate(
                date=parse_date(raw_date),
                rate=parse_decimal(raw_rate),
            )
        )
    return tuple(result)


def parse_principal_payments(value: str) -> tuple[PrincipalPayment, ...]:
    value = value.strip()
    if not value:
        return ()

    result: list[PrincipalPayment] = []
    for item in value.split():
        try:
            raw_date, raw_amount = item.split(",", maxsplit=1)
        except ValueError as error:
            raise ValueError(f"invalid principal payment: {item!r}") from error
        result.append(
            PrincipalPayment(
                date=parse_date(raw_date),
                amount=parse_decimal(raw_amount),
            )
        )
    return tuple(result)


def parse_main_rate_spec(row: dict[str, str]) -> RateSpec:
    return RateSpec(
        rate_type=_required(row, "rate_type_cd", str),
        interest_rate=_required(row, "interest_rate", parse_decimal),
        indicator=_optional(row, "base_indicator", str),
        indicator_rate=_optional(row, "base_indicator_rate", parse_decimal),
        payment_rule=parse_schedule_rule(
            row,
            start_column="interest_payment_rule_start_dttm",
            period_column="interest_payment_rule_period_cd",
            day_column="interest_payment_rule_day_num",
        ),
        repricing_rule=parse_schedule_rule(
            row,
            start_column="repricing_rule_start_dttm",
            period_column="repricing_rule_period_cd",
            day_column="repricing_rule_day_num",
        ),
        repricing_dates=_required(
            row,
            "repricing_dttm_schedule",
            parse_date_schedule,
            allow_empty=True,
        ),
        rate_schedule=_required(
            row,
            "repricing_dttm_rate_schedule",
            parse_dated_rates,
            allow_empty=True,
        ),
        fixed_rate_schedule=_required(
            row,
            "repricing_dttm_rate_schedule_fixed",
            parse_dated_rates,
            allow_empty=True,
        ),
        cap=_optional(row, "cap_limit_interest_rate", parse_decimal),
        floor=_optional(row, "floor_limit_interest_rate", parse_decimal),
        indicator_lag=_optional(row, "indicator_lag_cd", str),
    )


def parse_sub_rate_spec(row: dict[str, str]) -> RateSpec | None:
    if not row["sub_rate_type_cd"].strip():
        return None

    return RateSpec(
        rate_type=_required(row, "sub_rate_type_cd", str),
        interest_rate=_required(row, "sub_interest_rate", parse_decimal),
        indicator=_optional(row, "sub_float_indicator", str),
        indicator_rate=None,
        payment_rule=parse_schedule_rule(
            row,
            start_column="sub_payment_rule_start_dttm",
            period_column="sub_payment_rule_period_cd",
            day_column="sub_payment_rule_day_num",
        ),
        repricing_rule=parse_schedule_rule(
            row,
            start_column="sub_repricing_rule_start_dttm",
            period_column="sub_repricing_rule_period_cd",
            day_column="sub_repricing_rule_day_num",
        ),
        cap=_optional(row, "sub_cap_limit_interest_rate", parse_decimal),
        floor=_optional(row, "sub_floor_limit_interest_rate", parse_decimal),
        coefficient=_optional(row, "sub_coeff_index", parse_decimal),
        indicator_lag=_optional(row, "sub_indicator_lag_cd", str),
        first_repricing_event=_optional(
            row,
            "sub_repricing_rule_first_event_flg",
            parse_bool,
        ),
    )


def parse_deal(row: dict[str, str]) -> Deal:
    deal_id = row.get("deal_id", "<missing>").strip() or "<missing>"
    try:
        report_date = _required(row, "report_dttm", parse_date)
        deal_report_date = _required(row, "deal_report_dttm", parse_date)
        if report_date != deal_report_date:
            raise ValueError(
                "report_dttm and deal_report_dttm differ: "
                f"{report_date} != {deal_report_date}"
            )

        return Deal(
            deal_id=_required(row, "deal_id", int),
            deal_date=_required(row, "deal_dttm", parse_date),
            report_date=report_date,
            maturity_date=_required(row, "maturity_dttm", parse_date),
            currency=_required(row, "currency_id", str),
            discriminator=_required(row, "discriminator", str),
            start_principal=_optional(
                row,
                "start_principal_amt",
                parse_decimal,
            ),
            outstanding_principal=_required(
                row,
                "current_principal_amt",
                parse_decimal,
            ),
            accrued_interest=_optional(
                row,
                "accrued_interest",
                parse_decimal,
            ),
            day_count=_required(row, "day_convention_cd", str),
            rate_spec=parse_main_rate_spec(row),
            sub_rate_spec=parse_sub_rate_spec(row),
            principal_rule=parse_schedule_rule(
                row,
                start_column="regular_payment_rule_start_dttm",
                period_column="regular_payment_rule_period_cd",
                day_column="regular_payment_rule_day_num",
            ),
            interest_payment_dates=_required(
                row,
                "interest_payment",
                parse_date_schedule,
                allow_empty=True,
            ),
            principal_payments=_required(
                row,
                "principal_payment",
                parse_principal_payments,
                allow_empty=True,
            ),
            product=_optional(row, "product", str),
            behavior_model=_optional(row, "behavior_model_cd", str),
        )
    except (KeyError, ValueError) as error:
        raise ValueError(f"deal_id={deal_id}: {error}") from error


def parse_deals(path: str | Path) -> list[Deal]:
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        deals = [parse_deal(row) for row in reader]

    deal_ids = [deal.deal_id for deal in deals]
    duplicate_ids = sorted(
        deal_id
        for deal_id in set(deal_ids)
        if deal_ids.count(deal_id) > 1
    )
    if duplicate_ids:
        raise ValueError(f"duplicate deal_id values: {duplicate_ids}")
    return deals


def _required[T](
    row: dict[str, str],
    column: str,
    converter: Callable[[str], T],
    *,
    allow_empty: bool = False,
) -> T:
    raw_value = row[column]
    if not raw_value.strip() and not allow_empty:
        raise ValueError(f"column {column!r} is required")
    try:
        return converter(raw_value.strip())
    except ValueError as error:
        raise ValueError(f"column {column!r}: {error}") from error


def _optional[T](
    row: dict[str, str],
    column: str,
    converter: Callable[[str], T],
) -> T | None:
    try:
        return parse_optional(row[column], converter)
    except ValueError as error:
        raise ValueError(f"column {column!r}: {error}") from error
