"""Neue Datenbankstände ausdrücklich als Bund/Land festhalten, keine Gebietsinferenz."""

import copy

import pytest

from faktenbasis import importieren as metadaten
from faktenbasis import landesrecht, volltext
from faktenbasis.auswahl import erfassen
from faktenbasis.kontext import QuellenkontextFehler, festhalten, pruefen
from faktenbasis.models import Norm, RisImport
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_landesrecht import NUMMER as LANDNUMMER
from faktenbasis.test_landesrecht import STAND
from faktenbasis.test_landesrecht import beispiel as landbeispiel
from faktenbasis.test_landesxml import landnorm, textquelle  # noqa: F401
from faktenbasis.test_ris import NUMMER, beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.kontext import festhalten as text_festhalten
from plattform_core.quellenumfang import als_dict
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def test_land_originaltext_traegt_exakte_herkunft_im_neuen_quellenrahmen(landnorm, textquelle):  # noqa: F811
    original = volltext.importieren(landnorm).inhalt
    rahmen = festhalten([landnorm.pk], hoechstzahl=3, textzeichen=30, text_sha256="a"*64)
    q, = rahmen["quellen"]
    assert rahmen["version"] == 2 and rahmen["umfang"] == als_dict()
    assert q["ebene"] == "Land" and q["bundesland"] == "Oberösterreich"
    assert q["dokumenttext"]["id"] == original.pk and q["dokumenttext"]["auszug"] == original.text[:30]
    assert "/Landesnormen/" in q["dokumenttext"]["quelle"]
    assert pruefen(rahmen)["quellen"] == rahmen["quellen"]


def test_zusaetzliche_pythoneigenschaften_ersetzen_keine_erhaltenen_daten(landnorm):  # noqa: F811
    landnorm.bundesland = "Wien"
    rahmen = festhalten([landnorm.pk], hoechstzahl=3, textzeichen=30)
    assert rahmen["quellen"][0]["bundesland"] == "Oberösterreich"


def test_urspruengliche_landherkunft_muss_mit_neuem_feld_uebereinstimmen():
    d = landbeispiel()
    quelle = landesrecht.antwort_parsen(d, LANDNUMMER, "Oberoesterreich").normen[0]
    lauf = RisImport.objects.create(ebene="Land", bundesland="Wien", gesetzesnummer=LANDNUMMER,
        stand=STAND, erfolgreich=True, antwort=d)
    n = Norm.objects.create(ebene="Land", bundesland="Wien", ris_id=quelle.ris_id, gesetzesnummer=LANDNUMMER,
        kurztitel=quelle.kurztitel, titel=quelle.titel, stand=STAND, quelle=quelle.quelle,
        rohdaten=quelle.rohdaten, inhalt_hash=quelle.inhalt_hash, importlauf=lauf)
    with pytest.raises(QuellenkontextFehler, match="quellenherkunft"):
        festhalten([n.pk], hoechstzahl=3, textzeichen=30)


def test_neutraler_gemeinsamer_bestand_ohne_erfundene_gebietspruefung(monkeypatch, ordnung):  # noqa: F811
    bund, land = beispiel(), landbeispiel()
    bund["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Bundesrecht"]["Kurztitel"] = "Synthetischer Vertragsbeleg"
    land["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Landesrecht"]["Kurztitel"] = "Synthetischer Vertragsbeleg"
    monkeypatch.setattr(metadaten, "abrufen", lambda *args: antwort_parsen(bund, NUMMER))
    monkeypatch.setattr(landesrecht, "abrufen", lambda nummer, stand, name: landesrecht.antwort_parsen(land, nummer, name))
    metadaten.importieren(NUMMER, STAND)
    metadaten.importieren(LANDNUMMER, STAND, bundesland="Oberoesterreich")
    a = antrag_einbringen(mitglied_anlegen("quellenscope"), **{**ANTRAG, "titel": "Synthetischer Vertragsbeleg"}, ordnung=ordnung)
    a.gebiet = "Freitext, keine verifizierte Landeskennung"
    a.save(update_fields=["gebiet"])
    rahmen = erfassen(text_festhalten(a))
    assert rahmen["version"] == 2 and rahmen["umfang"] == als_dict()
    assert {q["ebene"] for q in rahmen["quellen"]} == {"Bund", "Land"}
    assert [q["ris_id"] for q in rahmen["quellen"]] == sorted(q["ris_id"] for q in rahmen["quellen"])
    assert rahmen["auswahl"]["bestand_gesamt"] == 2
    unveraendert = copy.deepcopy(rahmen)
    assert pruefen(rahmen)["umfang"] == als_dict() and rahmen == unveraendert


@pytest.mark.parametrize("fassung", [True, 0, 3, "2"])
def test_unbekannte_schreibfassung_darf_keinen_standard_still_ersetzen(fassung, django_assert_num_queries):
    with django_assert_num_queries(0), pytest.raises(QuellenkontextFehler):
        festhalten([], hoechstzahl=3, textzeichen=30, fassung=fassung)
