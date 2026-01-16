from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import yaml, but fail gracefully if not installed
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

class RulesRegistryError(ValueError):
    """Raised when the rules registry is invalid."""

def _to_decimal(value: Any, *, field_path: str) -> Decimal:
    """Convert registry numeric values to Decimal safely."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(str(value))
    if isinstance(value, float):
        return Decimal(str(value))
    raise RulesRegistryError(f"Invalid numeric value at {field_path}: {value!r}")

def default_registry_path() -> Path:
    """Default registry file path (JSON) co-located with this module."""
    here = Path(__file__).resolve().parent
    return here / "rules_registry.json"

@dataclass(frozen=True)
class RulesRegistry:
    schema_version: str
    jurisdiction: str
    module: str
    years: Dict[int, Dict[str, Any]]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RulesRegistry":
        if not isinstance(data, dict):
            raise RulesRegistryError("Registry must be a JSON object.")
        
        years_raw = data.get("years", {})
        years: Dict[int, Dict[str, Any]] = {}
        
        for year_key, year_cfg in years_raw.items():
            years[int(year_key)] = year_cfg

        return RulesRegistry(
            schema_version=str(data.get("schema_version", "")),
            jurisdiction=str(data.get("jurisdiction", "")),
            module=str(data.get("module", "")),
            years=years,
        )

def load_rules_registry(path: Optional[str] = None) -> RulesRegistry:
    """Load the registry from disk."""
    p = Path(path) if path else default_registry_path()
    if not p.exists():
        raise RulesRegistryError(f"Rules registry not found: {p}")

    raw_text = p.read_text(encoding="utf-8")
    
    if p.suffix == ".json":
        data = json.loads(raw_text)
    elif p.suffix in {".yaml", ".yml"} and yaml:
        data = yaml.safe_load(raw_text)
    else:
        # Fallback for simple JSON if extension is weird
        data = json.loads(raw_text)

    return RulesRegistry.from_dict(data)

def get_year_config(registry: RulesRegistry, tax_year: int) -> Dict[str, Any]:
    if tax_year not in registry.years:
        # Fallback to nearest year or raise error
        raise RulesRegistryError(f"Tax year {tax_year} not in registry.")
    return registry.years[tax_year]

def read_decimal(registry_year_cfg: Dict[str, Any], dotted_path: str) -> Decimal:
    """Read a nested value like 'rrsp.limit' and return Decimal."""
    parts = dotted_path.split(".")
    cur = registry_year_cfg
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise RulesRegistryError(f"Path not found: {dotted_path}")
    return _to_decimal(cur, field_path=dotted_path)