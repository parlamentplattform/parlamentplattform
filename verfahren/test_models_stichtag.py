"""Der Stichtag der Stimmberechtigung (§ 4 Abs 4 lit a) ist ein Wiener Kalendertag.

Befund #32: `phase_beginn.date()` lieferte das UTC-Datum. Beginnt eine Abstimmung zwischen
0 und 2 Uhr Wiener Zeit, lag der Stichtag damit einen Tag vor dem Beginn, den die Seite zeigte —
und wer seine Anwartschaft genau an diesem Tag erfüllte, war nicht stimmberechtigt."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

WIEN = ZoneInfo("Europe/Vienna")


def test_der_stichtag_ist_der_wiener_kalendertag_nicht_das_utc_datum(ordnung, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False  # die Anwartschaft nach § 4 Abs 4 gilt voll
    antrag = antrag_einbringen(mitglied_anlegen("stellerin"), **ANTRAG, ordnung=ordnung)
    for name in ("u1", "u2"):
        antrag.unterstuetzungen.create(mitglied=mitglied_anlegen(name))
    antrag.fortschreiben()
    assert antrag.phase == "beratung"
    # Anwartschaft für Sachfragen: drei Monate — am 1.7. erfüllt, am 30.6. noch nicht.
    knapp = mitglied_anlegen("knapp")
    knapp.beitritt = date(2026, 4, 1)
    knapp.save(update_fields=["beitritt"])

    beginn = datetime(2026, 6, 10, 0, 30, tzinfo=WIEN)
    antrag.phase_beginn = beginn
    antrag.save(update_fields=["phase_beginn"])
    wirksam = beginn + timedelta(days=antrag.policy().beratung_tage)  # 1.7. 00:30 MESZ
    assert wirksam.astimezone(UTC).date() == date(2026, 6, 30), "UTC liegt einen Tag zurück"

    antrag.fortschreiben(wirksam + timedelta(hours=1))
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung" and antrag.phase_beginn == wirksam
    assert antrag.stimmberechtigung_stichtag == date(2026, 7, 1)
    assert antrag.stichtag_der_stimmberechtigung() == date(2026, 7, 1)
    assert antrag.stimmberechtigte_anzahl == 4, "auch, wer die Anwartschaft genau am Stichtag erfüllt"


def test_ohne_gespeicherten_stichtag_gilt_der_wiener_tag_des_phasenbeginns(ordnung):  # noqa: F811
    """Ältere Verfahren (vor Migration 0017) tragen keinen Stichtag — der Rückfall ist trotzdem
    der Kalendertag, nicht das UTC-Datum."""
    antrag = antrag_einbringen(mitglied_anlegen("stellerin"), **ANTRAG, ordnung=ordnung)
    antrag.phase = "abstimmung"
    antrag.phase_beginn = datetime(2026, 7, 1, 0, 30, tzinfo=WIEN)
    antrag.save(update_fields=["phase", "phase_beginn"])
    antrag.refresh_from_db()  # aus der Datenbank kommt der Wert UTC-bewusst — so liest ihn jede Ansicht
    assert antrag.stimmberechtigung_stichtag is None
    assert antrag.stichtag_der_stimmberechtigung() == date(2026, 7, 1)
    assert antrag.phase_beginn.date() == date(2026, 6, 30)  # genau der alte Fehler
