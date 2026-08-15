"""SQLite databáza už videných ponúk – aby ti to isté neprišlo dvakrát."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Listing

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    title           TEXT,
    url             TEXT,
    price           TEXT,
    price_num       INTEGER,
    area            REAL,
    category        TEXT,
    location        TEXT,
    district        TEXT,
    advertiser_name TEXT,
    advertiser_type TEXT,
    created_at      TEXT,
    first_seen      TEXT,
    last_seen       TEXT,
    notified        INTEGER DEFAULT 0,
    raw             TEXT
);
CREATE INDEX IF NOT EXISTS idx_notified ON listings(notified);
CREATE INDEX IF NOT EXISTS idx_type     ON listings(advertiser_type);

CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    found      INTEGER,
    private    INTEGER,
    new        INTEGER
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @property
    def is_first_run(self) -> bool:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()
        return row["c"] == 0

    def filter_new(self, listings: list[Listing]) -> list[Listing]:
        """Vráti tie ponuky, ktoré ešte nikdy neboli v databáze."""
        if not listings:
            return []
        known = {
            r["id"] for r in self.conn.execute(
                "SELECT id FROM listings WHERE id IN (%s)"
                % ",".join("?" * len(listings)),
                [l.id for l in listings],
            )
        }
        return [l for l in listings if l.id not in known]

    def upsert(self, listings: list[Listing], notified: bool = False) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                l.id, l.title, l.url, l.price, l.price_num, l.area, l.category,
                l.location, l.district, l.advertiser_name, l.advertiser_type,
                l.created_at, now, now, 1 if notified else 0,
                json.dumps(l.to_dict(), ensure_ascii=False),
            )
            for l in listings
        ]
        self.conn.executemany(
            """
            INSERT INTO listings (id, title, url, price, price_num, area, category,
                                  location, district, advertiser_name, advertiser_type,
                                  created_at, first_seen, last_seen, notified, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = excluded.last_seen,
                price     = excluded.price,
                price_num = excluded.price_num,
                raw       = excluded.raw
            """,
            rows,
        )
        self.conn.commit()

    def log_run(self, found: int, private: int, new: int) -> None:
        self.conn.execute(
            "INSERT INTO runs (started_at, found, private, new) VALUES (?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), found, private, new),
        )
        self.conn.commit()

    def all_private(self, seen_within_days: int | None = None) -> list[Listing]:
        """Ponuky od majiteľa z databázy, od najnovšej.

        `seen_within_days` vynechá ponuky, ktoré scraper už dlhšie nevidel –
        tie sú s najväčšou pravdepodobnosťou predané alebo stiahnuté a viedli
        by na neexistujúcu stránku.
        """
        sql = ("SELECT raw, first_seen FROM listings "
               "WHERE advertiser_type='PRIVATE_PERSON'")
        params: list = []
        if seen_within_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(seen_within_days))
            sql += " AND last_seen >= ?"
            params.append(cutoff.isoformat())
        sql += " ORDER BY created_at DESC"

        rows = self.conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            try:
                listing = Listing(**json.loads(r["raw"]))
            except (json.JSONDecodeError, TypeError):
                continue
            listing.first_seen = r["first_seen"] or ""
            out.append(listing)
        return out

    def stats(self) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) c FROM listings WHERE advertiser_type='PRIVATE_PERSON'"
        ).fetchone()["c"]
        runs = self.conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        last = self.conn.execute(
            "SELECT started_at, new FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "private_total": total,
            "runs": runs,
            "last_run": last["started_at"] if last else None,
            "last_new": last["new"] if last else None,
        }

    def close(self) -> None:
        self.conn.close()
