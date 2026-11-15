"""Amtliche, datierte Bundes-Kundmachungen je gespeichertem Normstand."""

import json
from datetime import date

import pytest
from django.urls import reverse

from faktenbasis.kundmachung import zuordnen
from faktenbasis.models import Kundmachungsnachweis, Norm
from faktenbasis.ris import RisFehler
from faktenbasis.test_kundmachungsbeleg import rohbytes as landesdatei
from faktenbasis.test_novellenfundstelle import AUFHEBUNGSFELDER, normstaende_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from parameter.models import Parameter
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
    ("BgblAuth", "AlteDokumentnummer", "COO_2026_100_2_263307/99"),
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


def test_alte_coo_aktenkennung_bleibt_von_der_amtlichen_kundmachungskennung_getrennt():
    antwort, meta = antwort_und_meta()
    meta["Bundesrecht"]["BgblAuth"]["AlteDokumentnummer"] = "COO_2026_100_2_263307"
    beleg = bundeskundmachung(antwort, FUNDSTELLE, STAND)
    assert (beleg.dokumentnummer, beleg.eli) == (NUMMER, ELI)
    meta["Technisch"]["ID"] = "BGBLA_2024_I_99"
    assert bundeskundmachung(antwort, FUNDSTELLE, STAND) is None


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


@pytest.mark.django_db
def test_ausdrueckliche_aufhebung_mit_eigenem_wortlaut_und_datierter_quelle(client, monkeypatch, abrufuhr):  # noqa: F811
    alt, norm = normstaende_anlegen(monkeypatch, AUFHEBUNGSFELDER)
    ziel = reverse("faktenbasis:norm", args=[norm.pk])
    antwort = client.get(ziel)
    assert antwort.context["novelle"].ausserkraft_am == date(2025, 1, 1)
    assert antwort.context["novelle"].ziel == ELI.rsplit("/", maxsplit=1)[0]
    html = antwort.content.decode()
    assert "Aufhebungsfundstelle laut RIS-Metadaten" in html and 'datetime="2025-01-01"' in html
    assert "nennen diese Kundmachung als letzte Änderung" not in html
    assert "Aufhebungsfundstelle laut RIS-Metadaten" not in client.get(
        reverse("faktenbasis:norm", args=[alt.pk])
    ).content.decode()

    beleg = zuordnen(norm.pk, rohbytes())
    assert beleg.kundgemacht_am == date(2024, 7, 4) and beleg.parser_fassung == 5
    assert f'href="{ELI}"' in client.get(ziel).content.decode()
    assert zuordnen(norm.pk, rohbytes()).pk == beleg.pk
    assert AuditEintrag.objects.filter(ereignis__typ="ris_kundmachungsbeleg").count() == 1


@pytest.mark.django_db
def test_rueckverweis_gruppiert_nur_belegte_staende_mit_derselben_kennung_und_demselben_datum(
    client, monkeypatch, abrufuhr,  # noqa: F811
):
    alt, norm = normstaende_anlegen(monkeypatch)
    basis = zuordnen(norm.pk, rohbytes())
    daten = Norm.objects.filter(pk=norm.pk).values().get()
    daten.pop("id")
    neuer = Norm.objects.create(**(daten | {"stand": date(2026, 11, 4)}))
    zweiter = zuordnen(neuer.pk, rohbytes() + b"\n")
    ohne = Norm.objects.create(**(daten | {"stand": date(2026, 11, 5)}))
    fremder_tag = Norm.objects.create(**(daten | {"stand": date(2026, 11, 6)}))
    zuordnen(fremder_tag.pk, rohbytes().replace(b"2024-07-04", b"2024-07-03").replace(b"20240704", b"20240703"))

    ziel = reverse("faktenbasis:kundmachung", args=[basis.pk])
    assert ziel in client.get(reverse("faktenbasis:norm", args=[norm.pk])).content.decode()
    assert ziel not in client.get(reverse("faktenbasis:norm", args=[ohne.pk])).content.decode()
    vorher = AuditEintrag.objects.count()
    antwort = client.get(ziel)
    assert antwort.status_code == 200
    assert [e["pk"] for e in antwort.context["seite"]] == [neuer.pk, norm.pk]
    html = antwort.content.decode()
    assert zweiter.original_sha256 in html and basis.original_sha256 in html
    assert f'href="{ELI}"' in html
    for nicht_belegt in (alt, ohne, fremder_tag):
        assert reverse("faktenbasis:norm", args=[nicht_belegt.pk]) not in html

    Parameter.objects.update_or_create(schluessel="faktenbasis-seitengroesse", defaults={"wert": "1"})
    assert list(client.get(ziel).context["seite"])[0]["pk"] == neuer.pk
    assert list(client.get(ziel, {"seite": "2"}).context["seite"])[0]["pk"] == norm.pk
    assert client.post(ziel).status_code == 405
    assert client.get(reverse("faktenbasis:kundmachung", args=[999_999])).status_code == 404
    assert AuditEintrag.objects.count() == vorher
