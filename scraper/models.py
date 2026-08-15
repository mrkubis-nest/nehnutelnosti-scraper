"""Dátový model jednej ponuky."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

BASE_URL = "https://www.nehnutelnosti.sk"

# Hodnota advertiser.type, ktorú web zobrazuje ako "Priamo od majiteľa".
PRIVATE_OWNER = "PRIVATE_PERSON"


@dataclass
class Listing:
    id: str
    title: str
    url: str
    price: str = ""
    price_num: int | None = None
    unit_price: str = ""
    area: float | None = None
    category: str = ""
    transaction: str = ""
    state: str = ""
    location: str = ""
    city: str = ""
    district: str = ""
    county: str = ""
    advertiser_name: str = ""
    advertiser_type: str = ""
    created_at: str = ""
    updated_at: str = ""
    # Kedy ponuku prvýkrát zachytil scraper. Dopĺňa sa až pri čítaní
    # z databázy, v surových dátach z webu tento údaj nie je.
    first_seen: str = ""
    description: str = ""
    photo: str = ""
    photos: list[str] = field(default_factory=list)

    @property
    def is_private_owner(self) -> bool:
        return self.advertiser_type == PRIVATE_OWNER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_raw(cls, raw: dict[str, Any], resolve=None) -> "Listing":
        """Poskladá Listing z objektu vytiahnutého zo SSR dát webu.

        `resolve` je voliteľná funkcia na rozbalenie RSC referencií
        (web niektoré dlhé texty ukladá ako odkaz typu "$33").
        """
        resolve = resolve or (lambda v: v if isinstance(v, str) and not v.startswith("$") else "")

        params = raw.get("parameters") or {}
        cat = params.get("category") or {}
        loc = raw.get("location") or {}
        adv = raw.get("advertiser") or {}
        price = raw.get("price") or {}
        if not isinstance(price, dict):  # niekedy je to referencia
            price = {}

        photos = [
            p["url"] for p in (raw.get("photos") or [])
            if isinstance(p, dict) and p.get("url")
        ]

        listing_id = raw.get("id", "")
        sef = raw.get("sefName") or ""
        url = f"{BASE_URL}/detail/{listing_id}/{sef}" if sef else f"{BASE_URL}/detail/{listing_id}"

        return cls(
            id=listing_id,
            title=raw.get("title", "") or "",
            url=url,
            price=str(price.get("price") or ""),
            price_num=price.get("priceNum") if isinstance(price.get("priceNum"), int) else None,
            unit_price=str(price.get("unitPrice") or ""),
            area=params.get("area") if isinstance(params.get("area"), (int, float)) else None,
            category=str(cat.get("subValue") or cat.get("mainValue") or ""),
            transaction=str(params.get("transaction") or ""),
            state=str(params.get("realEstateState") or ""),
            location=str(loc.get("name") or ""),
            city=str(loc.get("city") or ""),
            district=str(loc.get("district") or ""),
            county=str(loc.get("county") or ""),
            advertiser_name=str(adv.get("name") or ""),
            advertiser_type=str(adv.get("type") or ""),
            created_at=str(raw.get("createdAt") or ""),
            updated_at=str(raw.get("updatedAt") or ""),
            description=(resolve(raw.get("description")) or "").strip(),
            photo=photos[0] if photos else "",
            photos=photos,
        )
