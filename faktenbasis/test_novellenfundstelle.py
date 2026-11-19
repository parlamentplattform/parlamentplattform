"""Die ausgewiesene Fundstelle ist an den einzelnen Normstand gebunden."""

from datetime import date

import pytest
from django.urls import reverse

from faktenbasis import importieren as metadaten
from faktenbasis import landesrecht
from faktenbasis.models import Norm
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_landesrecht import NUMMER as LAND_NUMMER
from faktenbasis.test_landesrecht import beispiel as landesbeispiel
from faktenbasis.test_ris import STAND, beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from plattform_core.novellenfundstelle import novellenfundstelle
from verfahren.models import AuditEintrag

FELDER = {"NovellenPublikationsorgan": "BGBl. I Nr.", "NovellenBgblnummer": "70/2024",
          "NovellenBeziehung": "zuletzt geändert durch"}
AUFHEBUNGSFELDER = {**FELDER, "NovellenBeziehung": "aufgehoben durch", "Ausserkrafttretensdatum": "2025-01-01"}
DSG_NUMMER = "10001597"


def test_genannte_novelle_ohne_rueckschluesse_aus_freitext():
    roh = {"Metadaten": {"Technisch": {"ID": "NOR40262691", "Applikation": "BrKons"},
                        "Bundesrecht": {"BrKons": FELDER}}}
    beleg = novellenfundstelle(roh, "NOR40262691", date(2026, 11, 3))
    assert beleg.bezeichnung == "BGBl. I Nr. 70/2024"
    assert beleg.ziel == "https://www.ris.bka.gv.at/eli/bgbl/I/2024/70"
    assert novellenfundstelle(roh, "NOR40139563", date(2026, 11, 3)) is None
    assert novellenfundstelle(roh, "NOR40262691", date(2023, 12, 31)) is None


@pytest.mark.parametrize("feld,wert", [
    ("NovellenPublikationsorgan", "LGBl.Nr."), ("NovellenPublikationsorgan", []),
    ("NovellenBgblnummer", "70/2024?target=http://example.invalid"), ("NovellenBgblnummer", "1/2003"),
    ("NovellenBgblnummer", "70/2024, 71/2024"), ("NovellenBgblnummer", "７０/2024"),
    ("NovellenBeziehung", "berichtigt durch"), ("NovellenBeziehung", None),
])
def test_unbekannte_oder_mehrdeutige_angaben_bleiben_ohne_link(feld, wert):
    roh = {"Metadaten": {"Technisch": {"ID": "NOR40262691", "Applikation": "BrKons"},
                        "Bundesrecht": {"BrKons": {**FELDER, feld: wert}}}}
    assert novellenfundstelle(roh, "NOR40262691", date(2026, 11, 3)) is None


@pytest.mark.parametrize("datum", [None, "", "20240704", "2024-02-30", "2024-07-05"])
def test_aufhebung_braucht_kanonisches_datum_bis_zum_gespeicherten_stichtag(datum):
    roh = {
        "Metadaten": {
            "Technisch": {"ID": "NOR40262691", "Applikation": "BrKons"},
            "Bundesrecht": {"BrKons": {**AUFHEBUNGSFELDER, "Ausserkrafttretensdatum": datum}},
        },
    }
    assert novellenfundstelle(roh, "NOR40262691", date(2024, 7, 4)) is None


def normstaende_anlegen(monkeypatch, beziehung=FELDER):
    daten = beispiel()
    referenzen = daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]
    referenz = referenzen[0] if isinstance(referenzen, list) else referenzen
    meta = referenz["Data"]["Metadaten"]
    meta["Technisch"]["ID"] = "NOR40262691"
    url = "https://ris.bka.gv.at/eli/bgbl/i/1999/165/P0/NOR40262691"
    meta["Allgemein"]["DokumentUrl"] = url
    bund = meta["Bundesrecht"]
    bund.update(Kurztitel="Datenschutzgesetz", Titel="Datenschutzgesetz (synthetischer Prüfstand)", Eli=url)
    felder = bund["BrKons"]
    felder.update(Gesetzesnummer=DSG_NUMMER, Typ="BG")
    monkeypatch.setattr(metadaten, "abrufen", lambda *args, **kwargs: antwort_parsen(daten, DSG_NUMMER))
    alt = metadaten.importieren(DSG_NUMMER, STAND)
    felder.update(beziehung)
    neu = metadaten.importieren(DSG_NUMMER, STAND)
    return Norm.objects.get(importlauf=alt), Norm.objects.get(importlauf=neu)


@pytest.mark.django_db
def test_normseite_zeigt_je_schnappschuss_dessen_novelle_ohne_schreibzugriff(client, monkeypatch, abrufuhr):  # noqa: F811
    alt_norm, neu_norm = normstaende_anlegen(monkeypatch)
    vorher = AuditEintrag.objects.count()
    html_alt = client.get(reverse("faktenbasis:norm", args=[alt_norm.pk])).content.decode()
    html_neu = client.get(reverse("faktenbasis:norm", args=[neu_norm.pk])).content.decode()
    assert 'id="novellenfundstelle"' not in html_alt
    assert 'href="https://www.ris.bka.gv.at/eli/bgbl/I/2024/70"' in html_neu
    assert AuditEintrag.objects.count() == vorher and Norm.objects.count() == 2


def landesnorm_anlegen(monkeypatch):
    daten = landesbeispiel()
    roh = daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]
    meta = roh["Metadaten"]
    meta["Technisch"]["ID"] = "LOO40027105"
    meta["Allgemein"]["DokumentUrl"] = "https://ris.bka.gv.at/eli/lgbl/OB/1990/91/P3/LOO40027105"
    land = meta["Landesrecht"]
    land.update(Kurztitel="Oö. Gemeindeordnung 1990", Titel="Oö. Gemeindeordnung 1990 (synthetischer Prüfstand)")
    land["LrKons"].update({**FELDER, "NovellenPublikationsorgan": "LGBl.Nr.", "NovellenBgblnummer": "62/2026",
                          "ArtikelParagraphAnlage": "§ 3", "Inkrafttretensdatum": "2026-09-01"})
    monkeypatch.setattr(landesrecht, "abrufen", lambda *args, **kwargs: landesrecht.antwort_parsen(
        daten, LAND_NUMMER, "Oberoesterreich",
    ))
    lauf = metadaten.importieren(LAND_NUMMER, STAND, bundesland="Oberoesterreich")
    return Norm.objects.get(importlauf=lauf)


@pytest.mark.django_db
def test_landesfundstelle_verwendet_weder_inkrafttreten_als_eli_datum_noch_fremdes_land(client, monkeypatch, abrufuhr):  # noqa: F811
    norm = landesnorm_anlegen(monkeypatch)
    vorher = AuditEintrag.objects.count()
    antwort = client.get(reverse("faktenbasis:norm", args=[norm.pk]))
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert "<strong>LGBl. Nr. 62/2026</strong> · Oberösterreich" in html
    assert "/eli/lgbl/OB/2026/62/20260901" not in html
    assert antwort.context["novelle"].ziel is None
    for bundesland in ("", "Tirol", "Niederösterreich"):
        assert novellenfundstelle(norm.rohdaten, norm.ris_id, STAND, bundesland=bundesland) is None
    assert AuditEintrag.objects.count() == vorher
