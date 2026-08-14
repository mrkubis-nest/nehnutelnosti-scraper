"""Lokálne ukladanie ponúk: CSV do Excelu + HTML prehľad do prehliadača."""

from __future__ import annotations

import csv
import html
import logging
from datetime import datetime
from pathlib import Path

from .models import Listing

log = logging.getLogger(__name__)

COLUMNS = [
    "Pridané", "Dátum inzerátu", "Titul", "Cena", "Cena €", "€/m²", "Plocha m²",
    "Kategória", "Stav", "Lokalita", "Okres", "Majiteľ", "Odkaz",
]

CATEGORY_SK = {
    # byty
    "STUDIO_APARTMENT": "Garsónka",
    "ONE_ROOM_APARTMENT": "1-izbový byt",
    "TWO_ROOM_APARTMENT": "2-izbový byt",
    "THREE_ROOM_APARTMENT": "3-izbový byt",
    "FOUR_ROOM_APARTMENT": "4-izbový byt",
    "FIVE_PLUS_ROOM_APARTMENT": "5+ izbový byt",
    "MAISONETTE": "Mezonet",
    "LOFT": "Loft",
    "HOLIDAY_APARTMENT": "Apartmán",
    # domy
    "FAMILY_HOUSE": "Rodinný dom",
    "APARTMENT_HOUSE": "Bytový dom",
    "COUNTRY_HOUSE": "Vidiecky dom",
    "MOBILE_HOUSE": "Mobilný dom",
    # rekreačné
    "COTTAGE_AND_RECREATION_HOUSE": "Chata / rekreačný dom",
    "CABIN_AND_LOG_CABIN": "Zrub / chalupa",
    "GARDEN_HUT": "Záhradná chatka",
    # pozemky
    "LAND_FOR_FAMILY_HOUSE": "Pozemok pre rodinný dom",
    "LAND_FOR_HOUSING_CONSTRUCTION": "Pozemok pre bytovú výstavbu",
    "LAND_FOR_CIVIC_AMENITIES": "Pozemok – občianska vybavenosť",
    "RECREATIONAL_LAND": "Rekreačný pozemok",
    "OTHER_TYPE_OF_LAND": "Iný pozemok",
    "GARDEN": "Záhrada",
    "ARABLE_LAND": "Orná pôda",
    "VINEYARD_AND_HOP_GARDEN": "Vinica / chmeľnica",
    "COMMERCIAL_ZONE": "Komerčná zóna",
    "INDUSTRIAL_ZONE": "Priemyselná zóna",
    "MIXED_ZONE": "Zmiešaná zóna",
    # priestory a objekty
    "BUSINESS_SPACES": "Obchodné priestory",
    "RESTAURANT_SPACES": "Reštauračné priestory",
    "RESTAURANT": "Reštaurácia",
    "OFFICES": "Kancelárie",
    "OFFICE_BUILDING": "Administratívna budova",
    "POLYFUNCTIONAL_BUILDING": "Polyfunkčná budova",
    "HOTEL_AND_PENSION": "Hotel / penzión",
    "WAREHOUSE": "Sklad",
    "DETACHED_GARAGE": "Samostatná garáž",
    "OTHER_TYPE_OF_SPACE": "Iný priestor",
    "OTHER_TYPE_OF_OBJECT": "Iný objekt",
    # hlavné kategórie (záloha, ak chýba podtyp)
    "APARTMENTS": "Byt", "HOUSES": "Dom", "LANDS": "Pozemok",
    "SPACES": "Priestor", "OBJECTS": "Objekt",
    "COTTAGES_AND_CABINS": "Chata / chalupa", "REAL_ESTATES": "Nehnuteľnosť",
}


def cat_sk(l: Listing) -> str:
    if l.category in CATEGORY_SK:
        return CATEGORY_SK[l.category]
    if l.category:
        log.debug("Neznáma kategória: %s", l.category)
    return l.category.replace("_", " ").capitalize()


def _row(l: Listing) -> list:
    return [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        (l.created_at or "")[:10],
        l.title,
        l.price,
        l.price_num if l.price_num is not None else "",
        l.unit_price,
        l.area if l.area is not None else "",
        cat_sk(l),
        l.state,
        l.location,
        l.district,
        l.advertiser_name,
        l.url,
    ]


def append_csv(path: str | Path, listings: list[Listing]) -> bool:
    """Pripojí nové ponuky do CSV. Vytvorí súbor aj s hlavičkou, ak neexistuje."""
    if not listings:
        return True
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    is_new = not p.exists() or p.stat().st_size == 0

    try:
        # utf-8-sig = BOM, inak Excel zobrazí diakritiku ako neporiadok
        with open(p, "a", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            if is_new:
                w.writerow(COLUMNS)
            for l in listings:
                w.writerow(_row(l))
    except OSError as exc:
        log.error("Zápis do CSV zlyhal (%s): %s", p, exc)
        return False

    log.info("Zapísaných %d ponúk do %s", len(listings), p)
    return True


# ── HTML prehľad ────────────────────────────────────────────────────────────

def _card(l: Listing, is_new: bool) -> str:
    e = html.escape
    photo = (
        f'<img src="{e(l.photo)}" alt="" loading="lazy">' if l.photo
        else '<div class="noimg">bez fotky</div>'
    )
    meta = " · ".join(x for x in [
        f"{l.area:g} m²" if l.area else "", cat_sk(l), l.state
    ] if x)
    search_blob = e(" ".join([l.title, l.location, cat_sk(l), l.advertiser_name]).lower())

    return f"""<article class="card" data-price="{l.price_num or 0}"
   data-area="{l.area or 0}" data-date="{e((l.created_at or '')[:10])}"
   data-search="{search_blob}">
  <a class="thumb" href="{e(l.url)}" target="_blank" rel="noopener">{photo}</a>
  <div class="body">
    {'<span class="new">NOVÉ</span>' if is_new else ''}
    <a class="title" href="{e(l.url)}" target="_blank" rel="noopener">{e(l.title)}</a>
    <p class="loc">{e(l.location)}</p>
    <p class="price">{e(l.price) or 'Cena dohodou'}
      <span class="unit">{e(l.unit_price)}</span></p>
    <p class="meta">{e(meta)}</p>
    <p class="owner">{e(l.advertiser_name or 'Majiteľ')}
      <span class="date">· pridané {e((l.created_at or '')[:10])}</span></p>
  </div>
</article>"""


def write_html(path: str | Path, listings: list[Listing],
               new_ids: set[str] | None = None) -> bool:
    """Vygeneruje prehľadnú stránku so všetkými ponukami."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_ids = new_ids or set()

    cards = "\n".join(_card(l, l.id in new_ids) for l in listings)
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")

    doc = f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ponuky priamo od majiteľa – Bratislavský kraj</title>
<style>
 :root {{ --bg:#f4f6f8; --card:#fff; --line:#e3e7ec; --ink:#12263f;
          --muted:#6b7480; --green:#0b7a52; }}
 @media (prefers-color-scheme:dark) {{
   :root {{ --bg:#0f1419; --card:#182029; --line:#2a3542; --ink:#e8edf3;
            --muted:#96a0ac; --green:#3ddc9a; }} }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--ink);
         font:15px/1.5 -apple-system,'Segoe UI',Roboto,Arial,sans-serif; }}
 .wrap {{ max-width:1100px; margin:0 auto; }}
 h1 {{ margin:0 0 4px; font-size:24px; }}
 .sub {{ margin:0 0 20px; color:var(--muted); font-size:14px; }}
 .bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;
         position:sticky; top:0; background:var(--bg); padding:10px 0; z-index:5; }}
 input,select {{ padding:9px 12px; border:1px solid var(--line); border-radius:8px;
                 background:var(--card); color:var(--ink); font-size:14px; }}
 input[type=search] {{ flex:1; min-width:200px; }}
 .count {{ color:var(--muted); font-size:14px; align-self:center; }}
 .card {{ display:flex; gap:16px; background:var(--card); border:1px solid var(--line);
          border-radius:12px; margin-bottom:14px; overflow:hidden; }}
 .thumb {{ flex:0 0 220px; }}
 .thumb img {{ width:220px; height:165px; object-fit:cover; display:block; }}
 .noimg {{ width:220px; height:165px; display:grid; place-items:center;
           background:var(--line); color:var(--muted); font-size:13px; }}
 .body {{ padding:14px 16px 14px 0; min-width:0; }}
 .title {{ color:var(--ink); font-size:16px; font-weight:600; text-decoration:none;
           display:block; }}
 .title:hover {{ text-decoration:underline; }}
 .loc {{ margin:5px 0 0; color:var(--muted); font-size:13px; }}
 .price {{ margin:9px 0 0; font-size:19px; font-weight:700; color:var(--green); }}
 .unit {{ font-size:13px; font-weight:400; color:var(--muted); }}
 .meta {{ margin:6px 0 0; color:var(--muted); font-size:13px; }}
 .owner {{ margin:8px 0 0; font-size:13px; }}
 .date {{ color:var(--muted); }}
 .new {{ display:inline-block; background:var(--green); color:#fff; font-size:11px;
         font-weight:700; padding:2px 8px; border-radius:20px; margin-bottom:6px; }}
 @media (max-width:640px) {{
   .card {{ flex-direction:column; }}
   .thumb, .thumb img, .noimg {{ width:100%; flex:none; }}
   .body {{ padding:0 16px 16px; }} }}
</style></head><body><div class="wrap">
<h1>Ponuky priamo od majiteľa</h1>
<p class="sub">Bratislavský kraj · predaj · bez realitných kancelárií<br>
Aktualizované {generated} · {len(listings)} ponúk</p>

<div class="bar">
  <input type="search" id="q" placeholder="Hľadať v názve, lokalite…">
  <select id="sort">
    <option value="date">Najnovšie</option>
    <option value="price-asc">Cena – najlacnejšie</option>
    <option value="price-desc">Cena – najdrahšie</option>
    <option value="area-desc">Plocha – najväčšie</option>
  </select>
  <span class="count" id="count"></span>
</div>

<div id="list">
{cards}
</div>
</div>
<script>
 const list=document.getElementById('list'), q=document.getElementById('q'),
       sort=document.getElementById('sort'), count=document.getElementById('count');
 const all=[...list.children];
 function render(){{
   const term=q.value.trim().toLowerCase();
   let vis=all.filter(c=>!term||c.dataset.search.includes(term));
   const s=sort.value;
   // Ceny 1 € a nižšie sú zástupné ("dohodou") – pri triedení patria dozadu.
   const p=c=>{{const v=+c.dataset.price; return v>1?v:null;}};
   vis.sort((a,b)=>{{
     if(s==='price-asc')  return (p(a)??9e15)-(p(b)??9e15);
     if(s==='price-desc') return (p(b)??-1)-(p(a)??-1);
     if(s==='area-desc')  return (+b.dataset.area)-(+a.dataset.area);
     return b.dataset.date.localeCompare(a.dataset.date);
   }});
   list.replaceChildren(...vis);
   count.textContent=vis.length+' z '+all.length;
 }}
 q.addEventListener('input',render); sort.addEventListener('change',render); render();
</script></body></html>"""

    try:
        p.write_text(doc, encoding="utf-8")
    except OSError as exc:
        log.error("Zápis HTML prehľadu zlyhal (%s): %s", p, exc)
        return False

    log.info("HTML prehľad: %s (%d ponúk)", p.resolve(), len(listings))
    return True
