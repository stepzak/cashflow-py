from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ScheduleRule:
    start_date: date | None
    period: str | None
    day_num: int | None


@dataclass(frozen=True, slots=True)
class DatedRate:
    date: date
    rate: Decimal


@dataclass(frozen=True, slots=True)
class PrincipalPayment:
    date: date
    amount: Decimal

@dataclass(frozen=True, slots=True)
class RateSpec:
    rate_type: str
    interest_rate: Decimal
    indicator: str | None
    indicator_rate: Decimal | None

    payment_rule: ScheduleRule | None = None
    repricing_rule: ScheduleRule | None = None
    repricing_dates: tuple[date, ...] = ()
    rate_schedule: tuple[DatedRate, ...] = ()
    fixed_rate_schedule: tuple[DatedRate, ...] = ()

    cap: Decimal | None = None
    floor: Decimal | None = None
    coefficient: Decimal | None = None
    indicator_lag: str | None = None
    first_repricing_event: bool | None = None


@dataclass(frozen=True, slots=True)
class Deal:
    deal_id: int
    deal_date: date
    report_date: date
    maturity_date: date
    currency: str
    discriminator: str

    start_principal: Decimal | None
    outstanding_principal: Decimal
    accrued_interest: Decimal | None
    day_count: str

    rate_spec: RateSpec
    sub_rate_spec: RateSpec | None
    principal_rule: ScheduleRule | None

    interest_payment_dates: tuple[date, ...] = ()
    principal_payments: tuple[PrincipalPayment, ...] = ()

    product: str | None = None
    behavior_model: str | None = None

    @property
    def interest_rate(self) -> Decimal:
        return self.rate_spec.interest_rate

    @property
    def rate_type(self) -> str:
        return self.rate_spec.rate_type


@dataclass(frozen=True, slots=True)
class CashFlow:
    deal_id: int
    cashflow_date: date
    currency: str

    interest_period_start: date
    interest_period_end: date

    principal_cf: Decimal
    interest_cf: Decimal

    balance_before: Decimal
    balance_after: Decimal


@dataclass(frozen=True, slots=True)
class DiscountedCashFlow:
    cashflow: CashFlow
    discount_factor: Decimal
    discounted_principal_cf: Decimal
    discounted_interest_cf: Decimal
    present_value: Decimal
