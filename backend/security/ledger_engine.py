# ------------------------------------------------------------------------------
# 8law - Super Accountant
# Module: Ledger Engine (Accounting Journal + SHA-256 Immutability Chain)
# File: backend/logic/ledger_engine.py  (or backend/security/ledger_engine.py)
# ------------------------------------------------------------------------------

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =========================
# Accounting Ledger Models
# =========================

_DEC2 = Decimal("0.01")


def _now_iso() -> str:
    # ISO timestamp in UTC; stable and audit-friendly
    return datetime.now(timezone.utc).isoformat()


def _to_decimal(v: Any) -> Decimal:
    """
    Convert numeric-like values to Decimal safely.
    Accepts Decimal, int, float, or numeric strings.
    """
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int,)):
        return Decimal(v)
    if isinstance(v, float):
        # Float -> string to reduce binary float artifacts
        return Decimal(str(v))
    s = str(v).strip()
    if s == "":
        return Decimal("0")
    return Decimal(s)


def _q2(v: Decimal) -> Decimal:
    return v.quantize(_DEC2, rounding=ROUND_HALF_UP)


def default_coa() -> Dict[str, Dict[str, str]]:
    """
    Minimal Chart of Accounts (COA).
    You can extend this as 8law matures.
    Structure: {account_code: {"name": str, "type": str}}
    Types: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    """
    return {
        "1000": {"name": "Cash", "type": "ASSET"},
        "1100": {"name": "Accounts Receivable", "type": "ASSET"},
        "1200": {"name": "Inventory", "type": "ASSET"},
        "1300": {"name": "Prepaid Expenses", "type": "ASSET"},

        "2000": {"name": "Accounts Payable", "type": "LIABILITY"},
        "2100": {"name": "GST/HST Payable", "type": "LIABILITY"},
        "2200": {"name": "Payroll Liabilities", "type": "LIABILITY"},

        "3000": {"name": "Owner's Equity", "type": "EQUITY"},
        "3100": {"name": "Retained Earnings", "type": "EQUITY"},

        "4000": {"name": "Sales / Revenue", "type": "REVENUE"},
        "4100": {"name": "Service Revenue", "type": "REVENUE"},
        "4200": {"name": "Other Income", "type": "REVENUE"},

        "5000": {"name": "Cost of Goods Sold", "type": "EXPENSE"},
        "6000": {"name": "Office Expense", "type": "EXPENSE"},
        "6100": {"name": "Advertising Expense", "type": "EXPENSE"},
        "6200": {"name": "Travel Expense", "type": "EXPENSE"},
        "6300": {"name": "Professional Fees", "type": "EXPENSE"},
        "6400": {"name": "Rent Expense", "type": "EXPENSE"},
        "6500": {"name": "Utilities Expense", "type": "EXPENSE"},
    }


@dataclass(frozen=True)
class JournalLine:
    """
    One debit or credit line against an account.
    Exactly one of debit/credit must be > 0.
    """
    account: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    memo: str = ""

    def normalized(self) -> "JournalLine":
        d = _q2(_to_decimal(self.debit))
        c = _q2(_to_decimal(self.credit))
        return JournalLine(account=str(self.account).strip(), debit=d, credit=c, memo=(self.memo or "").strip())


@dataclass
class JournalEntry:
    """
    A balanced accounting journal entry.
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entry_date: str = field(default_factory=_now_iso)
    description: str = ""
    source: str = "manual"  # e.g., "bank_txn", "invoice", "t4_import"
    lines: List[JournalLine] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "JournalEntry":
        return JournalEntry(
            entry_id=str(self.entry_id),
            entry_date=str(self.entry_date),
            description=(self.description or "").strip(),
            source=(self.source or "").strip(),
            lines=[ln.normalized() for ln in self.lines],
            metadata=dict(self.metadata or {}),
        )

    def totals(self) -> Tuple[Decimal, Decimal]:
        je = self.normalized()
        total_debits = sum((ln.debit for ln in je.lines), Decimal("0"))
        total_credits = sum((ln.credit for ln in je.lines), Decimal("0"))
        return _q2(total_debits), _q2(total_credits)

    def validate(self, coa: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        je = self.normalized()

        if not je.lines:
            raise ValueError("JournalEntry must contain at least one line.")

        # Account validity
        if coa is not None:
            for ln in je.lines:
                if ln.account not in coa:
                    raise ValueError(f"Unknown account code: {ln.account}")

        # Line validity: exactly one side positive
        for ln in je.lines:
            d, c = ln.debit, ln.credit
            if (d <= 0 and c <= 0) or (d > 0 and c > 0):
                raise ValueError(
                    f"Invalid JournalLine for account {ln.account}: "
                    f"exactly one of debit/credit must be > 0 (got debit={d}, credit={c})."
                )

        # Balanced entry
        td, tc = je.totals()
        if td != tc:
            raise ValueError(f"JournalEntry not balanced: debits={td} credits={tc}")

    def to_canonical_payload(self) -> Dict[str, Any]:
        """
        Canonical (stable) structure suitable for hashing / sealing.
        Keeps only deterministic fields (no changing timestamps beyond entry_date).
        """
        je = self.normalized()
        lines = [
            {
                "account": ln.account,
                "debit": str(ln.debit),
                "credit": str(ln.credit),
                "memo": ln.memo,
            }
            for ln in je.lines
        ]
        return {
            "entry_id": je.entry_id,
            "entry_date": je.entry_date,
            "description": je.description,
            "source": je.source,
            "lines": lines,
            "metadata": je.metadata,  # must be JSON-serializable if you include it
        }


# =========================
# Immutability Chain Engine
# =========================

class LedgerEngine:
    """
    The 'Notary' of 8law.
    Takes financial records (tax returns, journal entries, etc.) and 'freezes'
    them into a cryptographic chain using SHA-256.
    """

    @staticmethod
    def generate_hash(data_string: str) -> str:
        """Creates a SHA-256 fingerprint of any text."""
        return hashlib.sha256((data_string or "").encode("utf-8")).hexdigest()

    def create_genesis_block(self) -> Dict[str, Any]:
        """
        Creates Block #0. This is the anchor of the entire system.
        """
        timestamp = _now_iso()
        content = f"GENESIS_8LAW_2026|{timestamp}"
        return {
            "block_id": 0,
            "entity_id": "GENESIS",
            "entity_type": "GENESIS",
            "previous_block_hash": "0" * 64,
            "data_hash": "GENESIS_BLOCK_8LAW_START",
            "timestamp": timestamp,
            "block_hash": self.generate_hash(content),
        }

    def seal_entity(
        self,
        entity_type: str,
        entity_id: Any,
        payload: Dict[str, Any],
        previous_block: Dict[str, Any],
        include_payload_in_metadata: bool = False,
    ) -> Dict[str, Any]:
        """
        Generic sealer for any entity.
        - payload is serialized deterministically (sort_keys=True)
        - data_hash = SHA256(payload_json)
        - block_hash = SHA256(prev_hash + data_hash + timestamp)

        include_payload_in_metadata:
            If True, stores payload alongside block row (useful for debugging),
            but note: storing raw payload may be sensitive.
        """
        if not isinstance(previous_block, dict) or "block_hash" not in previous_block:
            raise ValueError("previous_block must be a dict containing 'block_hash'")

        prev_hash = str(previous_block["block_hash"])
        timestamp = _now_iso()

        # Deterministic serialization
        payload_string = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        current_data_hash = self.generate_hash(payload_string)

        block_content = f"{prev_hash}{current_data_hash}{timestamp}"
        final_block_hash = self.generate_hash(block_content)

        out: Dict[str, Any] = {
            "entity_id": str(entity_id),
            "entity_type": str(entity_type),
            "data_hash": current_data_hash,
            "previous_block_hash": prev_hash,
            "timestamp": timestamp,
            "block_hash": final_block_hash,
        }

        if include_payload_in_metadata:
            out["payload"] = payload  # be careful with PII/sensitive data

        return out

    def seal_tax_return(self, tax_return_data: Dict[str, Any], previous_block: Dict[str, Any]) -> Dict[str, Any]:
        """
        Backward-compatible wrapper for TAX_RETURN sealing.

        tax_return_data expected keys:
            {id, total_income, total_tax_payable, user_id}
        """
        payload = {
            "id": str(tax_return_data["id"]),
            "total_income": str(tax_return_data["total_income"]),
            "total_tax": str(tax_return_data["total_tax_payable"]),
            "user_id": str(tax_return_data["user_id"]),
        }
        return self.seal_entity(
            entity_type="TAX_RETURN",
            entity_id=tax_return_data["id"],
            payload=payload,
            previous_block=previous_block,
        )

    def seal_journal_entry(
        self,
        entry: JournalEntry,
        previous_block: Dict[str, Any],
        coa: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Validate and seal a JournalEntry into the immutability chain.
        """
        if coa is None:
            coa = default_coa()

        entry.validate(coa=coa)
        payload = entry.to_canonical_payload()

        return self.seal_entity(
            entity_type="JOURNAL_ENTRY",
            entity_id=entry.entry_id,
            payload=payload,
            previous_block=previous_block,
        )

    def verify_integrity(self, database_records: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        AUDIT FUNCTION:
        Verifies the hash chain links:
            current.previous_block_hash == previous.block_hash

        Notes:
        - Some DB schemas include block_id; some don't.
        - This function does not attempt to recompute block_hash from data_hash
          because the original timestamp and exact payload are often not available
          in the ledger table. If you store payload/timestamp deterministically,
          we can add a "deep verify" mode later.
        """
        if not database_records:
            return True, "No ledger records to verify."

        # Ensure the first record is treated as genesis anchor
        for i in range(1, len(database_records)):
            current_block = database_records[i]
            previous_block = database_records[i - 1]

            cur_prev = str(current_block.get("previous_block_hash", ""))
            prev_hash = str(previous_block.get("block_hash", ""))

            if not prev_hash:
                return False, f"Missing block_hash on previous record at index {i-1}"

            if cur_prev != prev_hash:
                block_id = current_block.get("block_id")
                label = f"Block {block_id}" if block_id is not None else f"Index {i}"
                return False, f"Broken chain at {label}: previous hash mismatch."

        return True, "Ledger integrity verified."


# -------------------------
# Convenience constructors
# -------------------------

def make_entry(
    description: str,
    lines: Iterable[Dict[str, Any]],
    source: str = "manual",
    entry_date: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    entry_id: Optional[str] = None,
) -> JournalEntry:
    """
    Helper to build a JournalEntry from dict lines.
    Example line dict:
        {"account": "1000", "debit": "10.00", "credit": "0", "memo": "..."}

    This is useful when your agent outputs JSON and you want strict validation.
    """
    jl: List[JournalLine] = []
    for ln in lines:
        jl.append(
            JournalLine(
                account=str(ln.get("account", "")).strip(),
                debit=_to_decimal(ln.get("debit", "0")),
                credit=_to_decimal(ln.get("credit", "0")),
                memo=str(ln.get("memo", "") or "").strip(),
            )
        )

    je = JournalEntry(
        entry_id=entry_id or str(uuid.uuid4()),
        entry_date=entry_date or _now_iso(),
        description=description,
        source=source,
        lines=jl,
        metadata=dict(metadata or {}),
    )
    return je
