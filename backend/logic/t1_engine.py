
# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Canadian T1 Decision Engine (Logic Core)
# File: backend/logic/t1_engine.py
# ------------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# ------------------------------------------------------------------------------
# 1. CORE TYPES & HELPERS
# ------------------------------------------------------------------------------

MoneyLike = Union[int, float, str, Decimal]

def D(x: MoneyLike) -> Decimal:
    """Safe Decimal conversion (avoid float artifacts)."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(str(x))
    return Decimal(x)

def money(x: MoneyLike) -> Decimal:
    """Quantize to cents using conventional rounding."""
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class IncomeType(str, Enum):
    CAPITAL_GAINS = "CAPITAL_GAINS"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    EMPLOYMENT = "EMPLOYMENT"
    DIVIDENDS = "DIVIDENDS" 
    OTHER = "OTHER"

    @staticmethod
    def normalize(value: Union["IncomeType", str]) -> "IncomeType":
        if isinstance(value, IncomeType):
            return value
        v = (value or "").strip().upper()
        synonyms = {
            "T4": "EMPLOYMENT",
            "EMPLOYMENT_INCOME": "EMPLOYMENT",
            "BUSINESS_INCOME": "SELF_EMPLOYED",
            "SELF_EMPLOYMENT": "SELF_EMPLOYED",
            "CAP_GAIN": "CAPITAL_GAINS",
            "CAPITALGAIN": "CAPITAL_GAINS",
        }
        v = synonyms.get(v, v)
        try:
            return IncomeType(v)
        except ValueError:
            return IncomeType.OTHER

class Province(str, Enum):
    ON = "ON"
    BC = "BC"
    AB = "AB"
    QC = "QC" # Note: QC has a separate tax system (Revenu Quebec), logic here approximates T1 Federal overlap.
    # Add others as needed

# ------------------------------------------------------------------------------
# 2. TAX RULES REGISTRY (VERSIONED)
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class TaxConfig:
    tax_year: int
    fed_brackets: List[Tuple[Decimal, Decimal]]
    prov_brackets: Dict[Province, List[Tuple[Decimal, Decimal]]]
    capital_gains_inclusion_rate: Decimal
    rrsp_percent_limit: Decimal = Decimal("0.18")
    rrsp_annual_max: Decimal = Decimal("31560")  # 2024 max

# 2024 Tax Rules (Federal + Major Provinces)
# Source: CRA 2024 Indexed Brackets
TAX_RULES: Dict[int, TaxConfig] = {
    2024: TaxConfig(
        tax_year=2024,
        # Federal Brackets: (Upper Limit, Rate)
        fed_brackets=[
            (Decimal("55867.00"), Decimal("0.15")),
            (Decimal("111733.00"), Decimal("0.205")),
            (Decimal("173205.00"), Decimal("0.26")),
            (Decimal("246752.00"), Decimal("0.29")),
            (Decimal("999999999.99"), Decimal("0.33")),
        ],
        # Provincial Brackets (Simplified 2024 projections)
        prov_brackets={
            Province.ON: [
                (Decimal("51446.00"), Decimal("0.0505")),
                (Decimal("102894.00"), Decimal("0.0915")),
                (Decimal("150000.00"), Decimal("0.1116")),
                (Decimal("220000.00"), Decimal("0.1216")),
                (Decimal("999999999.99"), Decimal("0.1316")),
            ],
            Province.BC: [
                (Decimal("47937.00"), Decimal("0.0506")),
                (Decimal("95875.00"), Decimal("0.077")),
                (Decimal("110076.00"), Decimal("0.105")),
                (Decimal("133664.00"), Decimal("0.1229")),
                (Decimal("181232.00"), Decimal("0.147")),
                (Decimal("999999999.99"), Decimal("0.168")), # simplified top tiers
            ],
            Province.AB: [
                (Decimal("148269.00"), Decimal("0.10")),
                (Decimal("177922.00"), Decimal("0.12")),
                (Decimal("237230.00"), Decimal("0.13")),
                (Decimal("355845.00"), Decimal("0.14")),
                (Decimal("999999999.99"), Decimal("0.15")),
            ]
        },
        capital_gains_inclusion_rate=Decimal("0.50"),
        rrsp_annual_max=Decimal("31560")
    )
}

# ------------------------------------------------------------------------------
# 3. NOA DATA STRUCTURE
# ------------------------------------------------------------------------------

@dataclass
class NoticeOfAssessment:
    """
    Represents data parsed from the user's uploaded NOA (Last Year).
    This is critical for accurate RRSP calculation.
    """
    tax_year: int
    earned_income_previous_year: Decimal
    rrsp_deduction_limit_current_year: Decimal # The "Room" CRA says you have
    unused_contributions: Decimal = Decimal("0.00") # Contributions made but not deducted

# ------------------------------------------------------------------------------
# 4. THE DECISION ENGINE
# ------------------------------------------------------------------------------

class T1DecisionEngine:
    def __init__(self, tax_year: int = 2024):
        if tax_year not in TAX_RULES:
            raise ValueError(f"Unsupported tax_year={tax_year}.")
        self.cfg = TAX_RULES[tax_year]

    def process_income_stream(self, income_type: Union[IncomeType, str], raw_amount: MoneyLike) -> Dict[str, Any]:
        """
        Calculates 'Taxable Income' based on Canadian inclusions.
        """
        itype = IncomeType.normalize(income_type)
        amt = money(raw_amount)

        if itype == IncomeType.CAPITAL_GAINS:
            rate = self.cfg.capital_gains_inclusion_rate
            taxable = money(amt * rate)
            note = f"Capital gains inclusion (Rate: {rate})"
        elif itype == IncomeType.EMPLOYMENT:
            taxable = amt
            note = "Fully taxable Employment Income"
        else:
            taxable = amt
            note = "Standard Income"

        return {
            "type": itype.value,
            "original": str(amt),
            "taxable": str(taxable),
            "note": note
        }

    def calculate_combined_tax(
        self, 
        taxable_income: MoneyLike, 
        province: Union[Province, str] = Province.ON
    ) -> Dict[str, Any]:
        """
        Calculates BOTH Federal and Provincial tax.
        """
        income = money(taxable_income)
        
        # 1. Calculate Federal
        fed_tax = self._calculate_brackets(income, self.cfg.fed_brackets)
        
        # 2. Calculate Provincial
        prov_enum = Province(province) if isinstance(province, str) else province
        if prov_enum not in self.cfg.prov_brackets:
            raise ValueError(f"Provincial rates for {prov_enum} not defined in config.")
            
        prov_tax = self._calculate_brackets(income, self.cfg.prov_brackets[prov_enum])
        
        total_tax = fed_tax + prov_tax
        
        return {
            "province": prov_enum.value,
            "taxable_income": str(income),
            "federal_tax": str(fed_tax),
            "provincial_tax": str(prov_tax),
            "total_estimated_tax": str(total_tax),
            "average_tax_rate": str(money((total_tax / income) * 100)) if income > 0 else "0.00"
        }

    def _calculate_brackets(self, income: Decimal, brackets: List[Tuple[Decimal, Decimal]]) -> Decimal:
        """Internal helper for progressive bracket math."""
        remaining = income
        previous_limit = Decimal("0.00")
        total_tax = Decimal("0.00")

        for limit, rate in brackets:
            if remaining <= 0:
                break
            
            bracket_span = limit - previous_limit
            taxable_in_bracket = min(remaining, bracket_span)
            
            total_tax += taxable_in_bracket * rate
            
            remaining -= taxable_in_bracket
            previous_limit = limit
            
        return money(total_tax)

    def optimize_rrsp_dynamic(
        self, 
        contribution_amount: MoneyLike, 
        noa_data: Optional[NoticeOfAssessment] = None,
        estimated_current_income: MoneyLike = 0
    ) -> Dict[str, Any]:
        """
        RRSP LOGIC V2:
        If NOA is present, use exact CRA limit.
        If NOA is missing, estimate based on 18% of current income (Fallback).
        """
        contrib = money(contribution_amount)

        if noa_data:
            # ACCURATE PATH: We have the user's uploaded NOA
            limit = noa_data.rrsp_deduction_limit_current_year
            source = "CRA Notice of Assessment (Exact)"
        else:
            # FALLBACK PATH: We guess based on current income
            # (Note: This is risky because it ignores previous years, but necessary if no NOA)
            est_income = money(estimated_current_income)
            calc_limit = est_income * self.cfg.rrsp_percent_limit
            limit = min(calc_limit, self.cfg.rrsp_annual_max)
            source = "Estimated (18% of Current Income) - UPLOAD NOA FOR EXACT LIMIT"

        # The 'Buffer' - CRA allows $2,000 over-contribution without immediate penalty
        over_contribution_buffer = Decimal("2000.00")
        
        if contrib > (limit + over_contribution_buffer):
            status = "DANGER"
            msg = f"Over-contribution of ${contrib - limit}. Penalty of 1%/month applies."
        elif contrib > limit:
            status = "WARNING"
            msg = f"Exceeds deduction limit by ${contrib - limit}, but within $2k safety buffer."
        else:
            status = "OPTIMAL"
            msg = "Contribution is within safe limits."

        return {
            "status": status,
            "contribution_amount": str(contrib),
            "deduction_limit": str(limit),
            "limit_source": source,
            "message": msg
        }
