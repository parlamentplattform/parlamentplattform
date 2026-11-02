"""Import, Erhalt alter Quellenstände und Rechenschaft; niemals ein echter API-Aufruf."""

import copy
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from faktenbasis import importieren as modul
from faktenbasis.importieren import importieren
from faktenbasis.models import Norm, RisImport
from faktenbasis.ris import RisFehler, antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from parameter.models import Parameter
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


@pytest.fixture
def antwort(monkeypatch):
    daten = beispiel()
    monkeypatch.setattr(modul, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    return daten


def test_wiederholung_dupliziert_keinen_inhalt_und_schreibt_herkunft_und_audit(antwort):
    erster = importieren(NUMMER, STAND)
    norm = Norm.objects.get()
    assert erster.neu == erster.gelesen == 1 and norm.importlauf_id == erster.pk
    assert norm.rohdaten["Metadaten"]["Technisch"]["ID"] == norm.ris_id
    zweiter = importieren(NUMMER, STAND)
    assert zweiter.neu == 0 and zweiter.gelesen == 1
    assert Norm.objects.count() == 1 and RisImport.objects.count() == 2
    norm.refresh_from_db()
    assert norm.importlauf_id == erster.pk
    eintrag = AuditEintrag.objects.last().ereignis
    assert eintrag["typ"] == "ris_import" and eintrag["import"] == zweiter.pk
    assert "mitglied" not in eintrag


def test_geaenderte_metadaten_erzeugen_einen_neuen_schnappschuss(antwort):
    importieren(NUMMER, STAND)
    erster = Norm.objects.get()
    alt = copy.deepcopy(erster.rohdaten)
    antwort["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Bundesrecht"]["Titel"] += " Zusatz"
    lauf = importieren(NUMMER, STAND)
    assert lauf.neu == 1 and Norm.objects.count() == 2
    erster.refresh_from_db()
    assert erster.rohdaten == alt
    assert Norm.objects.exclude(pk=erster.pk).get().inhalt_hash != erster.inhalt_hash
    with pytest.raises(ValidationError):
        erster.save()
    with pytest.raises(ValidationError):
        erster.delete()
    with pytest.raises(ValidationError):
        Norm.objects.filter(pk=erster.pk).update(titel="Überschrieben")
    with pytest.raises(ValidationError):
        Norm.objects.filter(pk=erster.pk).delete()


def test_abruf_abbruch_wird_sichtbar_ohne_alte_fakten_zu_veraendern(client, antwort, monkeypatch):
    importieren(NUMMER, STAND)
    def kaputt(*args):
        raise RisFehler("abruf")
    monkeypatch.setattr(modul, "abrufen", kaputt)
    with pytest.raises(RisFehler):
        importieren(NUMMER, STAND)
    assert Norm.objects.count() == 1
    assert not RisImport.objects.first().erfolgreich
    seite = client.get(reverse("faktenbasis:index")).content.decode()
    assert "Der letzte Abruf ist fehlgeschlagen" in seite


def test_schreibfehler_rollt_die_gesamte_uebernahme_zurueck(antwort, monkeypatch):
    ergebnis = antwort["OgdSearchResult"]["OgdDocumentResults"]
    erster = ergebnis["OgdDocumentReference"]
    zweiter = copy.deepcopy(erster)
    # Absichtlich künstliche zweite Kennung für den Transaktions-Test.
    zweiter["Data"]["Metadaten"]["Technisch"]["ID"] = "NOR00000001"
    zweiter["Data"]["Metadaten"]["Allgemein"]["DokumentUrl"] = "https://ris.bka.gv.at/test/NOR00000001"
    ergebnis["OgdDocumentReference"] = [erster, zweiter]
    ergebnis["Hits"]["#text"] = "2"
    original = Norm.save
    aufrufe = []
    def kaputt(self, *args, **kwargs):
        aufrufe.append(self.ris_id)
        if len(aufrufe) == 2:
            raise RuntimeError("Test: Datenbank nicht beschreibbar")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Norm, "save", kaputt)
    with pytest.raises(RuntimeError):
        importieren(NUMMER, STAND)
    assert not Norm.objects.exists() and not RisImport.objects.exists() and not AuditEintrag.objects.exists()
    assert len(aufrufe) == 2


def test_cli_erlaubt_nur_exakte_nummer_und_stichtag(antwort):
    ausgabe = StringIO()
    call_command("ris_import", gesetzesnummer=NUMMER, stand=STAND.isoformat(), stdout=ausgabe)
    assert "1 neu" in ausgabe.getvalue() and "Nur Metadaten" in ausgabe.getvalue()
    for nummer, stand in [("x", STAND.isoformat()), (NUMMER, "20261102"), (NUMMER, "2026-02-30")]:
        with pytest.raises(CommandError):
            call_command("ris_import", gesetzesnummer=nummer, stand=stand, stdout=ausgabe)
    assert Norm.objects.count() == 1


def test_oeffentlich_lesen_aber_kein_schreibzugang_und_keine_falsche_verifikation(client, antwort):
    leer = client.get(reverse("faktenbasis:index")).content.decode()
    assert "Noch keine amtlichen Metadaten importiert" in leer
    importieren(NUMMER, STAND)
    norm = Norm.objects.get()
    url = reverse("faktenbasis:norm", args=[norm.pk])
    detail = client.get(url).content.decode()
    assert norm.inhalt_hash in detail and norm.ris_id in detail and norm.quelle in detail
    assert "Metadaten, kein vollständiger Gesetzestext" in detail
    assert "ungeprüfter Modellvorschlag" in detail
    assert client.post(url, {"titel": "Nicht amtlich"}).status_code == 405
    assert client.post(reverse("faktenbasis:index"), {}).status_code == 405
    assert client.get(reverse("faktenbasis:norm", args=[norm.pk + 100])).status_code == 404
    download = client.get(reverse("faktenbasis:importantwort", args=[norm.importlauf_id]))
    assert download.json() == norm.importlauf.antwort
    from faktenbasis.ris import _hash
    assert _hash(download.json()) == norm.importlauf.antwort_hash
    assert client.post(reverse("faktenbasis:importantwort", args=[norm.importlauf_id])).status_code == 405


def test_seitengroesse_aus_register_und_englische_nachlese(client, antwort):
    importieren(NUMMER, STAND)
    antwort["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Bundesrecht"]["Titel"] += " Neu"
    importieren(NUMMER, STAND)
    Parameter.objects.create(schluessel="faktenbasis-seitengroesse", wert="1", beschreibung="Test", quelle="Test")
    seite = client.get(reverse("faktenbasis:index"), HTTP_ACCEPT_LANGUAGE="en")
    assert seite.context["seite"].paginator.count == 2
    assert len(seite.context["seite"]) == 1
    assert "Source data" in seite.content.decode()
    assert "1 document" in seite.content.decode() and "2 snapshots" in seite.content.decode()
