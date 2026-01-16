# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Canadian T1 Decision Engine (Logic Core)
# File: backend/logic/t1_engine.py
# ------------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .rules_registry import RulesRegistry, RulesRegistryError, get_year_config, load_rules_registry, read_decimal


MoneyLike = Union[int, float, str, Decimal]


def D(x: MoneyLike) -> Decimal:
    """Safe Decimal conversion."""
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def money(x: MoneyLike) -> Decimal:
    """Quantize to cents."""
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class IncomeType(str, Enum):
    EMPLOYMENT = "EMPLOYMENT"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    CAPITAL_GAINS = "CAPITAL_GAINS"
    INTEREST = "INTEREST"
    FOREIGN_INCOME = "FOREIGN_INCOME"
    DIVIDENDS_ELIGIBLE_TAXABLE = "DIVIDENDS_ELIGIBLE_TAXABLE"
    DIVIDENDS_NON_ELIGIBLE_TAXABLE = "DIVIDENDS_NON_ELIGIBLE_TAXABLE"
    OTHER = "OTHER"

    @staticmethod
    def normalize(value: Union["IncomeType", str]) -> "IncomeType":
        if isinstance(value, IncomeType):
            return value
        v = str(value).strip().upper()
        try:
            return IncomeType(v)
        except ValueError:
            return IncomeType.OTHER


@dataclass(frozen=True)
class TaxConfig:
    tax_year: int
    fed_brackets: List[Tuple[Decimal, Decimal]]
    capital_gains_inclusion_rate: Decimal
    rrsp_percent_limit: Decimal
    rrsp_dollar_limit: Decimal


def _parse_brackets(year_cfg: Dict[str, Any]) -> List[Tuple[Decimal, Decimal]]:
    fed = year_cfg.get("federal", {})
    brackets = fed.get("brackets", [])
    parsed = []
    for b in brackets:
        up_to = Decimal("999999999999.99") if str(b["up_to"]).lower() in ["inf", "infinity"] else D(b["up_to"])
        rate = D(b["rate"])
        parsed.append((up_to, rate))
    return parsed


def tax_config_from_registry(registry: RulesRegistry, tax_year: int) -> TaxConfig:
    year_cfg = get_year_config(registry, tax_year)
    brackets = _parse_brackets(year_cfg)
    cg_rate = read_decimal(year_cfg, "capital_gains.default_inclusion_rate")
    rrsp_percent = read_decimal(year_cfg, "rrsp.percent_limit")
    rrsp_dollar = money(read_decimal(year_cfg, "rrsp.dollar_limit"))
    
    return TaxConfig(
        tax_year=tax_year,
        fed_brackets=brackets,
        capital_gains_inclusion_rate=cg_rate,
        rrsp_percent_limit=rrsp_percent,
        rrsp_dollar_limit=rrsp_dollar,
    )


class T1DecisionEngine:
    def __init__(self, tax_year: int = 2024, registry: Optional[RulesRegistry] = None):
        self.tax_year = tax_year
        self.registry = registry or load_rules_registry()
        self.cfg = tax_config_from_registry(self.registry, tax_year)

    def process_income_stream(self, income_type: Union[IncomeType, str], raw_amount: MoneyLike) -> Dict[str, Any]:
        """Normalize raw money into taxable money."""
        itype = IncomeType.normalize(income_type)
        amt = money(raw_amount)
        
        # Default response structure (ensures 'taxable_amount' always exists)
        response = {
            "status": "OK",
            "tax_year": self.cfg.tax_year,
            "income_type": itype.value,
            "original_amount": str(amt),
            "taxable_amount": str(amt),  # Default: 100% inclusion
            "logic_applied": "Standard inclusion (100%).",
            "meta": {}
        }

        if itype == IncomeType.CAPITAL_GAINS:
            rate = self.cfg.capital_gains_inclusion_rate
            taxable = money(amt * rate)
            response["taxable_amount"] = str(taxable)
            response["logic_applied"] = f"Capital gain inclusion rate applied: {rate}"

        elif itype == IncomeType.SELF_EMPLOYED:
            response["logic_applied"] = "Self-employment income: taxable at 100%."

        elif itype == IncomeType.EMPLOYMENT:
            response["logic_applied"] = "Employment income: taxable at 100%."
            
        elif itype == IncomeType.OTHER:
            response["status"] = "REVIEW"
            response["logic_applied"] = "Unmapped income type; defaulted to fully taxable."

        return response

    def calculate_federal_tax(self, taxable_income: MoneyLike, return_breakdown: bool = False) -> Union[Decimal, Dict[str, Any]]:
        income = money(taxable_income)
        remaining = income
        previous_limit = Decimal("0.00")
        tax_owing = Decimal("0.00")
        breakdown = []

        for upper, rate in self.cfg.fed_brackets:
            if remaining <= 0:
                break
            bracket_span = upper - previous_limit
            in_bracket = min(remaining, bracket_span)
            chunk_tax = money(in_bracket * rate)
            tax_owing += chunk_tax
            
            breakdown.append({
                "rate": str(rate),
                "taxable_in_bracket": str(in_bracket),
                "tax_for_bracket": str(chunk_tax)
            })
            remaining -= in_bracket
            previous_limit = upper

        tax_owing = money(tax_owing)
        
        if return_breakdown:
            return {
                "federal_tax_before_credits": str(tax_owing),
                "bracket_breakdown": breakdown
            }
        return tax_owing