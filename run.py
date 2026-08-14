#!/usr/bin/env python3
"""Scraper ponúk priamo od majiteľa na nehnutelnosti.sk.

Použitie:
    python run.py                 # bežný beh: nájdi nové, pošli email
    python run.py --dry-run       # nič neodošle, nič neuloží, len vypíše
    python run.py --test-email    # overí SMTP nastavenie skúšobným mailom
    python run.py --limit 2       # rýchly test: len 2 okresy
    python run.py --stats         # čo je v databáze
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scraper.config import load_search_config, load_settings
from scraper.crawler import Crawler
from scraper.fetcher import Fetcher
from scraper.models import PRIVATE_OWNER, Listing
from scraper.store import Store
from scraper import (export_excel, export_local, export_web, filters,
                     notify_email, sheets)

log = logging.getLogger("run")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def limit_first_run(listings: list[Listing], cfg: dict) -> list[Listing]:
    """Pri prvom behu nezaplav schránku rokmi starými inzerátmi."""
    days = (cfg.get("filters") or {}).get("first_run_max_age_days")
    if not days:
        return listings
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
    kept = []
    for l in listings:
        try:
            created = datetime.fromisoformat(l.created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            kept.append(l)
            continue
        if created >= cutoff:
            kept.append(l)
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description="Ponuky priamo od majiteľa – nehnutelnosti.sk")
    ap.add_argument("--dry-run", action="store_true",
                    help="nič neodosielať ani neukladať, len vypísať výsledok")
    ap.add_argument("--test-sheets", action="store_true",
                    help="overiť pripojenie na Google Sheets a skončiť")
    ap.add_argument("--test-email", action="store_true",
                    help="poslať skúšobný email a skončiť")
    ap.add_argument("--stats", action="store_true", help="vypísať stav databázy")
    ap.add_argument("--limit", type=int, metavar="N",
                    help="prehľadať len prvých N okresov (na rýchly test)")
    ap.add_argument("--all", action="store_true",
                    help="poslať všetky nájdené ponuky, nielen nové")
    args = ap.parse_args()

    settings = load_settings()
    setup_logging(settings.log_level)
    cfg = load_search_config()

    if args.stats:
        store = Store(settings.db_path)
        s = store.stats()
        print(f"Ponúk od majiteľa v databáze: {s['private_total']}")
        print(f"Počet behov:                  {s['runs']}")
        print(f"Posledný beh:                 {s['last_run'] or '–'}")
        print(f"Nových naposledy:             {s['last_new'] if s['last_new'] is not None else '–'}")
        store.close()
        return 0

    if args.test_sheets or args.test_email:
        demo = Listing(
            id="TEST", title="Skúšobná ponuka – ak toto vidíš, funguje to",
            url="https://www.nehnutelnosti.sk/", price="123 456 €", price_num=123456,
            unit_price="2 500 €/m²", area=49.4, category="TWO_ROOM_APARTMENT",
            state="Novostavba", location="Testovacia 1, Bratislava",
            district="okres Bratislava I", advertiser_name="Test",
            advertiser_type=PRIVATE_OWNER,
            description="Toto je ukážka, ako budú vyzerať skutočné ponuky.",
        )
        if args.test_sheets:
            ok = sheets.append(settings, [demo])
            print("Zápis do Google Sheets prebehol ✓ – skontroluj tabuľku, "
                  "mal pribudnúť skúšobný riadok (pokojne ho zmaž)."
                  if ok else "Zápis do Google Sheets zlyhal ✗ (detaily vyššie)")
            return 0 if ok else 1
        ok = notify_email.send(settings, [demo])
        print("Email odoslaný ✓" if ok else "Email zlyhal ✗ (detaily vyššie)")
        return 0 if ok else 1

    if args.limit:
        cfg["districts"] = cfg["districts"][:args.limit]
        log.info("Obmedzené na okresy: %s", ", ".join(cfg["districts"]))

    started = datetime.now()
    fetcher = Fetcher(settings.request_delay, settings.request_timeout, settings.max_retries)
    crawler = Crawler(fetcher, cfg)

    all_listings = crawler.crawl()
    owners = [l for l in all_listings if l.advertiser_type == PRIVATE_OWNER]
    private = filters.apply_all(owners, cfg)
    private.sort(key=lambda l: l.created_at, reverse=True)

    max_age = (cfg.get("filters") or {}).get("max_age_days")
    log.info("Nájdené: %d ponúk celkom → %d od majiteľa → %d po filtroch "
             "(firmy odfiltrované, max %s dní)",
             len(all_listings), len(owners), len(private), max_age or "bez limitu")
    if crawler.stats["over_cap"]:
        for label, total in crawler.stats["over_cap"]:
            log.warning("Partícia '%s' (%d ponúk) presiahla limit stránkovania – "
                        "zváž jemnejšie delenie v config.yaml", label, total)

    store = Store(settings.db_path)
    first_run = store.is_first_run

    if args.all:
        to_send = private
    else:
        to_send = store.filter_new(private)
        if first_run:
            before = len(to_send)
            to_send = limit_first_run(to_send, cfg)
            if before != len(to_send):
                log.info("Prvý beh: z %d ponúk posielam %d najnovších "
                         "(staršie sú uložené, ale neposielajú sa)", before, len(to_send))

    log.info("Nových na odoslanie: %d", len(to_send))

    if args.dry_run:
        print(f"\n── DRY RUN – {len(to_send)} nových ponúk ──")
        for l in to_send:
            print(f"  {(l.created_at or '')[:10]}  {l.price or 'dohodou':>12}  "
                  f"{(str(l.area) + ' m²') if l.area else '':>9}  {l.title[:60]}")
            print(f"      {l.url}")
        store.close()
        return 0

    delivered = True
    # Prírastkové výstupy: každú ponuku doručia práve raz. Keď zlyhajú,
    # ponuku nesmieme označiť za vybavenú, inak by sa stratila.
    incremental_ok = True
    if to_send:
        if settings.csv_enabled:
            incremental_ok &= export_local.append_csv(settings.csv_path, to_send)
        if settings.sheets_enabled:
            incremental_ok &= sheets.append(settings, to_send)
        if settings.email_enabled:
            incremental_ok &= notify_email.send(settings, to_send)
        if not any((settings.excel_enabled, settings.csv_enabled,
                    settings.sheets_enabled, settings.email_enabled)):
            log.warning("Žiadny výstup nie je zapnutý – ponuky sa len uložia "
                        "do databázy. Zapni EXCEL_ENABLED v .env")
    elif settings.email_enabled and settings.email_on_empty:
        notify_email.send(settings, [])

    if incremental_ok:
        store.upsert(private, notified=True)
    else:
        log.warning("Doručenie zlyhalo – %d ponúk neoznačujem ako vybavené, "
                    "skúsi sa to znova pri ďalšom behu", len(to_send))
        pending = {l.id for l in to_send}
        store.upsert([l for l in private if l.id not in pending], notified=True)

    # Snímkové výstupy: prekresľujú sa celé z databázy, takže obsahujú aj
    # staršie ponuky. Keď zlyhajú, nič sa nestratí – ďalší beh ich vytvorí
    # znova z tých istých dát. Preto negatujú len návratový kód.
    snapshot_ok = True
    if settings.excel_enabled or settings.web_enabled or settings.html_enabled:
        # Filtre platia aj tu: ponuka, ktorá medzičasom prekročila vekový
        # limit alebo pochádza od firmy uloženej starším behom, do výstupu
        # nepatrí, aj keď je v databáze.
        stale_days = (cfg.get("filters") or {}).get("stale_after_days")
        stored = filters.apply_all(
            store.all_private(seen_within_days=stale_days), cfg, verbose=False
        )
        new_ids = {l.id for l in to_send}
        if settings.excel_enabled:
            snapshot_ok &= export_excel.write(settings.excel_path, stored, new_ids)
        if settings.web_enabled:
            # Excel sa kopíruje vedľa stránky, nech sa dá stiahnuť z webu.
            xlsx = None
            if settings.excel_enabled:
                src, dst = Path(settings.excel_path), Path(settings.web_path).parent
                if src.parent.resolve() != dst.resolve():
                    dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst / src.name)
                xlsx = src.name
            snapshot_ok &= export_web.write(settings.web_path, stored, new_ids, xlsx)
        if settings.html_enabled:
            snapshot_ok &= export_local.write_html(settings.html_path, stored, new_ids)

    store.log_run(len(all_listings), len(private), len(to_send))
    store.close()

    log.info("Beh trval %s", str(datetime.now() - started).split(".")[0])
    return 0 if (incremental_ok and snapshot_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
