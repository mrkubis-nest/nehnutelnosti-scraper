# Nehnuteľnosti.sk — ponuky priamo od majiteľa

Automaticky prehľadáva **nehnutelnosti.sk**, vyberie ponuky na **predaj v Bratislavskom
kraji, ktoré sú priamo od majiteľa** (bez realitnej kancelárie), a uloží ich
do lokálnej excelovskej databázy **`data/ponuky.xlsx`**.

Súbor sa pri každom behu prepíše celý z databázy, takže vždy obsahuje kompletný
a aktuálny zoznam — nie len posledný prírastok. Obsahuje dva hárky:

- **Ponuky** — jeden riadok = jedna ponuka, štyri stĺpce:
  **Lokalita · Inzerent · Typ nehnuteľnosti · Odkaz na ponuku**.
  Zapnutý filter a zmrazená hlavička, odkaz je preklik na inzerát.
  Nové ponuky majú zelený podklad.
- **Prehľad** — počty podľa okresu a typu nehnuteľnosti.

Žiadne obrázky, len text. Scraper si pamätá, čo už videl, takže tú istú ponuku
neoznačí ako novú dvakrát. CSV, HTML prehľad s fotkami, Google Sheets a email
sú pripravené ako voliteľné doplnky (vypnuté).

---

## Rýchly štart

```bash
cd C:\Users\User\Desktop\Websites\nehnutelnosti-scraper
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Skopíruj `.env.example` na `.env` a spusti:

```bash
.\.venv\Scripts\python run.py
```

Nič ďalšie netreba nastavovať. Výsledok nájdeš v `data/ponuky.xlsx`.

Na rýchle vyskúšanie bez zápisu:

```bash
.\.venv\Scripts\python run.py --dry-run --limit 1
```

---

## Ako to funguje

Web nemá filter „priamo od majiteľa" v URL a stránkovanie končí na **33. strane**
(~990 inzerátov), pričom v kraji je cez 9 000 ponúk na predaj. Preto scraper:

1. **Rozdelí hľadanie** na dvojice *kategória × okres* (napr. `byty/bratislava-ii`),
   aby sa žiadna ponuka neschovala za limitom stránkovania. Ak je partícia aj tak
   priveľká, rozdelí ju ešte na podkategórie.
2. **Číta dáta priamo zo SSR**. Web beží na Next.js a kompletné údaje o inzerátoch
   posiela v HTML ako JSON. Scraper ich vytiahne odtiaľ, nie z HTML tried — tie sa
   menia pri každom builde webu, JSON nie.
3. **Filtruje na majiteľov** podľa poľa `advertiser.type == "PRIVATE_PERSON"`, čo je
   presne to, čo web zobrazuje ako štítok „Priamo od majiteľa".
4. **Odsieva firmy podľa mena inzerenta** — viď nižšie.
5. **Zahodí ponuky staršie ako 4 mesiace** (`max_age_days: 120` v `config.yaml`).
6. **Porovná s databázou** (`data/seen.sqlite3`), aby označil, čo je naozaj nové.

### Prečo dve vrstvy filtrovania realitiek

Web označuje inzerenta ako súkromnú osobu **podľa typu účtu**, nie podľa toho,
či podniká s realitami. Na reálnych dátach sa ukázalo, že spomedzi 460 ponúk
označených ako „od majiteľa" ich **14 pochádzalo od firiem** inzerujúcich zo
súkromného účtu — napríklad *Reality Market*, *N HOMES sro*, *Pride Group*,
*Archcom Reality* či *FAREN Realitná kancelária*.

Preto je druhou vrstvou kontrola mena inzerenta proti zoznamu vzorov
`exclude_advertiser_patterns` v `config.yaml`. Zoznam je zámerne konzervatívny:
radšej prepustí firmu, než by odfiltroval človeka s nezvyklým priezviskom.
Ktoré ponuky vyhodil, vypíše pri každom behu do logu — keby ti niektorý vzor
vyhadzoval aj skutočného majiteľa, stačí ten riadok z `config.yaml` zmazať.

> **Presnosť filtra je overená:** na testovacích stránkach počet štítkov
> „Priamo od majiteľa" v HTML presne sedel s počtom `PRIVATE_PERSON` v dátach
> (33 zhôd z 33, vrátane stránky s 23 štítkami).

Namerané na reálnom behu (august 2026): **347 requestov, 17 minút,
9 465 prehľadaných ponúk, z toho 459 priamo od majiteľa** (4,9 %).
Medzi requestami drží pauzu 1,2 s. Scraper číta len `/vysledky/...`,
čo `robots.txt` webu povoľuje (`/api/` je zakázané a nepoužíva sa).

### Prečo nie ScrapeGraphAI

Pôvodný zámer bol postaviť to na [ScrapeGraphAI](https://github.com/ScrapeGraphAI/Scrapegraph-ai),
teda na LLM extrakcii. Pri prieskume webu sa ukázalo, že to nedáva zmysel:

- Údaje o inzerátoch sú na stránke **už ako štruktúrovaný JSON** — netreba ich
  z ničoho „vyčítavať". LLM by hádal to, čo je exaktne dané.
- Typ inzerenta je jednoznačné pole `advertiser.type`. Deterministický zápis je
  presnejší než akýkoľvek model a nemá ako halucinovať.
- Jeden beh spracuje ~9 500 inzerátov. Cez LLM by to boli tisíce volaní a
  reálne náklady za každý beh, pri nulovom prínose oproti čítaniu JSON-u.
- Bez LLM nie sú potrebné žiadne API kľúče ani `playwright` — appka je rádovo
  jednoduchšia a rýchlejšia.

ScrapeGraphAI by sa oplatil, ak by bolo treba ťahať údaje z **neštruktúrovaného
textu** — napríklad vyparsovať z voľného popisu „poschodie, orientácia, stav
kúpeľne". To by bol zmysluplný ďalší krok, nie náhrada tohto jadra.

---

## Voliteľne: Google Sheets

Zatiaľ vypnuté (`SHEETS_ENABLED=false`) — lokálne CSV a HTML stačia.
Keby si to neskôr chcel, potrebuješ *service account*, teda technický
Google účet, ktorý bude do tabuľky písať.

**1. Vytvor projekt a zapni API**
   - Choď na [console.cloud.google.com](https://console.cloud.google.com/)
   - Vytvor nový projekt (napr. „nehnutelnosti-scraper")
   - V *APIs & Services → Library* zapni **Google Sheets API**

**2. Vytvor service account**
   - *APIs & Services → Credentials → Create Credentials → Service account*
   - Daj mu meno, ostatné kroky preskoč (*Continue* → *Done*)
   - Klikni na vytvorený účet → záložka **Keys** → *Add Key → Create new key → JSON*
   - Stiahne sa `.json` súbor — **premenuj ho na `credentials.json`** a daj
     do priečinka `nehnutelnosti-scraper`

**3. Vytvor tabuľku a zdieľaj ju**
   - Vytvor nový [Google Sheet](https://sheets.new)
   - Otvor `credentials.json` a nájdi hodnotu `client_email`
     (vyzerá ako `nieco@nieco.iam.gserviceaccount.com`)
   - V tabuľke daj **Share** a pridaj tento email ako **Editor**
   - ⚠️ Bez tohto kroku zápis zlyhá na `PERMISSION_DENIED`

**4. Doplň ID tabuľky do `.env`**

   ID je časť URL medzi `/d/` a `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/1AbCdEfGh...XyZ/edit
                                          └──── toto ────┘
   ```
   ```
   SHEETS_ENABLED=true
   SHEETS_SPREADSHEET_ID=1AbCdEfGh...XyZ
   ```

**5. Otestuj**

```bash
.\.venv\Scripts\python run.py --test-sheets
```

Do tabuľky by mal pribudnúť jeden skúšobný riadok. Pokojne ho potom zmaž.

---

## Spúšťanie

```bash
.\.venv\Scripts\python run.py
```

| Prepínač | Čo robí |
|---|---|
| *(bez prepínača)* | Nájde nové ponuky a prekreslí `ponuky.xlsx` |
| `--dry-run` | Len vypíše, nič nezapíše ani neuloží |
| `--limit N` | Prehľadá len prvých N okresov (rýchly test) |
| `--stats` | Čo je zatiaľ v databáze |
| `--all` | Zapíše všetky nájdené, nielen nové |
| `--test-sheets` | Overí pripojenie na Google Sheets (ak si ho zapol) |

**Prvý beh** nájde stovky ponúk. V Exceli budú **všetky**, ale ako `Nové`
sa označia len tie z posledných 30 dní — inak by bol celý súbor zelený
a nevidel by si, čo naozaj pribudlo. Hranicu zmeníš v `config.yaml`
cez `first_run_max_age_days`.

---

## Automatické spúšťanie

Máš dve možnosti. **Cloud je lepší**, lebo nepotrebuje tvoj zapnutý počítač
a rovno rieši aj zdieľanie s ďalšími ľuďmi.

### A) V cloude cez GitHub Actions — odporúčané

Scrapuje 3× denne na serveroch GitHubu a výsledok publikuje ako webstránku,
ktorej odkaz môžeš poslať komukoľvek. Zadarmo.

**1. Vytvor repozitár a nahraj projekt**

```bash
cd C:\Users\User\Desktop\Websites\nehnutelnosti-scraper
git init
git add .
git commit -m "Scraper ponúk od majiteľa"
```

Potom na [github.com/new](https://github.com/new) vytvor repozitár a nahraj:

```bash
git remote add origin https://github.com/TVOJE-MENO/nehnutelnosti-scraper.git
git branch -M main
git push -u origin main
```

**2. Zapni GitHub Pages**

V repozitári *Settings → Pages → Source* nastav **GitHub Actions**.

**3. Spusti prvý beh**

Záložka *Actions → Scrape nehnutelnosti.sk → Run workflow*. Trvá ~10–15 minút.
Po dobehnutí nájdeš adresu stránky v *Settings → Pages* — vyzerá takto:

```
https://TVOJE-MENO.github.io/nehnutelnosti-scraper/
```

Tú pošleš komukoľvek. Nájde na nej tabuľku s vyhľadávaním aj tlačidlo na
stiahnutie Excelu. Ďalej sa to už aktualizuje samo 3× denne.

**Zmena frekvencie** — v `.github/workflows/scrape.yml` uprav riadok `cron`
(časy sú v UTC, v lete je u nás UTC+2):

```yaml
- cron: "0 5,11,17 * * *"      # 3× denne (7:00, 13:00, 19:00)
- cron: "0 4,8,12,16,20 * * *" # 5× denne
- cron: "0 */4 * * *"          # každé 4 hodiny
```

> **Pozor na limit:** GitHub dáva pri **súkromnom** repozitári 2 000 minút
> mesačne zadarmo. Jeden beh trvá ~10–15 min, takže 3× denne (~1 350 min)
> sa zmestí, 6× denne už nie. Pri **verejnom** repozitári sú minúty
> neobmedzené — ale vtedy sú dáta aj kód verejné, viď poznámku nižšie.

### B) Lokálne cez Plánovač úloh Windows

Beží len keď máš zapnutý počítač a výsledok ostáva u teba.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
```

Predvolene každých 6 hodín. Iný interval:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1 -Time "08:00" -RepeatHours 8
```

Odstránenie:
```powershell
Unregister-ScheduledTask -TaskName "Nehnutelnosti scraper" -Confirm:$false
```

---

## Zdieľanie s ďalšími ľuďmi

| Spôsob | Prístup | Treba účet? | Poznámka |
|---|---|---|---|
| **GitHub Pages** (možnosť A) | ktokoľvek s odkazom | nie | Najjednoduchšie. Stránka je verejná. |
| Súkromný repozitár | pozvaní spolupracovníci | GitHub účet | Stiahnu si `ponuky.xlsx` z repozitára. |
| Zdieľaný priečinok | koho pozveš | Google/Microsoft účet | Nastav `EXCEL_PATH` do priečinka OneDrive alebo Google Drive a zdieľaj ho. Funguje s možnosťou B. |

### Na čo si dať pozor pri verejnej stránke

Stránka na GitHub Pages je **verejná** — kto pozná adresu, uvidí ju.
Adresa sa nedá uhádnuť a stránka má `noindex`, takže ju Google nezaradí
do výsledkov, ale nie je za heslom. Zdieľanie chráneného obsahu heslom
GitHub v bezplatnej verzii neponúka.

V tabuľke sú **mená inzerentov**. Sú to síce údaje, ktoré sú už verejne na
nehnutelnosti.sk, ale zverejniť ich vcelku ako zoznam je predsa len niečo iné
než jednotlivý inzerát. Ak ti to prekáža, sú dve možnosti: nechať repozitár
súkromný a zdieľať iba Excel cez pozvánky do repozitára, alebo v
`scraper/export_web.py` stĺpec s menom z webovej verzie vynechať.

Ak dáš repozitár ako **verejný**, spolu s dátami sprístupníš aj celý kód —
preto v ňom nikdy nesmie skončiť `.env` ani `credentials.json`.
Oba sú v `.gitignore`, ale radšej si to over cez `git status` pred prvým `push`.

---

## Prispôsobenie

V `config.yaml`:

```yaml
transaction: predaj      # alebo: prenajom

filters:
  max_age_days: 120      # ignoruj staršie ako 4 mesiace
  min_price: 100000      # ignoruj lacnejšie
  max_price: 400000      # ignoruj drahšie
  min_area: 45           # ignoruj menšie ako 45 m²
```

Vekový limit platí vždy — pri hľadaní aj pri generovaní Excelu. Ponuka, ktorá
medzičasom prekročí limit, zo súboru pri ďalšom behu zmizne, hoci ostane
v databáze.

### Prečo Excel obsahuje aj ponuky, ktoré posledný beh nenašiel

Web radí výsledky podľa „Odporúčané" a poradie sa medzi behmi mierne mieša.
Pri stránkovaných partíciách sa preto stane, že jeden beh niektorú ponuku
minie, hoci na webe stále je. Merané na reálnych dátach: zo 4 ponúk, ktoré
jeden beh vynechal, boli **3 stále aktívne**.

Preto sa do Excelu berú ponuky videné za posledné `stale_after_days` dni
(predvolene 3), nie len tie z aktuálneho behu. Ponuka musí zmiznúť
z niekoľkých behov za sebou, kým ju scraper vyhodnotí ako stiahnutú.
Cenou je, že predaná ponuka môže v súbore ostať ešte pár dní.

Chceš len byty? Zmaž ostatné položky zo zoznamu `categories`.
Len konkrétne okresy? Uprav `districts`.

---

## Voliteľne: email

V `.env` nastav `EMAIL_ENABLED=true` a doplň `SMTP_PASSWORD`. Pri Gmaile to
**nie je** tvoje bežné heslo, ale 16-znakové *App Password*
z [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
(vyžaduje zapnuté dvojfaktorové overenie). Otestuj cez `run.py --test-email`.

---

## Keď niečo nefunguje

| Príznak | Príčina |
|---|---|
| Nájde 0 ponúk vo všetkých kategóriách | Web pravdepodobne zmenil štruktúru — ozvi sa |
| `presiahla limit stránkovania` | Partícia je väčšia ako 990 ponúk; pridaj podkategórie do `config.yaml` |
| Veľa HTTP 429 | Zvýš `REQUEST_DELAY` v `.env` |
| Rovnaké ponuky znova | Zmazal sa `data/seen.sqlite3` |
| `máš ten súbor otvorený v Exceli?` | Zavri `ponuky.xlsx` a spusti znova — Windows nedovolí prepísať otvorený súbor |
| Rozsypaná diakritika v CSV | Otvor cez *Údaje → Z textu* a zvoľ UTF-8, alebo použi Excel výstup |
| Podozrivo málo ponúk v okrese | Skontroluj prefix `okres-` v `config.yaml` (viď poznámka tam) |
| Chýba ponuka od skutočného majiteľa | Možno ju vyhodil vzor v `exclude_advertiser_patterns` — log vypisuje, koho odfiltroval |
| V Exceli je realitka | Pridaj si vzor do `exclude_advertiser_patterns` v `config.yaml` |
| `PERMISSION_DENIED` pri Sheets | Nezdieľal si tabuľku s `client_email` zo `credentials.json` ako Editor |

---

## Štruktúra

```
run.py                  vstupný bod, CLI
config.yaml             čo hľadať (kategórie, okresy, cenové filtre)
.env                    prístupy a technické nastavenia
scraper/
  fetcher.py            HTTP klient + parser SSR dát webu
  crawler.py            delenie hľadania na partície
  models.py             dátový model ponuky
  store.py              SQLite databáza videných ponúk
  filters.py            vek ponuky + odsievanie firemných inzerentov
  export_excel.py       Excel export (hlavný výstup)
  export_web.py         textová webstránka pre GitHub Pages
  export_local.py       CSV + HTML prehľad s fotkami (voliteľné)
  sheets.py             zápis do Google Sheets (voliteľné)
  notify_email.py       HTML email (voliteľné)
data/
  seen.sqlite3          čo už scraper videl
public/
  index.html            webstránka, ktorá sa publikuje
  ponuky.xlsx           excelovská databáza ponúk
.github/workflows/
  scrape.yml            cloudové spúšťanie 3× denne + publikovanie
scripts/install_task.ps1  registrácia do Plánovača úloh
```

## Poznámka

Scraper je určený na osobné sledovanie ponúk. Drží pauzy medzi requestami
a rešpektuje `robots.txt`. Ak by si zvyšoval frekvenciu, nechaj `REQUEST_DELAY`
aspoň na `1.0`.
