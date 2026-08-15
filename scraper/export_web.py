"""Webová stránka so zoznamom ponúk – čistý text, žiadne fotky.

Generuje jeden samostatný HTML súbor, ktorý sa dá otvoriť lokálne
alebo publikovať cez GitHub Pages.
"""

from __future__ import annotations

import html
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .export_local import cat_sk
from .models import Listing

log = logging.getLogger(__name__)

# Zaradenie podtypov do širších skupín, aby sa dali farebne odlíšiť.
GROUPS = {
    "byt": {"Garsónka", "1-izbový byt", "2-izbový byt", "3-izbový byt",
            "4-izbový byt", "5+ izbový byt", "Mezonet", "Loft", "Apartmán", "Byt"},
    "dom": {"Rodinný dom", "Bytový dom", "Vidiecky dom", "Mobilný dom", "Dom"},
    "pozemok": {"Pozemok pre rodinný dom", "Pozemok pre bytovú výstavbu",
                "Pozemok – občianska vybavenosť", "Rekreačný pozemok", "Iný pozemok",
                "Záhrada", "Orná pôda", "Vinica / chmeľnica", "Komerčná zóna",
                "Priemyselná zóna", "Zmiešaná zóna", "Pozemok"},
    "rekreacia": {"Chata / rekreačný dom", "Zrub / chalupa", "Záhradná chatka",
                  "Chata / chalupa"},
}


def _group(typ: str) -> str:
    for name, members in GROUPS.items():
        if typ in members:
            return name
    return "ine"


def _short_district(d: str) -> str:
    return (d or "").replace("okres ", "").strip() or "Neuvedené"


def _parse(value: str):
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _rows(listings: list[Listing], new_ids: set[str]) -> str:
    out = []
    for l in listings:
        e = html.escape
        typ = cat_sk(l)
        okres = _short_district(l.district)
        added = (l.created_at or "")[:10]
        blob = e(" ".join([l.location, l.advertiser_name, typ, okres]).lower())
        pretty = ".".join(reversed(added.split("-"))) if added else "—"

        out.append(
            f'<li class="row" data-s="{blob}" data-d="{e(added)}"'
            f' data-t="{e(typ)}" data-o="{e(okres)}">'
            f'<div class="main">'
            f'<a class="place" href="{e(l.url)}" target="_blank" rel="noopener">'
            f'{e(l.location)}</a>'
            f'<div class="sub">'
            f'<span class="chip g-{_group(typ)}">{e(typ)}</span>'
            f'<span class="who">{e(l.advertiser_name or "Súkromná osoba")}</span>'
            f'</div></div>'
            f'<div class="side">'
            f'{"<span class=badge>NOVÉ</span>" if l.id in new_ids else ""}'
            f'<time datetime="{e(added)}">{e(pretty)}</time>'
            f'<a class="go" href="{e(l.url)}" target="_blank" rel="noopener"'
            f' aria-label="Otvoriť inzerát">Inzerát<span aria-hidden="true"> →</span></a>'
            f'</div></li>'
        )
    return "\n".join(out)


def write(path: str | Path, listings: list[Listing],
          new_ids: set[str] | None = None,
          xlsx_name: str | None = "ponuky.xlsx") -> bool:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_ids = new_ids or set()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    last_week = sum(1 for l in listings
                    if (d := _parse(l.created_at)) and d >= week_ago)

    okresy = Counter(_short_district(l.district) for l in listings)
    typy = sorted({cat_sk(l) for l in listings})

    chips = "".join(
        f'<button class="fchip" data-okres="{html.escape(o)}">'
        f'{html.escape(o)}<span>{n}</span></button>'
        for o, n in sorted(okresy.items(), key=lambda x: (-x[1], x[0]))
    )
    opts = "".join(f'<option value="{html.escape(t)}">{html.escape(t)}</option>'
                   for t in typy)
    dl = (f'<a class="dl" href="{xlsx_name}" download>Stiahnuť Excel</a>'
          if xlsx_name else "")

    doc = f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<meta name="description" content="Ponuky nehnuteľností priamo od majiteľa v Bratislavskom kraji, bez realitných kancelárií.">
<title>Priamo od majiteľa — Bratislavský kraj</title>
<style>
  :root {{
    --paper:#f0f1f3; --card:#ffffff; --sunk:#e7e9ed;
    --ink:#151a21; --ink-2:#3d4753; --muted:#6b7683; --line:#dfe3e9;
    --accent:#9a5b12; --accent-ink:#7d4a0d; --accent-bg:#f6ecdc;
    --link:#1a5490;
    --byt:#2f6f8f; --byt-bg:#e2eef4;
    --dom:#4a7c3f; --dom-bg:#e6f0e2;
    --poz:#8a6a1f; --poz-bg:#f4eddb;
    --rek:#7d4b7a; --rek-bg:#f1e7f1;
    --ine:#5f6874; --ine-bg:#e8eaee;
    --serif:Constantia,"Palatino Linotype",Palatino,Georgia,serif;
    --sans:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;
    --mono:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --paper:#0f1318; --card:#171d24; --sunk:#1e252d;
      --ink:#e8ecf1; --ink-2:#c2cad4; --muted:#8d98a6; --line:#28303a;
      --accent:#e0a049; --accent-ink:#e8b268; --accent-bg:#2b2216;
      --link:#6fb0ef;
      --byt:#7fc0dd; --byt-bg:#162d38;
      --dom:#8fce80; --dom-bg:#1a2d18;
      --poz:#d9bb6b; --poz-bg:#2d2716;
      --rek:#cf9fcc; --rek-bg:#2b1e2a;
      --ine:#9aa4b1; --ine-bg:#232a32;
    }}
  }}
  :root[data-theme="dark"] {{
    --paper:#0f1318; --card:#171d24; --sunk:#1e252d;
    --ink:#e8ecf1; --ink-2:#c2cad4; --muted:#8d98a6; --line:#28303a;
    --accent:#e0a049; --accent-ink:#e8b268; --accent-bg:#2b2216;
    --link:#6fb0ef;
    --byt:#7fc0dd; --byt-bg:#162d38;
    --dom:#8fce80; --dom-bg:#1a2d18;
    --poz:#d9bb6b; --poz-bg:#2d2716;
    --rek:#cf9fcc; --rek-bg:#2b1e2a;
    --ine:#9aa4b1; --ine-bg:#232a32;
  }}

  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; background:var(--paper); color:var(--ink);
    font-family:var(--sans); font-size:16px; line-height:1.5;
    -webkit-font-smoothing:antialiased;
  }}
  .wrap {{ max-width:940px; margin:0 auto; padding:38px 18px 80px; }}

  /* ---------- hlavička ---------- */
  header {{ margin-bottom:26px; }}
  .kicker {{
    font-family:var(--mono); font-size:11px; letter-spacing:.16em;
    text-transform:uppercase; color:var(--accent); margin:0 0 10px;
  }}
  h1 {{
    font-family:var(--serif); font-weight:700; font-size:clamp(31px,5.6vw,46px);
    line-height:1.06; letter-spacing:-.02em; margin:0 0 10px; text-wrap:balance;
  }}
  .tagline {{ margin:0; color:var(--muted); font-size:16px; max-width:56ch; }}

  .stats {{
    display:flex; gap:0; flex-wrap:wrap; margin:24px 0 0;
    background:var(--card); border:1px solid var(--line); border-radius:12px;
    overflow:hidden;
  }}
  .stat {{ flex:1 1 130px; padding:15px 18px; border-right:1px solid var(--line); }}
  .stat:last-child {{ border-right:none; }}
  .stat b {{
    display:block; font-family:var(--serif); font-size:29px; font-weight:700;
    line-height:1.1; font-variant-numeric:tabular-nums; letter-spacing:-.01em;
  }}
  .stat span {{
    display:block; font-family:var(--mono); font-size:10.5px; letter-spacing:.1em;
    text-transform:uppercase; color:var(--muted); margin-top:5px;
  }}
  .stat.hl b {{ color:var(--accent); }}

  /* ---------- ovládanie ---------- */
  /* Pozadie musí byť nepriehľadné a bez prechodu do stratena: cez priesvitný
     okraj presvitali riadky zoznamu a prechod ležal na texte nadpisov. */
  .controls {{
    position:sticky; top:0; z-index:20; padding:14px 0 13px;
    background:var(--paper); margin-top:26px;
    border-bottom:1px solid var(--line);
  }}
  .line1 {{ display:flex; gap:9px; flex-wrap:wrap; align-items:center; }}
  input[type=search], select {{
    font:inherit; font-size:14.5px; padding:10px 13px; color:var(--ink);
    background:var(--card); border:1px solid var(--line); border-radius:9px;
  }}
  input[type=search] {{ flex:1 1 230px; min-width:0; }}
  select {{ cursor:pointer; }}
  .dl {{
    background:var(--ink); color:var(--paper); text-decoration:none;
    font-size:14px; font-weight:600; padding:10px 16px; border-radius:9px;
    white-space:nowrap;
  }}
  .dl:hover {{ opacity:.87; }}
  .chips {{ display:flex; gap:7px; flex-wrap:wrap; margin-top:11px; }}
  .fchip {{
    font:inherit; font-size:13.5px; cursor:pointer; color:var(--ink-2);
    background:var(--card); border:1px solid var(--line); border-radius:20px;
    padding:6px 13px; display:inline-flex; gap:7px; align-items:center;
  }}
  .fchip span {{
    font-family:var(--mono); font-size:11px; color:var(--muted);
    font-variant-numeric:tabular-nums;
  }}
  .fchip:hover {{ border-color:var(--muted); }}
  .fchip[aria-pressed="true"] {{
    background:var(--ink); border-color:var(--ink); color:var(--paper);
  }}
  .fchip[aria-pressed="true"] span {{ color:var(--paper); opacity:.72; }}

  .status {{
    display:flex; justify-content:space-between; align-items:baseline;
    gap:14px; margin:16px 0 8px; flex-wrap:wrap;
  }}
  .count {{ font-family:var(--mono); font-size:12px; color:var(--muted); letter-spacing:.05em; }}
  .reset {{
    font:inherit; font-size:13px; background:none; border:none; cursor:pointer;
    color:var(--link); text-decoration:underline; padding:0;
  }}

  /* ---------- zoznam ---------- */
  ul.list {{ list-style:none; margin:0; padding:0;
             background:var(--card); border:1px solid var(--line); border-radius:12px; }}
  .row {{
    display:flex; gap:18px; align-items:flex-start; justify-content:space-between;
    padding:15px 18px; border-bottom:1px solid var(--line);
  }}
  .row:last-child {{ border-bottom:none; }}
  .row:hover {{ background:var(--sunk); }}
  .main {{ min-width:0; }}
  .place {{
    font-family:var(--serif); font-size:18.5px; font-weight:600; line-height:1.28;
    color:var(--ink); text-decoration:none; display:block; letter-spacing:-.005em;
  }}
  .place:hover {{ text-decoration:underline; text-underline-offset:3px; }}
  .sub {{ display:flex; gap:9px; align-items:center; flex-wrap:wrap; margin-top:7px; }}
  .chip {{
    font-size:12px; font-weight:600; padding:2.5px 9px; border-radius:5px;
    white-space:nowrap;
  }}
  .g-byt {{ color:var(--byt); background:var(--byt-bg); }}
  .g-dom {{ color:var(--dom); background:var(--dom-bg); }}
  .g-pozemok {{ color:var(--poz); background:var(--poz-bg); }}
  .g-rekreacia {{ color:var(--rek); background:var(--rek-bg); }}
  .g-ine {{ color:var(--ine); background:var(--ine-bg); }}
  .who {{ font-size:13.5px; color:var(--muted); }}
  .side {{
    display:flex; align-items:center; gap:13px; flex-shrink:0; padding-top:3px;
  }}
  .badge {{
    font-family:var(--mono); font-size:9.5px; font-weight:700; letter-spacing:.1em;
    color:var(--accent-ink); background:var(--accent-bg); border-radius:4px;
    padding:3px 7px;
  }}
  time {{
    font-family:var(--mono); font-size:12.5px; color:var(--muted);
    font-variant-numeric:tabular-nums; white-space:nowrap;
  }}
  .go {{
    font-size:13.5px; font-weight:600; color:var(--link); text-decoration:none;
    white-space:nowrap;
  }}
  .go:hover {{ text-decoration:underline; }}
  .empty {{ padding:44px 18px; text-align:center; color:var(--muted); }}

  footer {{
    margin-top:26px; padding-top:18px; border-top:1px solid var(--line);
    color:var(--muted); font-size:13px; display:flex; justify-content:space-between;
    gap:14px; flex-wrap:wrap;
  }}
  footer .mono {{ font-family:var(--mono); font-size:12px; }}

  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {{
    outline:2px solid var(--link); outline-offset:2px;
  }}
  @media (max-width:620px) {{
    .row {{ flex-direction:column; gap:10px; }}
    .side {{ padding-top:0; }}
    .stat {{ flex:1 1 50%; border-bottom:1px solid var(--line); }}
    /* Na úzkej obrazovke by osem okresov v dvoch radoch zabralo pol displeja,
       preto sa posúvajú vodorovne. */
    .chips {{
      flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none;
      padding-bottom:2px; margin-right:-18px; padding-right:18px;
    }}
    .chips::-webkit-scrollbar {{ display:none; }}
    .fchip {{ flex:0 0 auto; }}
  }}
  @media (prefers-reduced-motion:reduce) {{
    html {{ scroll-behavior:auto; }} * {{ transition:none !important; }}
  }}
</style></head><body>
<div class="wrap">

<header>
  <p class="kicker">Bratislavský kraj · predaj</p>
  <h1>Priamo od majiteľa</h1>
  <p class="tagline">
    Ponuky bez realitných kancelárií, zozbierané z nehnutelnosti.sk.
    Len inzeráty z posledných štyroch mesiacov.
  </p>

  <div class="stats">
    <div class="stat"><b>{len(listings)}</b><span>ponúk celkom</span></div>
    <div class="stat hl"><b>{len(new_ids)}</b><span>nových dnes</span></div>
    <div class="stat"><b>{last_week}</b><span>za týždeň</span></div>
    <div class="stat"><b>{len(okresy)}</b><span>okresov</span></div>
  </div>
</header>

<div class="controls">
  <div class="line1">
    <input type="search" id="q" placeholder="Hľadať v adrese alebo mene inzerenta…"
           aria-label="Hľadať">
    <select id="typ" aria-label="Typ nehnuteľnosti">
      <option value="">Všetky typy</option>{opts}
    </select>
    <select id="sort" aria-label="Zoradenie">
      <option value="new">Najnovšie</option>
      <option value="old">Najstaršie</option>
      <option value="loc">Podľa adresy</option>
    </select>
    {dl}
  </div>
  <div class="chips" id="chips">{chips}</div>
</div>

<div class="status">
  <span class="count" id="count"></span>
  <button class="reset" id="reset" hidden>Zrušiť filtre</button>
</div>

<ul class="list" id="list">
{_rows(listings, new_ids)}
</ul>
<p class="empty" id="empty" hidden>Nič nesedí. Skús zmeniť filtre.</p>

<footer>
  <span>Aktualizované <b>{datetime.now().strftime('%d.%m.%Y o %H:%M')}</b></span>
  <span class="mono">zdroj nehnutelnosti.sk</span>
</footer>

</div>
<script>
(function () {{
  var list = document.getElementById('list'),
      empty = document.getElementById('empty'),
      q = document.getElementById('q'),
      typ = document.getElementById('typ'),
      sort = document.getElementById('sort'),
      count = document.getElementById('count'),
      reset = document.getElementById('reset'),
      chips = [].slice.call(document.querySelectorAll('.fchip')),
      all = [].slice.call(list.children),
      okres = null;

  function draw() {{
    var term = q.value.trim().toLowerCase(), t = typ.value;
    var vis = all.filter(function (r) {{
      return (!term || r.dataset.s.indexOf(term) !== -1)
          && (!t || r.dataset.t === t)
          && (!okres || r.dataset.o === okres);
    }});

    var s = sort.value;
    vis.sort(function (a, b) {{
      if (s === 'loc') return a.querySelector('.place').textContent
                              .localeCompare(b.querySelector('.place').textContent, 'sk');
      if (s === 'old') return a.dataset.d.localeCompare(b.dataset.d);
      return b.dataset.d.localeCompare(a.dataset.d);
    }});

    list.replaceChildren.apply(list, vis);
    var filtered = term || t || okres;
    empty.hidden = vis.length > 0;
    list.hidden = vis.length === 0;
    reset.hidden = !filtered;
    count.textContent = filtered
      ? 'Zobrazených ' + vis.length + ' z ' + all.length
      : all.length + ' ponúk';
  }}

  chips.forEach(function (c) {{
    c.setAttribute('aria-pressed', 'false');
    c.addEventListener('click', function () {{
      var val = c.dataset.okres;
      okres = (okres === val) ? null : val;
      chips.forEach(function (x) {{
        x.setAttribute('aria-pressed', String(x.dataset.okres === okres));
      }});
      draw();
    }});
  }});

  reset.addEventListener('click', function () {{
    q.value = ''; typ.value = ''; okres = null;
    chips.forEach(function (x) {{ x.setAttribute('aria-pressed', 'false'); }});
    draw(); q.focus();
  }});

  q.addEventListener('input', draw);
  typ.addEventListener('change', draw);
  sort.addEventListener('change', draw);
  draw();
}})();
</script>
</body></html>"""

    try:
        p.write_text(doc, encoding="utf-8")
    except OSError as exc:
        log.error("Zápis webstránky zlyhal (%s): %s", p, exc)
        return False

    log.info("Webstránka: %s (%d ponúk)", p.resolve(), len(listings))
    return True
