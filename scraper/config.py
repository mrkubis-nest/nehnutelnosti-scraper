"""Načítanie nastavení z .env a config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "ano", "áno")


@dataclass
class Settings:
    email_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_from: str
    email_to: list[str]
    email_on_empty: bool

    excel_enabled: bool
    excel_path: str
    web_enabled: bool
    web_path: str
    csv_enabled: bool
    csv_path: str
    html_enabled: bool
    html_path: str

    sheets_enabled: bool
    google_credentials_file: str
    spreadsheet_id: str
    worksheet: str

    request_delay: float
    request_timeout: int
    max_retries: int
    db_path: str
    log_level: str

    def validate_email(self) -> list[str]:
        problems = []
        if not self.smtp_user:
            problems.append("SMTP_USER nie je vyplnené")
        if not self.smtp_password:
            problems.append(
                "SMTP_PASSWORD nie je vyplnené – vygeneruj App Password na "
                "https://myaccount.google.com/apppasswords"
            )
        if not self.email_to:
            problems.append("EMAIL_TO nie je vyplnené")
        return problems

    def validate_sheets(self) -> list[str]:
        problems = []
        if not self.spreadsheet_id:
            problems.append("SHEETS_SPREADSHEET_ID nie je vyplnené")
        cred = Path(self.google_credentials_file)
        if not cred.is_absolute():
            cred = ROOT / cred
        if not cred.exists():
            problems.append(f"súbor s kľúčom '{cred}' neexistuje")
        return problems


def load_settings(env_file: str | Path | None = None) -> Settings:
    load_dotenv(env_file or ROOT / ".env")
    recipients = [a.strip() for a in os.getenv("EMAIL_TO", "").split(",") if a.strip()]
    return Settings(
        email_enabled=_bool("EMAIL_ENABLED", True),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", "").replace(" ", ""),
        email_from=os.getenv("EMAIL_FROM", "") or os.getenv("SMTP_USER", ""),
        email_to=recipients,
        email_on_empty=_bool("EMAIL_ON_EMPTY", False),
        excel_enabled=_bool("EXCEL_ENABLED", True),
        excel_path=os.getenv("EXCEL_PATH", "data/ponuky.xlsx"),
        web_enabled=_bool("WEB_ENABLED", False),
        web_path=os.getenv("WEB_PATH", "public/index.html"),
        csv_enabled=_bool("CSV_ENABLED", False),
        csv_path=os.getenv("CSV_PATH", "data/ponuky.csv"),
        html_enabled=_bool("HTML_ENABLED", False),
        html_path=os.getenv("HTML_PATH", "data/ponuky.html"),
        sheets_enabled=_bool("SHEETS_ENABLED", False),
        google_credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        spreadsheet_id=os.getenv("SHEETS_SPREADSHEET_ID", ""),
        worksheet=os.getenv("SHEETS_WORKSHEET", "Ponuky"),
        request_delay=float(os.getenv("REQUEST_DELAY", "1.2")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        db_path=os.getenv("DB_PATH", "data/seen.sqlite3"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def load_search_config(path: str | Path | None = None) -> dict:
    with open(path or ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
