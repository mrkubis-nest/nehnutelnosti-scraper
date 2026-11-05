"""Doplnenie dátumu zverejnenia z detailovej stránky.

Od novembra 2026 web vo výsledkoch vyhľadávania pole `createdAt` neposiela,
na detaile inzerátu však stále je. Bez neho by prestal fungovať filter na vek
ponuky aj zoraďovanie podľa dátumu.

Detaily sa sťahujú len pre ponuky od majiteľa, ktoré dátum ešte nemajú –
pri bežnom behu ide o jednotky inzerátov.
"""

from __future__ import annotations

import logging
import re

from .fetcher import Fetcher, flight_text
from .models import Listing

log = logging.getLogger(__name__)

_CREATED = re.compile(r'"createdAt":"([0-9T:.\-]+Z?)"')


def fetch_created_at(fetcher: Fetcher, url: str) -> str:
    """Vráti dátum zverejnenia z detailovej stránky, alebo prázdny reťazec."""
    html = fetcher.get(url)
    if not html:
        return ""
    m = _CREATED.search(flight_text(html))
    return m.group(1) if m else ""


def add_created_at(fetcher: Fetcher, listings: list[Listing],
                   known: dict[str, str] | None = None,
                   limit: int = 150) -> int:
    """Doplní chýbajúce dátumy. Vráti počet stiahnutých detailov.

    `known` sú dátumy už uložené v databáze – tie sa použijú zadarmo.
    `limit` je poistka, aby jeden beh nestiahol tisíce detailov.
    """
    known = known or {}
    todo = []
    for l in listings:
        if l.created_at:
            continue
        stored = known.get(l.id)
        if stored:
            l.created_at = stored
        else:
            todo.append(l)

    if not todo:
        return 0

    if len(todo) > limit:
        log.warning("Chýba dátum pri %d ponukách, sťahujem len prvých %d "
                    "(zvyšok sa doplní v ďalších behoch)", len(todo), limit)
        todo = todo[:limit]

    log.info("Dopĺňam dátum zverejnenia z %d detailových stránok…", len(todo))
    done = 0
    for l in todo:
        l.created_at = fetch_created_at(fetcher, l.url)
        if l.created_at:
            done += 1
    log.info("Dátum doplnený pri %d z %d ponúk", done, len(todo))
    return done
