"""Sťahovanie stránok nehnutelnosti.sk a parsovanie ich SSR dát.

Web beží na Next.js App Routeri. Kompletné dáta o inzerátoch sú v HTML
zabalené vo volaniach `self.__next_f.push([1,"..."])` – po ich spojení
vznikne RSC "flight" stream, z ktorého sa dajú vytiahnuť celé JSON objekty
inzerátov. Je to podstatne spoľahlivejšie než parsovanie HTML tried, ktoré
sa menia pri každom builde.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://www.nehnutelnosti.sk"

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)')
# Web od novembra 2026 posiela inzeráty v dvoch oddelených poliach, ktoré
# sa musia spojiť podľa id:
#   advertisementGtmItems  – inzerent a jeho typ, lokalita, cena, kategória
#   items[].advertisement  – slug do odkazu, plocha, adresa, slovenský názov typu
_GTM_START = re.compile(r'\{"photoUrl":"')
_ITEM_START = re.compile(r'\{"advertisement":\{')
_TOTAL = re.compile(r'"totalCount":(\d+)')
_TEXT_ROW = re.compile(r'(?:^|\n)([0-9a-f]+):T([0-9a-f]+),')
_STR_ROW = re.compile(r'(?:^|\n)([0-9a-f]+):("(?:[^"\\]|\\.)*")')

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class Fetcher:
    def __init__(self, delay: float = 1.2, timeout: int = 30, max_retries: int = 3):
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        wait = self.delay - elapsed
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.3))
        self._last_request = time.monotonic()

    def get(self, url: str) -> str | None:
        """Stiahne stránku. Vráti HTML, alebo None ak stránka neexistuje (404)."""
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                r = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning("Chyba siete (%s/%s) %s: %s", attempt, self.max_retries, url, exc)
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                backoff = 2 ** attempt * 2
                log.warning("HTTP %s pri %s – čakám %ss", r.status_code, url, backoff)
                time.sleep(backoff)
                continue
            log.error("Neočakávaný HTTP %s pri %s", r.status_code, url)
            return None

        log.error("Vzdávam sa po %s pokusoch: %s", self.max_retries, url)
        return None


def flight_text(html: str) -> str:
    """Spojí všetky RSC chunky z HTML do jedného reťazca."""
    parts = []
    for m in _PUSH.finditer(html):
        try:
            parts.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _balanced_object(text: str, start: int) -> str | None:
    """Vráti kompletný JSON objekt začínajúci na pozícii `start` ('{')."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def build_ref_table(flight: str) -> dict[str, str]:
    """Mapa RSC referencií (napr. "$33") na skutočný text.

    Dlhé texty (popisy inzerátov) web posiela ako samostatné riadky
    v tvare `33:T<dĺžka v hexa>,<text>`.
    """
    table: dict[str, str] = {}
    for m in _TEXT_ROW.finditer(flight):
        length = int(m.group(2), 16)
        table[m.group(1)] = flight[m.end():m.end() + length]
    for m in _STR_ROW.finditer(flight):
        if m.group(1) in table:
            continue
        try:
            table[m.group(1)] = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
    return table


def make_resolver(flight: str):
    """Funkcia, ktorá rozbalí hodnotu typu "$33" na text."""
    table = build_ref_table(flight)

    def resolve(value):
        if not isinstance(value, str):
            return ""
        if not value.startswith("$"):
            return value
        ref = value[1:]
        # Referencie s dvojbodkou sú odkazy na iné pole objektu – tie
        # neriešime, dôležité údaje máme priamo v objekte inzerátu.
        if ":" in ref:
            return ""
        return table.get(ref, "")

    return resolve


def _objects(flight: str, anchor: re.Pattern):
    """Prejde všetky JSON objekty začínajúce daným vzorom."""
    for match in anchor.finditer(flight):
        raw = _balanced_object(flight, match.start())
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def parse_listings(html: str) -> tuple[list[dict], int | None]:
    """Vytiahne zo stránky inzeráty a celkový počet výsledkov.

    Spája dve polia, ktoré web posiela oddelene. Prvé nesie typ inzerenta
    (bez neho by sa nedalo filtrovať na majiteľov), druhé slug do odkazu
    a plochu. Spoločným kľúčom je id inzerátu.
    """
    flight = flight_text(html)
    if not flight:
        return [], None

    total = None
    m = _TOTAL.search(flight)
    if m:
        total = int(m.group(1))

    gtm: dict[str, dict] = {}
    for obj in _objects(flight, _GTM_START):
        if obj.get("id") and "advertiser" in obj and "price" in obj:
            gtm.setdefault(obj["id"], obj)

    detail: dict[str, dict] = {}
    for obj in _objects(flight, _ITEM_START):
        ad = obj.get("advertisement") or {}
        if ad.get("id"):
            detail.setdefault(ad["id"], ad)

    results = []
    for ad_id, g in gtm.items():
        d = detail.get(ad_id, {})
        results.append({
            "id": ad_id,
            "title": g.get("title") or d.get("title") or "",
            "slug": d.get("slug") or "",
            "location": g.get("location") or {},
            "address": (d.get("address") or {}).get("location") or "",
            "advertiser": g.get("advertiser") or {},
            "price": g.get("price") or {},
            "category": g.get("category") or {},
            "subcategory": d.get("subcategory") or "",
            "area": d.get("area"),
            "transaction": d.get("transaction") or "",
            "realEstateState": g.get("realEstateState") or d.get("realEstateState") or "",
            "photoUrl": g.get("photoUrl") or "",
            "description": d.get("description") or "",
        })

    return results, total


def search_url(category: str | None, location: str, transaction: str, page: int = 1) -> str:
    """Poskladá URL výsledkov vyhľadávania."""
    parts = [BASE_URL, "vysledky"]
    if category:
        parts.append(category)
    parts.append(location)
    parts.append(transaction)
    url = "/".join(parts)
    if page > 1:
        url += f"?page={page}"
    return url
