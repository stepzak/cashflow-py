from dataclasses import dataclass, Field
from datetime import date
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PrincipalPayment:
    date: date
    amount: Decimal

@dataclass
class Deal:
    deal_id: int
    report_date: date
    maturity_date: date
    outstanding_principal: Decimal
    interest_rate: Decimal
    rate_type: str
    discriminator: str
    day_count: str
    currency: str
    principal_payments: list[PrincipalPayment] = Field(default_factory=list)

@dataclass
class CashFlow:
    deal_id: int
    date_: date
    currency: str

    interest_period_start: date
    interest_period_end: date

    principal_cf: Decimal
    interest_cf: Decimal

    balance_before: Decimal
    balance_after: Decimal