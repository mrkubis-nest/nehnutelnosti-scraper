"""Filtrovanie ponúk: vek inzerátu a odsievanie firemných inzerentov.

Web označí inzerenta ako PRIVATE_PERSON podľa typu účtu, nie podľa toho,
či podniká s realitami. Časť realitiek a firiem inzeruje zo súkromného účtu,
takže druhou vrstvou je kontrola mena inzerenta.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .models import Listing

log = logging.getLogger(__name__)

# Vzory, ktoré v mene inzerenta prezrádzajú firmu. Zámerne konzervatívne –
# radšej prepustiť firmu, než odfiltrovať človeka s nezvyklým priezviskom.
DEFAULT_COMPANY_PATTERNS = [
    r"\bs\.?\s?r\.?\s?o\.?\b",
    r"\ba\.?\s?s\.?\b",
    r"\bspol\.?\b",
    r"\bk\.?\s?s\.?\b",
    r"realit",
    r"\breality\b",
    r"\bestate\b",
    r"\bhomes\b",
    r"\bproperty\b",
    r"\bproperties\b",
    r"\binvest",
    r"\bgroup\b",
    r"\bdevelop",
    r"\bbroker",
    r"\bagentúr|\bagentur",
    r"\bkancelár|\bkancelar",
    r"\bservis\b",
]


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_company_name(name: str, patterns: list[str] | None = None) -> bool:
    """Vyzerá meno inzerenta ako firma?"""
    if not name:
        return False
    for pat in (patterns or DEFAULT_COMPANY_PATTERNS):
        if re.search(pat, name, re.IGNORECASE):
            return True
    return False


def drop_companies(listings: list[Listing],
                   patterns: list[str] | None = None,
                   verbose: bool = True) -> list[Listing]:
    """Odstráni ponuky, kde meno inzerenta vyzerá na firmu."""
    kept, dropped = [], []
    for l in listings:
        if is_company_name(l.advertiser_name, patterns):
            dropped.append(l)
        else:
            kept.append(l)

    if dropped and verbose:
        names = sorted({l.advertiser_name for l in dropped})
        log.info("Odfiltrovaných %d ponúk od firemných inzerentov: %s",
                 len(dropped), ", ".join(names[:12]) + ("…" if len(names) > 12 else ""))
    return kept


def drop_old(listings: list[Listing], max_age_days: int | None) -> list[Listing]:
    """Odstráni ponuky staršie než zadaný počet dní.

    Ponuky bez dátumu si necháme – radšej niečo navyše než prísť o ponuku
    kvôli chýbajúcemu údaju.
    """
    if not max_age_days:
        return listings
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(max_age_days))
    kept = []
    for l in listings:
        created = _parse_date(l.created_at)
        if created is None or created >= cutoff:
            kept.append(l)
    return kept


def apply_all(listings: list[Listing], cfg: dict, verbose: bool = True) -> list[Listing]:
    """Všetky filtre z config.yaml naraz."""
    f = cfg.get("filters") or {}
    out = drop_companies(listings, cfg.get("exclude_advertiser_patterns"), verbose)
    out = drop_old(out, f.get("max_age_days"))

    result = []
    for l in out:
        if f.get("min_price") and (l.price_num or 0) < f["min_price"]:
            continue
        if f.get("max_price") and l.price_num and l.price_num > f["max_price"]:
            continue
        if f.get("min_area") and (l.area or 0) < f["min_area"]:
            continue
        if f.get("max_area") and l.area and l.area > f["max_area"]:
            continue
        result.append(l)
    return result
