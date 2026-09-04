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
    # Deutsch ausdrücklich anfordern: Ohne Sprachangabe zeigt diese Seite Englisch (FB-M1)
    inhalt = client.get(reverse("verfahren:partner"), headers={"accept-language": "de"}).content.decode()
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
    """Der Baukasten ist eingecheckt und öffentlich; seine Quelle (die Satzung im internen
    Fahrtenbuch-Ordner) ist es nicht — fehlt sie, wird nur das Erzeugnis geprüft."""
    baukasten = (WURZEL / "docs" / "partner" / "SATZUNG_BAUKASTEN.md").read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("satzung_baukasten", WURZEL / "tools" / "satzung_baukasten.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    if modul.QUELLE.exists():
        assert baukasten == modul.erzeugen(), "tools/satzung_baukasten.py neu ausführen"
    text = baukasten
    rumpf = text.split("## § 1 ")[1]
    assert "Direkte Demokratie Österreich" not in rumpf and "DDÖ" not in rumpf and "Österreich" not in rumpf
    for platzhalter in ("[PARTEINAME]", "[KÜRZEL]", "[LAND]", "[SITZ]", "[REGISTRIERUNGSBEHÖRDE]", "[PARTEIENGESETZ]"):
        assert platzhalter in rumpf, platzhalter
    assert "## § 12 Internationale Zusammenarbeit" in rumpf  # der Kern bleibt
    assert "rechtliche Prüfung im eigenen Land" in rumpf


# ── Die Sprache der Welt (FB-M1, FB-M2) ───────────────────────────────────────


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        (None, "International partners"),          # keine Angabe: Englisch ist die sichere Wahl
        ("en", "International partners"),
        ("es", "International partners"),          # Spanisch → Englisch, nicht Deutsch
        ("fr-FR,fr;q=0.9", "International partners"),
        ("ja", "International partners"),
        ("de", "Internationale Partner"),          # Deutschsprachige bleiben bei Deutsch
        ("de-AT,de;q=0.9,en;q=0.8", "Internationale Partner"),
    ],
)
def test_partnerseite_begruesst_die_welt_auf_englisch(client, sprache, erwartet):
    """FB-M1: Die Zielgruppe dieser Seite sitzt außerhalb des deutschen Sprachraums.

    Ohne diese Regel landet jede Sprache, die nicht Deutsch oder Englisch ist, auf der
    deutschen Fassung — ausgerechnet hier."""
    kopf = {"headers": {"accept-language": sprache}} if sprache else {}
    inhalt = client.get(reverse("verfahren:partner"), **kopf).content.decode()
    assert erwartet in inhalt


def test_eigene_sprachwahl_hat_vorrang(client):
    """Wer die Sprache selbst wählt, behält sie — auch auf der Partner-Seite."""
    from django.conf import settings

    client.get(reverse("verfahren:partner"), headers={"accept-language": "es"})
    sitzung = client.session
    sitzung[settings.LANGUAGE_COOKIE_NAME] = "de"
    sitzung.save()
    inhalt = client.get(reverse("verfahren:partner"), headers={"accept-language": "es"}).content.decode()
    assert "Internationale Partner" in inhalt, "die eigene Wahl wird nicht überstimmt"


def test_die_sprachregel_faerbt_nicht_auf_andere_seiten_ab(client):
    """Nur die Partner-Seite schaltet um; das Parlament bleibt bei der Voreinstellung."""
    client.get(reverse("verfahren:partner"), headers={"accept-language": "es"})
    inhalt = client.get(reverse("verfahren:parlament"), headers={"accept-language": "es"}).content.decode()
    assert "Parlament" in inhalt and "International partners" not in inhalt
