"""Quellenidentität, unveränderliches Archiv und öffentliche Nachlese."""

import copy
import hashlib
import json
from datetime import date
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse

from faktenbasis.models import VfghEntscheidungsstand
from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.vfgh_import import importieren
from parameter.models import Parameter
from plattform_core.vfgh_metadaten import entscheidung
from verfahren.models import AuditEintrag

DOKUMENT = "JFT_20251007_25G99999_00"
AKTENZEICHEN = "G99999/2025"
ECLI = "ECLI:AT:VFGH:2025:G99999.2025"
QUELLE = f"https://www.ris.bka.gv.at/Dokument.wxe?Abfrage=Vfgh&Dokumentnummer={DOKUMENT}"
META = {
    "Technisch": {"ID": DOKUMENT, "Applikation": "Vfgh"},
    "Allgemein": {"DokumentUrl": QUELLE.replace("www.", "ogd.")},
    "Judikatur": {
        "Dokumenttyp": "Text", "Entscheidungsdatum": "2025-10-07",
        "Geschaeftszahl": {"item": AKTENZEICHEN},
        "EuropeanCaseLawIdentifier": ECLI, "Normen": {"item": ["DSG §1", "B-VG Art140"]},
    },
}


def antwort(meta=META):
    return {"OgdSearchResult": {"OgdDocumentResults": {"OgdDocumentReference": {"Data": {"Metadaten": meta}}}}}


def original(meta=META):
    return json.dumps(antwort(meta), ensure_ascii=False).encode()


def test_ids_datum_und_wortlaut_des_amtlichen_belegs_auswerten():
    beleg = entscheidung(antwort(), DOKUMENT)
    assert beleg.dokumentnummer == DOKUMENT
    assert beleg.entschieden_am == date(2025, 10, 7)
    assert beleg.ecli == ECLI and beleg.quelle == QUELLE
    assert beleg.geschaeftszahlen == (AKTENZEICHEN,)
    assert beleg.normangaben == ("DSG §1", "B-VG Art140")
    bekannt = copy.deepcopy(META)
    del bekannt["Judikatur"]["Normen"]
    assert entscheidung(antwort(bekannt), DOKUMENT).normangaben == ()


@pytest.mark.parametrize(("bereich", "feld", "wert"), [
    ("Technisch", "ID", "JFT_20251007_25G12345_00"),
    ("Technisch", "Applikation", "Vwgh"),
    ("Allgemein", "DokumentUrl", "https://ris.bka.gv.at.example.test/Dokument.wxe?Abfrage=Vfgh"),
    ("Allgemein", "DokumentUrl", QUELLE + "&Dokumentnummer=JFT_20251007_25G12345_00"),
    ("Judikatur", "Dokumenttyp", "Rechtssatz"),
    ("Judikatur", "Entscheidungsdatum", "20251007"),
    ("Judikatur", "Entscheidungsdatum", "2025-10-08"),
    ("Judikatur", "EuropeanCaseLawIdentifier", "ECLI:AT:VFGH:2024:G99999.2025"),
    ("Judikatur", "Geschaeftszahl", {"item": []}),
    ("Judikatur", "Normen", {"item": ["DSG", {"url": QUELLE}]}),
])
def test_abweichendes_oder_uneindeutiges_material_wird_abgelehnt(bereich, feld, wert):
    meta = copy.deepcopy(META)
    meta[bereich][feld] = wert
    assert entscheidung(antwort(meta), DOKUMENT) is None


def test_mehrere_referenzen_sind_kein_einzelbeleg():
    daten = antwort()
    ergebnis = daten["OgdSearchResult"]["OgdDocumentResults"]
    ergebnis["OgdDocumentReference"] = [ergebnis["OgdDocumentReference"]] * 2
    assert entscheidung(daten, DOKUMENT) is None


@pytest.mark.django_db
def test_cli_archiviert_bytes_einmal_und_bewahrt_frueheren_stand(tmp_path):
    datei = tmp_path / "entscheidung.json"
    daten = original()
    datei.write_bytes(daten)
    hashwert = hashlib.sha256(daten).hexdigest()
    ausgabe = StringIO()
    vorher = AuditEintrag.objects.count()
    for _ in range(2):
        call_command("ris_vfgh_metadaten", dokumentnummer=DOKUMENT, datei=datei, sha256=hashwert, stdout=ausgabe)
    erster = VfghEntscheidungsstand.objects.get()
    assert bytes(erster.original) == daten and erster.original_sha256 == hashwert and hashwert in ausgabe.getvalue()
    neuer = importieren(DOKUMENT, daten + b"\n")
    assert neuer.pk != erster.pk
    assert bytes(VfghEntscheidungsstand.objects.get(pk=erster.pk).original) == daten
    assert AuditEintrag.objects.count() == vorher + 2
    with pytest.raises(ValidationError):
        erster.delete()
    with pytest.raises(CommandError, match="pruefsumme"):
        call_command("ris_vfgh_metadaten", dokumentnummer=DOKUMENT, datei=datei, sha256="0" * 64)


@pytest.mark.parametrize(("daten", "code"), [
    (b"", "antwortgroesse"), (b" " * (HOECHSTBYTES + 1), "antwortgroesse"),
    (b'{"OgdSearchResult": {}, "OgdSearchResult": {}}', "antwortformat"),
    (original(), "vfgh_metadaten"),
], ids=["leer", "zu-gross", "doppelter-schluessel", "falsche-dokumentnummer"])
def test_unvollstaendige_datei_oder_falsche_kennung_erzeugt_keinen_schreibzugriff(daten, code):
    with pytest.raises(RisFehler, match=code):
        importieren("JFT_20251007_25G12121_00", daten)


@pytest.mark.django_db
def test_oeffentliche_nachlese_ist_begrenzt_und_zeigt_normen_als_text(client):
    erster = importieren(DOKUMENT, original())
    neuer = importieren(DOKUMENT, original() + b"\n")
    Parameter.objects.update_or_create(schluessel="faktenbasis-seitengroesse", defaults={"wert": "1"})
    liste = reverse("faktenbasis:vfgh")
    detail = reverse("faktenbasis:vfgh_detail", args=[erster.pk])
    vorher = AuditEintrag.objects.count()
    assert client.get(liste).context["seite"][0].pk == neuer.pk
    assert client.get(liste, {"seite": "2"}).context["seite"][0].pk == erster.pk
    antwort = client.get(detail)
    assert antwort.status_code == 200
    text = antwort.content.decode()
    assert 'class="fakten-hash">DSG §1</li>' in text and erster.original_sha256 in text
    assert QUELLE.replace("&", "&amp;") in text
    assert client.post(liste).status_code == client.post(detail).status_code == 405
    assert AuditEintrag.objects.count() == vorher
