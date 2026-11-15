"""Geprüfte Zuordnung, Originalbytes und unveränderte alte Normdaten."""

import json
from datetime import date
from hashlib import sha256
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse

from faktenbasis.kundmachung import zuordnen
from faktenbasis.models import Kundmachungsnachweis, Norm
from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.test_novellenfundstelle import landesnorm_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from plattform_core.novellenfundstelle import VERSION, Fundstelle, landeskundmachung
from verfahren.models import AuditEintrag

NUMMER = "LGBLA_OB_20260831_62"
ELI = "https://www.ris.bka.gv.at/eli/lgbl/OB/2026/62/20260831"
FUNDSTELLE = Fundstelle("", "62", "2026", "Oberösterreich")
NORMSTAND = date(2026, 11, 3)


def antwort_und_meta():
    meta = {
        "Technisch": {"Applikation": "LgblAuth", "ID": NUMMER},
        "Allgemein": {"DokumentUrl": ELI.replace("www.", "ogd.")},
        "Landesrecht": {
            "Bundesland": "Oberösterreich", "Kundmachungsdatum": "2026-08-31",
            "LgblAuth": {"Lgblnummer": "LGBl. Nr. 62/2026", "EuropeanLegislationIdentifier": ELI},
        },
    }
    return {"OgdSearchResult": {"OgdDocumentResults": {"OgdDocumentReference": {"Data": {"Metadaten": meta}}}}}, meta


def rohbytes():
    antwort, _ = antwort_und_meta()
    return json.dumps(antwort, ensure_ascii=False).encode("utf-8")


def test_kundmachung_stimmt_mit_oberosterreichischer_fundstelle_ueberein():
    antwort, _ = antwort_und_meta()
    beleg = landeskundmachung(antwort, FUNDSTELLE, NORMSTAND)
    assert (beleg.dokumentnummer, beleg.datum, beleg.eli) == (NUMMER, date(2026, 8, 31), ELI)
    ergebnis = antwort["OgdSearchResult"]["OgdDocumentResults"]
    ergebnis["OgdDocumentReference"] = [ergebnis["OgdDocumentReference"]]
    assert landeskundmachung(antwort, FUNDSTELLE, NORMSTAND) == beleg
    ergebnis["OgdDocumentReference"] *= 2
    assert landeskundmachung(antwort, FUNDSTELLE, NORMSTAND) is None


@pytest.mark.parametrize("pfad,wert", [
    (("Technisch", "Applikation"), "LrKons"),
    (("Technisch", "ID"), "LGBLA_OB_20260901_62"),
    (("Landesrecht", "Bundesland"), "Tirol"),
    (("Landesrecht", "Kundmachungsdatum"), "20260901"),
    (("Landesrecht", "Kundmachungsdatum"), "2026-02-31"),
    (("Landesrecht", "Kundmachungsdatum"), None),
    (("Landesrecht", "Kundmachungsdatum"), "2025-08-31"),
    (("Landesrecht", "LgblAuth", "Lgblnummer"), "LGBl. Nr. 63/2026"),
    (("Landesrecht", "LgblAuth", "EuropeanLegislationIdentifier"), ELI + "#a"),
    (("Landesrecht", "LgblAuth", "EuropeanLegislationIdentifier"), ELI.replace("www.ris.", "fremd.")),
    (("Allgemein", "DokumentUrl"), "https://ogd.ris.bka.gv.at/eli/lgbl/OB/2026/62/20260901"),
])
def test_widerspruch_in_der_quelle_verhindert_ein_direktes_ziel(pfad, wert):
    antwort, objekt = antwort_und_meta()
    for schluessel in pfad[:-1]:
        objekt = objekt[schluessel]
    objekt[pfad[-1]] = wert
    assert landeskundmachung(antwort, FUNDSTELLE, NORMSTAND) is None


def test_frueher_stichtag_und_falsche_fundstelle_erhalten_keinen_beleg():
    antwort, _ = antwort_und_meta()
    assert landeskundmachung(antwort, FUNDSTELLE, date(2026, 8, 30)) is None
    assert landeskundmachung(antwort, Fundstelle("", "62", "2026", "Tirol"), NORMSTAND) is None
    assert landeskundmachung(None, FUNDSTELLE, NORMSTAND) is None
    assert landeskundmachung({"OgdSearchResult": False}, FUNDSTELLE, NORMSTAND) is None


@pytest.mark.django_db
def test_cli_archiviert_einmal_und_der_normstand_erhaelt_den_exakten_link(client, monkeypatch, abrufuhr, tmp_path):  # noqa: F811
    norm = landesnorm_anlegen(monkeypatch)
    vorher = Norm.objects.filter(pk=norm.pk).values().get()
    ziel = reverse("faktenbasis:norm", args=[norm.pk])
    assert ELI not in client.get(ziel).content.decode()
    original = rohbytes()
    quelle = tmp_path / "ris-einzelfund.json"
    quelle.write_bytes(original)
    pruefsumme = sha256(original).hexdigest()
    audit = AuditEintrag.objects.count()
    stdout = StringIO()
    for _ in range(2):
        call_command("ris_kundmachungsbeleg", norm=norm.pk, datei=quelle, sha256=pruefsumme, stdout=stdout)
    beleg = Kundmachungsnachweis.objects.get(norm=norm)
    assert bytes(beleg.original) == original and beleg.original_sha256 == pruefsumme
    assert beleg.parser_fassung == VERSION and beleg.kundgemacht_am == date(2026, 8, 31)
    html = client.get(ziel).content.decode()
    assert f'href="{ELI}"' in html and pruefsumme in html and NUMMER in html
    assert "/62/20260901" not in html and AuditEintrag.objects.count() == audit + 1
    assert Norm.objects.filter(pk=norm.pk).values().get() == vorher
    getrennte_fassung = {key: wert for key, wert in vorher.items() if key != "id"}
    getrennte_fassung["inhalt_hash"] = "1" * 64
    andere = Norm.objects.create(**getrennte_fassung)
    assert ELI not in client.get(reverse("faktenbasis:norm", args=[andere.pk])).content.decode()
    with pytest.raises(ValidationError):
        Kundmachungsnachweis.objects.filter(pk=beleg.pk).update(eli="https://example.org")
    assert pruefsumme in stdout.getvalue()


@pytest.mark.django_db
def test_import_weist_andere_datei_ohne_ueberschreiben_ab(monkeypatch, abrufuhr):  # noqa: F811
    norm = landesnorm_anlegen(monkeypatch)
    original = rohbytes()
    audit = AuditEintrag.objects.count()
    for daten, pruefsumme, code in (
        (b"", None, "antwortgroesse"),
        (b"x" * (HOECHSTBYTES + 1), None, "antwortgroesse"),
        (original, "a" * 64, "pruefsumme"),
        (b"{", None, "antwortformat"),
        (b'{"OgdSearchResult": {}, "OgdSearchResult": {}}', None, "antwortformat"),
        (original.replace(b"62/2026", b"63/2026"), None, "kundmachungsbeleg"),
    ):
        with pytest.raises(RisFehler) as fehler:
            zuordnen(norm.pk, daten, erwartete_pruefsumme=pruefsumme)
        assert fehler.value.code == code
        assert not Kundmachungsnachweis.objects.exists() and AuditEintrag.objects.count() == audit
    beleg = zuordnen(norm.pk, original)
    with pytest.raises(RisFehler, match="bereits_belegt"):
        zuordnen(norm.pk, original + b" ")
    assert bytes(Kundmachungsnachweis.objects.get(pk=beleg.pk).original) == original
    with pytest.raises(RisFehler, match="normstand"):
        zuordnen(norm.pk + 1, original)


def test_cli_liest_keine_fehlende_datei(tmp_path):
    with pytest.raises(CommandError, match="ließ sich nicht lesen"):
        call_command("ris_kundmachungsbeleg", norm=1, datei=tmp_path / "fehlt.json")
