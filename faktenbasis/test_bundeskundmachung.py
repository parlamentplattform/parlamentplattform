"""Amtliche, datierte Bundes-Kundmachungen je gespeichertem Normstand."""

import json
from datetime import date

import pytest
from django.urls import reverse

from faktenbasis.kundmachung import zuordnen
from faktenbasis.models import Kundmachungsnachweis
from faktenbasis.ris import RisFehler
from faktenbasis.test_kundmachungsbeleg import rohbytes as landesdatei
from faktenbasis.test_novellenfundstelle import normstaende_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from plattform_core.novellenfundstelle import Fundstelle, bundeskundmachung
from verfahren.models import AuditEintrag

NUMMER = "BGBLA_2024_I_70"
ELI = "https://www.ris.bka.gv.at/eli/bgbl/I/2024/70/20240704"
FUNDSTELLE = Fundstelle("I", "70", "2024")
STAND = date(2026, 11, 3)


def antwort_und_meta():
    meta = {
        "Technisch": {"Applikation": "BgblAuth", "ID": NUMMER},
        "Allgemein": {"DokumentUrl": ELI.replace("www.", "ogd.")},
        "Bundesrecht": {
            "Eli": ELI,
            "BgblAuth": {
                "Bgblnummer": FUNDSTELLE.bezeichnung, "AlteDokumentnummer": NUMMER,
                "Teil": "Teil1", "Ausgabedatum": "2024-07-04",
                "Gesetzgebungsperiode": "XXVII", "AusschussberichtNationalrat": {"item": "2594"},
                "AusschussberichtBundesrat": {"item": "11514"}, "Initiativantrag": {"item": "9000"},
            },
        },
    }
    return {"OgdSearchResult": {"OgdDocumentResults": {"OgdDocumentReference": {"Data": {"Metadaten": meta}}}}}, meta


def rohbytes():
    antwort, _ = antwort_und_meta()
    return json.dumps(antwort).encode()


@pytest.mark.parametrize("teil,teilwert", [("I", "Teil1"), ("II", "Teil2"), ("III", "Teil3")])
def test_bundesbeleg_fuer_jeden_teil(teil, teilwert):
    antwort, meta = antwort_und_meta()
    fundstelle = Fundstelle(teil, "70", "2024")
    nummer = f"BGBLA_2024_{teil}_70"
    eli = ELI.replace("/I/", f"/{teil}/")
    meta["Technisch"]["ID"] = nummer
    meta["Allgemein"]["DokumentUrl"] = eli
    meta["Bundesrecht"]["Eli"] = eli
    meta["Bundesrecht"]["BgblAuth"].update(
        Bgblnummer=fundstelle.bezeichnung, AlteDokumentnummer=nummer, Teil=teilwert,
    )
    beleg = bundeskundmachung(antwort, fundstelle, STAND)
    assert (beleg.dokumentnummer, beleg.datum, beleg.eli) == (nummer, date(2024, 7, 4), eli)
    assert beleg.gesetzgebungsperiode == "XXVII"
    assert beleg.ausschussberichte_nationalrat == ("2594",)
    assert beleg.ausschussberichte_bundesrat == ("11514",)


@pytest.mark.parametrize("gruppe,feld,wert", [
    ("Technisch", "Applikation", "BrKons"),
    ("Technisch", "ID", "BGBLA_2024_I_69"),
    ("Allgemein", "DokumentUrl", ELI + "#A1"),
    ("Bundesrecht", "Eli", ELI.replace("www.", "fremd.")),
    ("Bundesrecht", "Eli", ELI.replace("20240704", "20240703")),
    ("BgblAuth", "Teil", "Teil2"),
    ("BgblAuth", "Bgblnummer", "BGBl. I Nr. 70/2023"),
    ("BgblAuth", "AlteDokumentnummer", "BGBLA_2024_I_99"),
    ("BgblAuth", "Ausgabedatum", "20240704"),
    ("BgblAuth", "Ausgabedatum", "2024-02-31"),
])
def test_widerspruechlicher_bundesbeleg_wird_nicht_zugeordnet(gruppe, feld, wert):
    antwort, meta = antwort_und_meta()
    objekt = meta["Bundesrecht"]["BgblAuth"] if gruppe == "BgblAuth" else meta[gruppe]
    objekt[feld] = wert
    assert bundeskundmachung(antwort, FUNDSTELLE, STAND) is None


def test_berichtsnummern_erhalten_die_reihenfolge_der_quelle():
    antwort, meta = antwort_und_meta()
    blatt = meta["Bundesrecht"]["BgblAuth"]
    blatt["AusschussberichtNationalrat"]["item"] = ["2594", "92", "2594"]
    blatt["AusschussberichtBundesrat"]["item"] = "https://example.org"
    blatt["Gesetzgebungsperiode"] = "XXVII/123"
    beleg = bundeskundmachung(antwort, FUNDSTELLE, STAND)
    assert beleg.ausschussberichte_nationalrat == ("2594", "92")
    assert beleg.ausschussberichte_bundesrat == ()
    assert beleg.gesetzgebungsperiode == ""
    assert bundeskundmachung(antwort, FUNDSTELLE, date(2024, 7, 3)) is None


@pytest.mark.django_db
def test_bundesbeleg_bleibt_bei_der_bestaetigten_fassung(client, monkeypatch, abrufuhr):  # noqa: F811
    andere, norm = normstaende_anlegen(monkeypatch)
    ziel = reverse("faktenbasis:norm", args=[norm.pk])
    assert f'href="{ELI.rsplit("/", 1)[0]}"' in client.get(ziel).content.decode()
    vorher = AuditEintrag.objects.count()
    for norm_id, original in [(andere.pk, rohbytes()), (norm.pk, landesdatei())]:
        with pytest.raises(RisFehler, match="kundmachungsbeleg"):
            zuordnen(norm_id, original)
    assert not Kundmachungsnachweis.objects.exists() and AuditEintrag.objects.count() == vorher
    zuordnen(norm.pk, rohbytes())
    beleg = Kundmachungsnachweis.objects.get(norm=norm)
    assert beleg.parlamentsmaterialien == {
        "periode": "XXVII", "nationalrat": ["2594"], "bundesrat": ["11514"],
    }
    html = client.get(ziel).content.decode()
    assert f'href="{ELI}"' in html and 'href="https://www.parlament.gv.at/' not in html
    assert "<dd>2594</dd>" in html and "<dd>11514</dd>" in html and "<dd>9000</dd>" not in html
    assert ELI not in client.get(reverse("faktenbasis:norm", args=[andere.pk])).content.decode()
    assert AuditEintrag.objects.count() == vorher + 1
