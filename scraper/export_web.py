"""Webová stránka so zoznamom ponúk – čistý text, žiadne fotky.

Generuje jeden samostatný HTML súbor, ktorý sa dá otvoriť lokálne
alebo publikovať cez GitHub Pages.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path

from .export_local import cat_sk
from .models import Listing

log = logging.getLogger(__name__)


def _rows(listings: list[Listing], new_ids: set[str]) -> str:
    out = []
    for l in listings:
        e = html.escape
        blob = e(" ".join([l.location, l.advertiser_name, cat_sk(l)]).lower())
        added = (l.created_at or "")[:10]
        out.append(
            f'<tr data-s="{blob}" data-d="{e(added)}" data-t="{e(cat_sk(l))}">'
            f'<td class="loc">{e(l.location)}'
            f'{" <span class=n>NOVÉ</span>" if l.id in new_ids else ""}</td>'
            f'<td>{e(l.advertiser_name)}</td>'
            f'<td>{e(cat_sk(l))}</td>'
            f'<td class="d">{e(added)}</td>'
            f'<td><a href="{e(l.url)}" target="_blank" rel="noopener">otvoriť →</a></td>'
            f'</tr>'
        )
    return "\n".join(out)


def write(path: str | Path, listings: list[Listing],
          new_ids: set[str] | None = None,
          xlsx_name: str | None = "ponuky.xlsx") -> bool:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_ids = new_ids or set()

    types = sorted({cat_sk(l) for l in listings})
    options = "".join(f'<option value="{html.escape(t)}">{html.escape(t)}</option>'
                      for t in types)
    download = (
        f'<a class="dl" href="{xlsx_name}" download>⬇ Stiahnuť ako Excel</a>'
        if xlsx_name else ""
    )

    doc = f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Ponuky priamo od majiteľa – Bratislavský kraj</title>
<style>
 :root {{ --bg:#f6f7f9; --card:#fff; --line:#e2e6ec; --ink:#16202c;
          --muted:#6b7480; --accent:#0b7a52; }}
 @media (prefers-color-scheme:dark) {{
   :root {{ --bg:#0f1419; --card:#171f28; --line:#2a3542; --ink:#e8edf3;
            --muted:#95a0ac; --accent:#3ddc9a; }} }}
 *{{box-sizing:border-box}}
 body {{ margin:0; padding:22px 16px; background:var(--bg); color:var(--ink);
   font:15px/1.45 -apple-system,'Segoe UI',Roboto,Arial,sans-serif; }}
 .wrap {{ max-width:1080px; margin:0 auto; }}
 h1 {{ margin:0 0 4px; font-size:23px; }}
 .sub {{ margin:0 0 18px; color:var(--muted); font-size:14px; }}
 .bar {{ display:flex; gap:9px; flex-wrap:wrap; align-items:center; margin-bottom:14px; }}
 input,select {{ padding:9px 12px; border:1px solid var(--line); border-radius:8px;
   background:var(--card); color:var(--ink); font-size:14px; }}
 input {{ flex:1; min-width:190px; }}
 .cnt {{ color:var(--muted); font-size:14px; }}
 .dl {{ margin-left:auto; background:var(--accent); color:#fff; text-decoration:none;
   padding:9px 15px; border-radius:8px; font-size:14px; font-weight:600; }}
 .tw {{ overflow-x:auto; background:var(--card); border:1px solid var(--line);
   border-radius:10px; }}
 table {{ border-collapse:collapse; width:100%; min-width:720px; }}
 th {{ background:var(--card); text-align:left; font-size:12px; letter-spacing:.04em;
   text-transform:uppercase; color:var(--muted); padding:11px 14px;
   border-bottom:1px solid var(--line); position:sticky; top:0; cursor:pointer;
   user-select:none; white-space:nowrap; }}
 th:hover {{ color:var(--ink); }}
 td {{ padding:11px 14px; border-bottom:1px solid var(--line); vertical-align:top; }}
 tr:last-child td {{ border-bottom:none; }}
 .loc {{ font-weight:600; min-width:250px; }}
 .d {{ color:var(--muted); white-space:nowrap; font-variant-numeric:tabular-nums; }}
 a {{ color:#1668c4; text-decoration:none; white-space:nowrap; }}
 @media (prefers-color-scheme:dark) {{ a {{ color:#5aa9f5; }} }}
 a:hover {{ text-decoration:underline; }}
 .n {{ background:var(--accent); color:#fff; font-size:10px; font-weight:700;
   padding:2px 7px; border-radius:20px; margin-left:7px; vertical-align:2px; }}
 .foot {{ margin:18px 0 0; color:var(--muted); font-size:12px; text-align:center; }}
</style></head><body><div class="wrap">
<h1>Ponuky priamo od majiteľa</h1>
<p class="sub">Bratislavský kraj · predaj · bez realitných kancelárií ·
posledné 4 mesiace</p>

<div class="bar">
  <input id="q" type="search" placeholder="Hľadať v lokalite, inzerentovi…">
  <select id="t"><option value="">Všetky typy</option>{options}</select>
  <span class="cnt" id="c"></span>
  {download}
</div>

<div class="tw"><table>
<thead><tr>
  <th data-k="0">Lokalita</th><th data-k="1">Inzerent</th>
  <th data-k="2">Typ nehnuteľnosti</th><th data-k="3">Pridané</th><th>Odkaz</th>
</tr></thead>
<tbody id="b">
{_rows(listings, new_ids)}
</tbody></table></div>

<p class="foot">Aktualizované {datetime.now().strftime('%d.%m.%Y o %H:%M')} ·
{len(listings)} ponúk · zdroj nehnutelnosti.sk</p>
</div>
<script>
 const b=document.getElementById('b'), q=document.getElementById('q'),
       t=document.getElementById('t'), c=document.getElementById('c');
 // dir=+1 zoradí zostupne, -1 vzostupne. Štart: najnovšie ponuky hore.
 const all=[...b.rows]; let sk=3, dir=1;
 function draw(){{
   const term=q.value.trim().toLowerCase(), typ=t.value;
   let v=all.filter(r=>(!term||r.dataset.s.includes(term))&&(!typ||r.dataset.t===typ));
   v.sort((x,y)=>{{
     const a=(sk===3?x.dataset.d:x.cells[sk].textContent).toLowerCase();
     const z=(sk===3?y.dataset.d:y.cells[sk].textContent).toLowerCase();
     return a<z?dir:a>z?-dir:0;
   }});
   b.replaceChildren(...v);
   c.textContent=v.length+' z '+all.length;
 }}
 document.querySelectorAll('th[data-k]').forEach(h=>h.onclick=()=>{{
   // Dátum chceme od najnovšieho, text od A po Z.
   const k=+h.dataset.k; dir=(k===sk)?-dir:(k===3?1:-1); sk=k; draw();
 }});
 q.oninput=draw; t.onchange=draw; draw();
</script></body></html>"""

    try:
        p.write_text(doc, encoding="utf-8")
    except OSError as exc:
        log.error("Zápis webstránky zlyhal (%s): %s", p, exc)
        return False

    log.info("Webstránka: %s (%d ponúk)", p.resolve(), len(listings))
    return True
