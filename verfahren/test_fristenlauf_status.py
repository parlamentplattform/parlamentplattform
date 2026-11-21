"""GP-155: Ein stehender oder fehlerhafter Fristenlauf ist von außen erkennbar.

Der Fristen-Wächter (verfahren/hintergrund.py, D-J1a) hält seinen Stand nur in der Zeile
`Hintergrundlauf(name="fristen")`. Die Maschinenadresse `/gesund/fristen.json` liest sie — nach dem
Muster von `/sicherung/status.json`: 200 bei einem pünktlichen, fehlerfreien Lauf, sonst 503 —, ohne
Fehlertexte und ohne Personenbezug, damit die äußere Wache darauf prüfen kann."""

from datetime import timedelta

import pytest
from django.utils import timezone

from plattform_core import Phase
from verfahren import hintergrund
from verfahren.models import Antrag, Hintergrundlauf, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

ADRESSE = "/gesund/fristen.json"


def _fristenlauf():
    return next(lauf for lauf in hintergrund.LAEUFE if lauf.name == "fristen")


@pytest.fixture
def laufender_antrag(ordnung):  # noqa: F811
    m = mitglied_anlegen("probe")
    antrag = antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(phase=Phase.UNTERSTUETZUNG.value)
    return antrag


def test_puenktlicher_fehlerfreier_lauf_ist_ok(client):
    assert hintergrund.ausfuehren(_fristenlauf())
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["status"] == "ok" and daten["lauf"] == "fristen"
    assert daten["ueberfaellig"] is False and daten["fehler"] == 0 and daten["abgebrochen"] is False
    assert daten["zuletzt_begonnen"] and daten["zuletzt_beendet"]
    assert "no-cache" in antwort.headers.get("Cache-Control", "")


def test_zurueckdatierter_lauf_ist_ueberfaellig(client, settings):
    settings.DDOE_WAECHTER_MINUTEN = 10
    jetzt = timezone.now()
    assert hintergrund.ausfuehren(_fristenlauf(), jetzt)
    Hintergrundlauf.objects.filter(name="fristen").update(
        zuletzt_begonnen=jetzt - timedelta(days=2), zuletzt_beendet=jetzt - timedelta(days=2)
    )
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 503
    daten = antwort.json()
    assert daten["status"] == "ueberfaellig" and daten["ueberfaellig"] is True


def test_innerhalb_von_drei_takten_ist_nicht_ueberfaellig(client, settings):
    settings.DDOE_WAECHTER_MINUTEN = 10
    jetzt = timezone.now()
    assert hintergrund.ausfuehren(_fristenlauf(), jetzt)
    Hintergrundlauf.objects.filter(name="fristen").update(zuletzt_begonnen=jetzt - timedelta(minutes=25))
    assert client.get(ADRESSE).json()["ueberfaellig"] is False


def test_werfender_antrag_ergibt_fehler_1(client, laufender_antrag, monkeypatch):
    def wirft(self, jetzt=None):
        raise RuntimeError("Antrag kaputt (Test) probe@example.org")

    monkeypatch.setattr(Antrag, "fortschreiben", wirft)
    assert hintergrund.ausfuehren(_fristenlauf())
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 503
    daten = antwort.json()
    assert daten["status"] == "fehler" and daten["fehler"] == 1 and daten["abgebrochen"] is False
    assert "probe" not in antwort.content.decode()

    # Nach einem fehlerfreien Lauf wieder 200
    monkeypatch.undo()
    Hintergrundlauf.objects.filter(name="fristen").update(zuletzt_begonnen=timezone.now() - timedelta(days=1))
    assert hintergrund.ausfuehren(_fristenlauf())
    assert client.get(ADRESSE).status_code == 200


def test_abgebrochener_lauf_meldet_ohne_fehlertext(client, monkeypatch):
    from verfahren.management.commands import verfahren_fortschreiben

    def bricht(jetzt=None):
        raise RuntimeError("geheimer Verbindungstext (Test)")

    monkeypatch.setattr(verfahren_fortschreiben, "alles_fortschreiben", bricht)
    assert hintergrund.ausfuehren(_fristenlauf())
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 503
    daten = antwort.json()
    assert daten["status"] == "fehler" and daten["abgebrochen"] is True
    assert "geheim" not in antwort.content.decode() and "RuntimeError" not in antwort.content.decode()


def test_ohne_zeile_noch_nicht_gelaufen(client):
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 503 and antwort.json()["status"] == "noch_nicht_gelaufen"


def test_altbestand_ohne_fehlerzaehler_im_stand(client, settings):
    """Zeilen von vor 0.113 tragen im Stand keinen Schlüssel „fehler“, oder einen leeren Stand."""
    settings.DDOE_WAECHTER_MINUTEN = 10
    jetzt = timezone.now()
    Hintergrundlauf.objects.create(name="fristen", zuletzt_begonnen=jetzt, zuletzt_beendet=jetzt,
                                   zuletzt_stand={"phasenwechsel": 2})
    assert client.get(ADRESSE).json() | {"zuletzt_begonnen": None, "zuletzt_beendet": None} == {
        "lauf": "fristen", "status": "ok", "ueberfaellig": False, "fehler": 0, "abgebrochen": False,
        "takt_minuten": 10,
        "zuletzt_begonnen": None, "zuletzt_beendet": None,
    }
    Hintergrundlauf.objects.filter(name="fristen").update(zuletzt_stand={"fehler": "kaputt"}, zuletzt_beendet=None)
    antwort = client.get(ADRESSE)
    assert antwort.status_code == 200 and antwort.json()["fehler"] == 0
