"""S14a (§ 12; FB-M1, M6, M7, M8): die Partner-Seite mit Gemeinsamer Vision, Schaubild, Schnittstelle,
Einstieg in zwei Spuren und Übertragungspaket; das Paket als ZIP; der Satzungs-Baukasten bleibt aktuell."""

import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

WURZEL = Path(__file__).resolve().parent.parent
PAKET = (
    "README-PAKET.md", "GEMEINSAME_VISION.md", "EINSTIEG.md", "EINRICHTUNG.md", "SATZUNG_BAUKASTEN.md",
    "SCHEMA.md", "instanz/docker-compose.yml", "instanz/env.example", "instanz/render.yaml",
    "policies/kategorien-v2.yaml", "policies/grundordnung-v1.yaml", "parameter-erstbestand.json",
)


def test_partner_seite_zeigt_vision_modell_schnittstelle_einstieg_und_paket(client):
    inhalt = client.get(reverse("verfahren:partner")).content.decode()
    for text in (
        "Gemeinsame Vision", "Fassung 0.1", "Ein Kern, viele Instanzen", 'class="schaubild"',
        "/parameter.json", "/kennzahlen.json", "docs/SCHEMA.md", "Bestehende Partei umgestalten", "Neu gründen",
        'href="/partner/paket/"', "at-ddoe", "Labor der Demokratien", "Partner-Konto", "mailto:plattform@ddoe.at",
    ):
        assert text in inhalt, text
    assert inhalt.count("<h2") >= 7
    assert "oninput" not in inhalt and "onclick" not in inhalt
    for datei in PAKET:
        assert f"<code>{datei}</code>" in inhalt, datei


def test_partner_seite_auf_englisch(client):
    inhalt = client.get(reverse("verfahren:partner"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "One core, many instances" in inhalt and "Download the package" in inhalt


def test_uebertragungspaket_als_zip(client):
    antwort = client.get(reverse("verfahren:partner_paket"))
    assert antwort.status_code == 200 and antwort["Content-Type"] == "application/zip"
    assert "parlamentplattform-paket-" in antwort["Content-Disposition"]
    with zipfile.ZipFile(io.BytesIO(antwort.content)) as zf:
        namen = set(zf.namelist())
        for name in PAKET:
            assert name in namen, name
        erstbestand = json.loads(zf.read("parameter-erstbestand.json"))
        assert erstbestand["schema_version"] == "1.0"
        assert all(p["schema_key"] for p in erstbestand["parameter"])
        assert "[PARTEINAME]" in zf.read("SATZUNG_BAUKASTEN.md").decode("utf-8")
        assert "DDOE_SYSTEM_ID" in zf.read("instanz/env.example").decode("utf-8")
        assert "Übertragungspaket" in zf.read("README-PAKET.md").decode("utf-8")


def test_satzung_baukasten_ist_aktuell_und_ohne_eigennamen():
    spec = importlib.util.spec_from_file_location("satzung_baukasten", WURZEL / "tools" / "satzung_baukasten.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    text = modul.erzeugen()
    assert (WURZEL / "docs" / "partner" / "SATZUNG_BAUKASTEN.md").read_text(encoding="utf-8") == text
    rumpf = text.split("## § 1 ")[1]
    assert "Direkte Demokratie Österreich" not in rumpf and "DDÖ" not in rumpf and "Österreich" not in rumpf
    for platzhalter in ("[PARTEINAME]", "[KÜRZEL]", "[LAND]", "[SITZ]", "[REGISTRIERUNGSBEHÖRDE]", "[PARTEIENGESETZ]"):
        assert platzhalter in rumpf, platzhalter
    assert "## § 12 Internationale Zusammenarbeit" in rumpf  # der Kern bleibt
    assert "rechtliche Prüfung im eigenen Land" in rumpf
