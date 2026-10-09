from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.dates import year_fraction
from src.models import CashFlow, DiscountedCashFlow


_MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ZeroCouponNode:
    term: Decimal
    annual_rate: Decimal


@dataclass(frozen=True, slots=True)
class ZeroCouponCurve:
    valuation_date: date
    nodes: tuple[ZeroCouponNode, ...]

    def zero_rate(self, term: Decimal) -> Decimal:
        if term < 0:
            raise ValueError("term cannot be negative")
        if not self.nodes:
            raise ValueError("zero-coupon curve is empty")
        if term <= self.nodes[0].term:
            return self.nodes[0].annual_rate
        if term >= self.nodes[-1].term:
            return self.nodes[-1].annual_rate

        for left, right in zip(self.nodes, self.nodes[1:], strict=False):
            if left.term <= term <= right.term:
                weight = (term - left.term) / (right.term - left.term)
                return left.annual_rate + weight * (
                    right.annual_rate - left.annual_rate
                )

        raise ValueError(f"cannot interpolate zero rate for term {term}")

    def discount_factor(self, cashflow_date: date) -> Decimal:
        term = year_fraction(
            self.valuation_date,
            cashflow_date,
            "ACT/365",
        )
        zero_rate = self.zero_rate(term)
        return (-zero_rate * term).exp()


def cbr_zero_coupon_curve(valuation_date: date) -> ZeroCouponCurve:
    if valuation_date != date(2022, 8, 31):
        raise ValueError(
            "zero-coupon curve is unavailable for "
            f"{valuation_date.isoformat()}"
        )

    values = (
        ("0.25", "0.0771"),
        ("0.50", "0.0768"),
        ("0.75", "0.0768"),
        ("1.00", "0.0769"),
        ("2.00", "0.0784"),
        ("3.00", "0.0805"),
        ("5.00", "0.0851"),
        ("7.00", "0.0884"),
        ("10.00", "0.0911"),
        ("15.00", "0.0932"),
        ("20.00", "0.0943"),
        ("30.00", "0.0956"),
    )
    return ZeroCouponCurve(
        valuation_date=valuation_date,
        nodes=tuple(
            ZeroCouponNode(Decimal(term), Decimal(rate))
            for term, rate in values
        ),
    )


def discount_cashflow(
    cashflow: CashFlow,
    curve: ZeroCouponCurve,
) -> DiscountedCashFlow:
    factor = curve.discount_factor(cashflow.cashflow_date)
    discounted_principal = _round_money(cashflow.principal_cf * factor)
    discounted_interest = _round_money(cashflow.interest_cf * factor)
    return DiscountedCashFlow(
        cashflow=cashflow,
        discount_factor=factor,
        discounted_principal_cf=discounted_principal,
        discounted_interest_cf=discounted_interest,
        present_value=_round_money(
            discounted_principal + discounted_interest
        ),
    )


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
