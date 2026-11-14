"""Die ausgewiesene Fundstelle ist an den einzelnen Normstand gebunden."""

from datetime import date

import pytest
from django.urls import reverse

from faktenbasis import importieren as metadaten
from faktenbasis.models import Norm
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import STAND, beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from plattform_core.novellenfundstelle import novellenfundstelle
from verfahren.models import AuditEintrag

FELDER = {"NovellenPublikationsorgan": "BGBl. I Nr.", "NovellenBgblnummer": "70/2024",
          "NovellenBeziehung": "zuletzt geändert durch"}
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


def normstaende_anlegen(monkeypatch):
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
    felder.update(FELDER)
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
