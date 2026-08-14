"""Prehľadávanie webu rozdelené na partície.

Stránkovanie na nehnutelnosti.sk končí na 33. strane, čo je ~990 inzerátov.
V Bratislavskom kraji je ale cez 9 000 ponúk na predaj. Preto sa hľadanie
rozdelí na dvojice (kategória, okres) a ak je aj tá príliš veľká, ešte na
podkategórie. Vďaka tomu sa k žiadnej ponuke nestratí prístup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .fetcher import Fetcher, make_resolver, parse_listings, flight_text, search_url
from .models import Listing

log = logging.getLogger(__name__)


@dataclass
class Partition:
    category: str | None
    district: str
    label: str


class Crawler:
    def __init__(self, fetcher: Fetcher, config: dict):
        self.fetcher = fetcher
        self.cfg = config
        self.transaction = config.get("transaction", "predaj")
        self.page_size = int(config.get("page_size", 30))
        self.max_pages = int(config.get("max_pages", 33))
        self.reachable = self.page_size * self.max_pages
        self.stats = {"requests": 0, "pages": 0, "over_cap": []}

    # ── jedna stránka ────────────────────────────────────────────────────
    def _fetch_page(self, category, district, page):
        url = search_url(category, district, self.transaction, page)
        html = self.fetcher.get(url)
        self.stats["requests"] += 1
        if html is None:
            return None, None
        raw, total = parse_listings(html)
        resolve = make_resolver(flight_text(html))
        listings = [Listing.from_raw(o, resolve) for o in raw]
        return listings, total

    # ── jedna partícia (kategória × okres) ───────────────────────────────
    def _crawl_partition(self, part: Partition, out: dict[str, Listing]) -> None:
        first, total = self._fetch_page(part.category, part.district, 1)
        if first is None:
            log.warning("  %s – stránka neexistuje, preskakujem", part.label)
            return

        if total is None:
            total = len(first)

        if total == 0:
            log.info("  %-46s 0 ponúk", part.label)
            return

        # Príliš veľká partícia – skús ju rozdeliť na podkategórie.
        if total > self.reachable:
            subs = self._subcategories(part.category)
            if subs:
                log.info("  %-46s %5d ponúk → delím na %d podkategórií",
                         part.label, total, len(subs))
                for sub in subs:
                    self._crawl_partition(
                        Partition(sub, part.district, f"{sub}/{part.district}"), out
                    )
                return
            log.warning("  %-46s %5d ponúk – NAD LIMITOM (%d), časť ostane neprehľadaná",
                        part.label, total, self.reachable)
            self.stats["over_cap"].append((part.label, total))

        pages = min((total + self.page_size - 1) // self.page_size, self.max_pages)
        self._collect(first, out)
        self.stats["pages"] += 1
        log.info("  %-46s %5d ponúk / %2d strán", part.label, total, pages)

        for page in range(2, pages + 1):
            listings, _ = self._fetch_page(part.category, part.district, page)
            if not listings:
                break
            self._collect(listings, out)
            self.stats["pages"] += 1

    @staticmethod
    def _collect(listings: list[Listing], out: dict[str, Listing]) -> int:
        added = 0
        for l in listings:
            if l.id and l.id not in out:
                out[l.id] = l
                added += 1
        return added

    def _subcategories(self, category: str | None) -> list[str]:
        for entry in self.cfg.get("categories", []):
            if entry.get("slug") == category:
                return list(entry.get("subcategories") or [])
        return []

    # ── celý beh ─────────────────────────────────────────────────────────
    def crawl(self) -> list[Listing]:
        """Prejde všetky partície a vráti unikátne ponuky (všetkých inzerentov)."""
        out: dict[str, Listing] = {}
        districts = self.cfg.get("districts", [])
        categories = self.cfg.get("categories", [])

        total_parts = len(districts) * len(categories)
        log.info("Prehľadávam %d partícií (%d kategórií × %d okresov)...",
                 total_parts, len(categories), len(districts))

        for entry in categories:
            slug = entry.get("slug")
            log.info("Kategória: %s", slug)
            for district in districts:
                part = Partition(slug, district, f"{slug}/{district}")
                self._crawl_partition(part, out)

        log.info("Hotovo: %d unikátnych ponúk, %d requestov",
                 len(out), self.stats["requests"])
        return list(out.values())
