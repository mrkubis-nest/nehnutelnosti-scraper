"""Zapisovanie ponúk do Google Sheets."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .config import ROOT, Settings
from .models import Listing

log = logging.getLogger(__name__)

HEADER = [
    "Pridané", "Dátum inzerátu", "Titul", "Cena", "Cena €", "€/m²", "Plocha m²",
    "Kategória", "Stav", "Lokalita", "Okres", "Majiteľ", "Odkaz",
]


def _row(l: Listing) -> list:
    return [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        (l.created_at or "")[:10],
        l.title,
        l.price,
        l.price_num if l.price_num is not None else "",
        l.unit_price,
        l.area if l.area is not None else "",
        l.category,
        l.state,
        l.location,
        l.district,
        l.advertiser_name,
        l.url,
    ]


def append(settings: Settings, listings: list[Listing]) -> bool:
    """Pripojí ponuky ako nové riadky. Vráti True pri úspechu."""
    if not listings:
        return True

    problems = settings.validate_sheets()
    if problems:
        for p in problems:
            log.error("Google Sheets nie je nastavené: %s", p)
        return False

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        log.error("Chýbajú balíky. Spusti: pip install gspread google-auth")
        return False

    cred_path = Path(settings.google_credentials_file)
    if not cred_path.is_absolute():
        cred_path = ROOT / cred_path

    try:
        creds = Credentials.from_service_account_file(
            str(cred_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(settings.spreadsheet_id)

        try:
            ws = sheet.worksheet(settings.worksheet)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(settings.worksheet, rows=1000, cols=len(HEADER))
            ws.append_row(HEADER, value_input_option="USER_ENTERED")
            ws.freeze(rows=1)

        if not ws.get_all_values():
            ws.append_row(HEADER, value_input_option="USER_ENTERED")
            ws.freeze(rows=1)

        ws.append_rows([_row(l) for l in listings], value_input_option="USER_ENTERED")

    except Exception as exc:
        msg = str(exc)
        if "PERMISSION_DENIED" in msg or "403" in msg:
            log.error(
                "Google Sheets odmietol prístup. Nezabudol si tabuľku zdieľať "
                "s emailom service accountu (client_email z credentials.json) "
                "ako Editor?"
            )
        else:
            log.error("Zápis do Google Sheets zlyhal: %s", exc)
        return False

    log.info("Zapísaných %d riadkov do Google Sheets", len(listings))
    return True
