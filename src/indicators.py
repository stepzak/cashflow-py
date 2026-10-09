import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from dateutil.relativedelta import relativedelta


_LAG_PATTERN = re.compile(r"(?P<count>[+-]?\d+)(?P<unit>[MD])")
_INDICATOR_FILES = {
    "CBKEY1M": Path(__file__).resolve().parent.parent / "data" / "cbkey1m.csv",
}


@dataclass(frozen=True, slots=True)
class IndicatorObservation:
    effective_date: date
    rate: Decimal


@lru_cache(maxsize=None)
def load_indicator_history(
    indicator: str,
) -> tuple[IndicatorObservation, ...]:
    try:
        path = _INDICATOR_FILES[indicator]
    except KeyError as error:
        raise ValueError(f"unsupported indicator: {indicator!r}") from error

    observations: list[IndicatorObservation] = []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        if reader.fieldnames != ["effective_date", "rate_percent"]:
            raise ValueError(
                f"invalid columns in {path}: {reader.fieldnames!r}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                effective_date = date.fromisoformat(row["effective_date"])
                rate = Decimal(row["rate_percent"]) / Decimal(100)
            except (TypeError, ValueError, ArithmeticError) as error:
                raise ValueError(
                    f"invalid indicator data in {path} at line {line_number}"
                ) from error

            if not rate.is_finite() or rate <= 0:
                raise ValueError(
                    f"indicator rate must be positive in {path} "
                    f"at line {line_number}"
                )
            if observations and effective_date <= observations[-1].effective_date:
                raise ValueError(
                    f"indicator dates must be strictly increasing in {path} "
                    f"at line {line_number}"
                )
            observations.append(IndicatorObservation(effective_date, rate))

    if not observations:
        raise ValueError(f"indicator history is empty: {path}")
    return tuple(observations)


def indicator_rate_on(
    indicator: str,
    fixing_date: date,
    valuation_date: date,
) -> Decimal:
    observation_date = min(fixing_date, valuation_date)
    applicable = [
        observation
        for observation in load_indicator_history(indicator)
        if observation.effective_date <= observation_date
    ]
    if not applicable:
        raise ValueError(
            f"CBKEY1M is unavailable on {observation_date.isoformat()}"
        )
    return applicable[-1].rate


def apply_indicator_lag(
    fixing_date: date,
    lag: str | None,
) -> date:
    if lag is None:
        return fixing_date

    match = _LAG_PATTERN.fullmatch(lag)
    if match is None:
        raise ValueError(f"unsupported indicator lag: {lag!r}")

    count = int(match.group("count"))
    if match.group("unit") == "M":
        return fixing_date + relativedelta(months=count)
    return fixing_date + relativedelta(days=count)
