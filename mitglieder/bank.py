"""Kontoinformationsdienst-Anbindung für den Beitragsabgleich (F-59, § 4 Abs 3).

Angebunden wird GoCardless Bank Account Data (PSD2-Kontoinformationsdienst,
Berlin-Group-Schema) — nur lesend, nur das Vereinskonto. Grundsätze:

* Die Zustimmung erteilt die Kontoinhaberin bzw. der Kontoinhaber selbst im
  eigenen Online-Banking (Weiterleitung über den Dienst); die Plattform sieht
  nie Bankzugangsdaten und speichert von den Umsätzen nur das Abgleichsergebnis.
* PSD2 erlaubt wenige unbegleitete Abrufe pro Tag — die `Bankkopplung` führt
  darüber Buch (Standard: 4). Abgerufen wird, wenn ein Mitglied „Ich habe
  überwiesen" meldet oder die Verwaltung nachsieht — nicht auf Verdacht.
* Fällt der Dienst aus, scheitert der Abgleich leise und ehrlich: Kein Konto
  wird deshalb schlechter gestellt; der nächste Abruf holt alles nach (die
  Umsatzhistorie überlappt bewusst um Tage).
"""

from __future__ import annotations

import time

import requests
from django.conf import settings
from django.utils import timezone

from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Bankkopplung, Mitglied, beitrag_verbuchen
from plattform_core.beitraege import eingaenge_zuordnen, name_passt

API = "https://bankaccountdata.gocardless.com/api/v2"
ZEITLIMIT = 15  # Sekunden je HTTP-Aufruf
ABRUF_TAGE = 14  # Umsatzfenster je Abruf — überlappt bewusst (Dedupe über Umsatz-ID)

_token_cache: tuple[str, float] = ("", 0.0)


def eingerichtet() -> bool:
    return bool(settings.DDOE_BANK_SECRET_ID and settings.DDOE_BANK_SECRET_KEY)


def _token() -> str:
    """Zugriffstoken des Dienstes — im Prozess zwischengespeichert (~24 h gültig)."""
    global _token_cache
    wert, bis = _token_cache
    if wert and time.monotonic() < bis:
        return wert
    antwort = requests.post(
        f"{API}/token/new/",
        json={
            "secret_id": settings.DDOE_BANK_SECRET_ID,
            "secret_key": settings.DDOE_BANK_SECRET_KEY,
        },
        timeout=ZEITLIMIT,
    )
    antwort.raise_for_status()
    daten = antwort.json()
    _token_cache = (daten["access"], time.monotonic() + int(daten.get("access_expires", 86400)) - 300)
    return _token_cache[0]


def _get(pfad: str, **params) -> dict:
    antwort = requests.get(
        f"{API}{pfad}", headers={"Authorization": f"Bearer {_token()}"}, params=params, timeout=ZEITLIMIT
    )
    antwort.raise_for_status()
    return antwort.json()


def _post(pfad: str, daten: dict) -> dict:
    antwort = requests.post(
        f"{API}{pfad}", headers={"Authorization": f"Bearer {_token()}"}, json=daten, timeout=ZEITLIMIT
    )
    antwort.raise_for_status()
    return antwort.json()


def institutionen() -> list[dict]:
    """Österreichische Banken des Dienstes: [{id, name}, …] — für die Kopplungsauswahl."""
    return [
        {"id": i["id"], "name": i["name"]}
        for i in _get("/institutions/", country="at")
    ]


def kopplung_starten(institution_id: str) -> str:
    """Beginnt die Kopplung: legt Zustimmung und Anfrage beim Dienst an und gibt
    den Link zurück, unter dem die Kontoinhaberin im eigenen Banking zustimmt."""
    zustimmung = _post(
        "/agreements/enduser/",
        {
            "institution_id": institution_id,
            "max_historical_days": 90,
            "access_valid_for_days": 180,
            "access_scope": ["transactions"],
        },
    )
    anfrage = _post(
        "/requisitions/",
        {
            "redirect": f"{settings.DDOE_BASIS_URL}/verwaltung/bank/rueckkehr/",
            "institution_id": institution_id,
            "agreement": zustimmung["id"],
            "reference": f"ddoe-{int(time.time())}",
        },
    )
    Bankkopplung.objects.create(
        requisition_id=anfrage["id"], institution_id=institution_id, aktiv=False
    )
    return anfrage["link"]


def kopplung_abschliessen() -> Bankkopplung | None:
    """Nach der Rückkehr aus dem Banking: Konto übernehmen und Kopplung scharf schalten."""
    kopplung = Bankkopplung.objects.filter(account_id="").order_by("-gekoppelt_am").first()
    if kopplung is None:
        return None
    daten = _get(f"/requisitions/{kopplung.requisition_id}/")
    konten = daten.get("accounts") or []
    if daten.get("status") != "LN" or not konten:
        return None
    Bankkopplung.objects.filter(aktiv=True).update(aktiv=False)
    kopplung.account_id = konten[0]
    kopplung.consent_bis = timezone.localdate() + timezone.timedelta(days=180)
    kopplung.aktiv = True
    kopplung.save(update_fields=["account_id", "consent_bis", "aktiv"])
    return kopplung


def _offene_referenzen() -> dict[str, int]:
    """Beitragsreferenz → Mitglieds-ID für alle Konten, denen ein Eingang guttäte."""
    referenzen = {}
    for m in Mitglied.objects.filter(is_active=True).only("pk", "username"):
        referenzen[beitragsreferenz(m)] = m.pk
    return referenzen


def abgleich_ausfuehren(erzwungen: bool = False) -> tuple[int, str]:
    """Ruft Umsätze ab und verbucht alle Referenz-Treffer. Rückgabe (neu, meldung).

    Hält das Tageskontingent ein (`erzwungen` übergeht nur die Abstands-,
    nie die Kontingentgrenze). Jeder Treffer läuft durch `beitrag_verbuchen`
    (idempotent) — mit Namensvergleich, dessen Ergebnis als bloßes Ja/Nein
    gespeichert wird.
    """
    if not eingerichtet():
        return 0, "bank_nicht_eingerichtet"
    kopplung = Bankkopplung.aktuelle()
    if kopplung is None:
        return 0, "keine_kopplung"
    if not kopplung.abruf_erlaubt():
        return 0, "kontingent_erschoepft"

    date_from = (timezone.localdate() - timezone.timedelta(days=ABRUF_TAGE)).isoformat()
    try:
        daten = _get(f"/accounts/{kopplung.account_id}/transactions/", date_from=date_from)
    except (requests.RequestException, OSError) as fehler:
        return 0, f"abruf_gescheitert:{type(fehler).__name__}"
    kopplung.abruf_vermerken()

    gebucht = daten.get("transactions", {}).get("booked", [])
    treffer = eingaenge_zuordnen(gebucht, _offene_referenzen())
    mitglieder = Mitglied.objects.in_bulk([mid for mid, _e in treffer])
    neu = 0
    for mid, eingang in treffer:
        mitglied = mitglieder.get(mid)
        if mitglied is None:
            continue
        ok = name_passt(eingang.absender, mitglied.first_name, mitglied.last_name)
        if beitrag_verbuchen(mitglied, eingang, namens_ok=ok):
            neu += 1
    return neu, "ok"
