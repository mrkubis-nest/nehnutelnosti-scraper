"""Odosielanie emailu s novými ponukami cez SMTP."""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from .config import Settings
from .models import Listing

log = logging.getLogger(__name__)

from .export_local import cat_sk as _cat


def _card(l: Listing) -> str:
    e = html.escape
    photo = (
        f'<img src="{e(l.photo)}" width="200" alt="" '
        f'style="width:200px;height:140px;object-fit:cover;border-radius:6px;display:block">'
        if l.photo else
        '<div style="width:200px;height:140px;background:#eef1f5;border-radius:6px"></div>'
    )
    bits = []
    if l.area:
        bits.append(f"{l.area:g} m²")
    if _cat(l):
        bits.append(e(_cat(l)))
    if l.state:
        bits.append(e(l.state))
    meta = " · ".join(bits)

    desc = l.description.strip().replace("\n", " ")
    if len(desc) > 260:
        desc = desc[:260].rsplit(" ", 1)[0] + "…"
    desc_html = (
        f'<p style="margin:8px 0 0;color:#5b6470;font-size:13px;line-height:1.5">{e(desc)}</p>'
        if desc else ""
    )

    return f"""
    <table cellpadding="0" cellspacing="0" border="0" width="100%"
           style="margin:0 0 16px;border:1px solid #e3e7ec;border-radius:10px;
                  background:#fff;border-collapse:separate">
      <tr>
        <td width="216" valign="top" style="padding:16px 0 16px 16px">{photo}</td>
        <td valign="top" style="padding:16px">
          <a href="{e(l.url)}" style="color:#12263f;font-size:16px;font-weight:600;
             text-decoration:none;line-height:1.35">{e(l.title)}</a>
          <p style="margin:6px 0 0;color:#6b7480;font-size:13px">📍 {e(l.location)}</p>
          <p style="margin:10px 0 0">
            <span style="font-size:20px;font-weight:700;color:#0b7a52">{e(l.price) or 'Cena dohodou'}</span>
            {f'<span style="color:#8a929c;font-size:13px"> &nbsp;{e(l.unit_price)}</span>' if l.unit_price else ''}
          </p>
          <p style="margin:8px 0 0;color:#6b7480;font-size:13px">{meta}</p>
          {desc_html}
          <p style="margin:12px 0 0">
            <span style="display:inline-block;background:#e8f5ee;color:#0b7a52;font-size:12px;
                         font-weight:600;padding:4px 10px;border-radius:20px">
              Priamo od majiteľa{f' · {e(l.advertiser_name)}' if l.advertiser_name else ''}
            </span>
          </p>
          <p style="margin:12px 0 0">
            <a href="{e(l.url)}" style="display:inline-block;background:#12263f;color:#fff;
               font-size:13px;font-weight:600;text-decoration:none;padding:9px 18px;
               border-radius:6px">Zobraziť inzerát →</a>
          </p>
        </td>
      </tr>
    </table>"""


def build_html(listings: list[Listing]) -> str:
    cards = "".join(_card(l) for l in listings)
    n = len(listings)
    word = "nová ponuka" if n == 1 else ("nové ponuky" if 2 <= n <= 4 else "nových ponúk")
    return f"""<!doctype html>
<html lang="sk"><body style="margin:0;padding:24px 12px;background:#f4f6f8;
      font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif">
  <table cellpadding="0" cellspacing="0" border="0" width="100%"
         style="max-width:680px;margin:0 auto">
    <tr><td>
      <h1 style="margin:0 0 4px;font-size:22px;color:#12263f">
        {n} {word} priamo od majiteľa
      </h1>
      <p style="margin:0 0 20px;color:#6b7480;font-size:14px">
        Bratislavský kraj · predaj · nehnutelnosti.sk
      </p>
      {cards}
      <p style="margin:24px 0 0;color:#9aa2ad;font-size:12px;text-align:center">
        Automatická správa z tvojho scrapera. Ponuky bez realitnej kancelárie.
      </p>
    </td></tr>
  </table>
</body></html>"""


def build_text(listings: list[Listing]) -> str:
    lines = [f"{len(listings)} nových ponúk priamo od majiteľa (Bratislavský kraj, predaj)", ""]
    for i, l in enumerate(listings, 1):
        lines += [
            f"{i}. {l.title}",
            f"   {l.price or 'Cena dohodou'}"
            + (f" ({l.unit_price})" if l.unit_price else "")
            + (f" · {l.area:g} m²" if l.area else ""),
            f"   {l.location}",
            f"   {l.url}",
            "",
        ]
    return "\n".join(lines)


def send(settings: Settings, listings: list[Listing]) -> bool:
    """Pošle email. Vráti True pri úspechu."""
    problems = settings.validate_email()
    if problems:
        for p in problems:
            log.error("Email nie je nastavený: %s", p)
        return False

    n = len(listings)
    msg = EmailMessage()
    msg["Subject"] = (
        f"🏠 {n} {'nová ponuka' if n == 1 else 'nových ponúk'} od majiteľa – Bratislavský kraj"
        if n else "🏠 Žiadne nové ponuky od majiteľa"
    )
    msg["From"] = formataddr(("Nehnuteľnosti scraper", settings.email_from))
    msg["To"] = ", ".join(settings.email_to)

    if n:
        msg.set_content(build_text(listings))
        msg.add_alternative(build_html(listings), subtype="html")
    else:
        msg.set_content("Za posledný beh nepribudli žiadne nové ponuky priamo od majiteľa.")

    try:
        context = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                  context=context, timeout=30) as s:
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
                s.starttls(context=context)
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        log.error(
            "SMTP prihlásenie zlyhalo. Pri Gmaile musíš použiť App Password "
            "(https://myaccount.google.com/apppasswords), nie bežné heslo."
        )
        return False
    except Exception as exc:
        log.error("Email sa nepodarilo odoslať: %s", exc)
        return False

    log.info("Email odoslaný na %s", ", ".join(settings.email_to))
    return True
