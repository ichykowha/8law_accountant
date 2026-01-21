from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple


Money = Decimal


def _d(v: Any) -> Money:
    if v is None:
        return Decimal("0.00")
    if isinstance(v, Decimal):
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: str  # ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    normal_balance: str  # DEBIT or CREDIT


@dataclass
class JournalLine:
    account_code: str
    account_name: str
    debit: Money = field(default_factory=lambda: Decimal("0.00"))
    credit: Money = field(default_factory=lambda: Decimal("0.00"))
    memo: str = ""

    def __post_init__(self) -> None:
        self.debit = _d(self.debit)
        self.credit = _d(self.credit)

        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit/Credit cannot be negative.")
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A single journal line cannot have both debit and credit amounts.")


@dataclass
class JournalEntry:
    entry_date: date
    description: str
    lines: List[JournalLine]
    source: str = "user"
    references: Dict[str, Any] = field(default_factory=dict)  # citations, doc ids, etc.

    def total_debits(self) -> Money:
        return sum((ln.debit for ln in self.lines), Decimal("0.00")).quantize(Decimal("0.01"))

    def total_credits(self) -> Money:
        return sum((ln.credit for ln in self.lines), Decimal("0.00")).quantize(Decimal("0.01"))

    def is_balanced(self) -> bool:
        return self.total_debits() == self.total_credits()

    def validate(self, chart_of_accounts: Optional[Dict[str, Account]] = None) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not self.description.strip():
            errors.append("JournalEntry.description is empty.")

        if not self.lines:
            errors.append("JournalEntry.lines is empty.")
            return False, errors

        for i, ln in enumerate(self.lines):
            if ln.debit == Decimal("0.00") and ln.credit == Decimal("0.00"):
                errors.append(f"Line {i} has zero debit and zero credit.")

            if chart_of_accounts is not None:
                if ln.account_code not in chart_of_accounts:
                    errors.append(f"Line {i} account_code not in COA: {ln.account_code}")

        if not self.is_balanced():
            errors.append(f"Entry not balanced: debits={self.total_debits()} credits={self.total_credits()}")

        return (len(errors) == 0), errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_date": self.entry_date.isoformat(),
            "description": self.description,
            "source": self.source,
            "references": self.references,
            "lines": [
                {
                    "account_code": ln.account_code,
                    "account_name": ln.account_name,
                    "debit": str(ln.debit),
                    "credit": str(ln.credit),
                    "memo": ln.memo,
                }
                for ln in self.lines
            ],
            "total_debits": str(self.total_debits()),
            "total_credits": str(self.total_credits()),
            "balanced": self.is_balanced(),
        }


def default_coa() -> Dict[str, Account]:
    """
    Minimal COA for bookkeeping workflows. Expand later per client.
    """
    coa = [
        Account("1000", "Cash", "ASSET", "DEBIT"),
        Account("1060", "Bank", "ASSET", "DEBIT"),
        Account("1100", "Accounts Receivable", "ASSET", "DEBIT"),
        Account("2000", "Accounts Payable", "LIABILITY", "CREDIT"),
        Account("2100", "GST/HST Payable", "LIABILITY", "CREDIT"),
        Account("2200", "CPP Payable", "LIABILITY", "CREDIT"),
        Account("2210", "EI Payable", "LIABILITY", "CREDIT"),
        Account("3000", "Owner's Equity", "EQUITY", "CREDIT"),
        Account("4000", "Revenue", "REVENUE", "CREDIT"),
        Account("5000", "Cost of Goods Sold", "EXPENSE", "DEBIT"),
        Account("6100", "Office Supplies", "EXPENSE", "DEBIT"),
        Account("6200", "Meals & Entertainment", "EXPENSE", "DEBIT"),
        Account("6300", "Travel", "EXPENSE", "DEBIT"),
        Account("6400", "Vehicle Expense", "EXPENSE", "DEBIT"),
        Account("6500", "Advertising & Marketing", "EXPENSE", "DEBIT"),
        Account("6600", "Professional Fees", "EXPENSE", "DEBIT"),
        Account("6700", "Rent", "EXPENSE", "DEBIT"),
        Account("6800", "Utilities", "EXPENSE", "DEBIT"),
        Account("6900", "Wages Expense", "EXPENSE", "DEBIT"),
    ]
    return {a.code: a for a in coa}
