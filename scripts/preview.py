#!/usr/bin/env python3
"""Vygeneruje náhľad stránky a Excelu z lokálnej databázy – bez scrapovania.

Zapisuje do priečinka `preview/`, nie do `public/`. Priečinok `public/`
prepisuje pri každom behu GitHub Actions, takže keby doň zapisoval aj
lokálny počítač, vznikali by pri každom `git pull` konflikty.

Použitie:
    .\\.venv\\Scripts\\python scripts\\preview.py
"""

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper import export_excel, export_web, filters          # noqa: E402
from scraper.config import load_search_config, load_settings   # noqa: E402
from scraper.store import Store                                # noqa: E402

OUT = ROOT / "preview"


def main() -> int:
    settings = load_settings()
    cfg = load_search_config()
    stale = (cfg.get("filters") or {}).get("stale_after_days")

    store = Store(settings.db_path)
    listings = filters.apply_all(
        store.all_private(seen_within_days=stale), cfg, verbose=False
    )
    store.close()

    if not listings:
        print("Databáza je prázdna – najprv spusti `python run.py`.")
        return 1

    OUT.mkdir(exist_ok=True)
    # Prvých päť označíme ako nové, nech je vidno aj ten stav.
    export_excel.write(OUT / "ponuky.xlsx", listings, set())
    export_web.write(OUT / "index.html", listings,
                     {l.id for l in listings[:5]}, "ponuky.xlsx")

    page = OUT / "index.html"
    print(f"\nNáhľad: {page}")
    webbrowser.open(page.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
