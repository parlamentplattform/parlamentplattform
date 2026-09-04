"""Bildschirmtests der Partner-Seite (S14a; FB-M1, M6, M7): Schaubild und Abschnitte stehen,
das Übertragungspaket lädt herunter, die Schnittstellen-Adressen antworten, am Handy bricht
nichts aus dem Rahmen."""

from __future__ import annotations

import io
import zipfile

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_partner_seite_zeigt_vision_schaubild_und_einstieg(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    ueberschriften = [h.strip() for h in p.locator("main h2").all_inner_texts()]
    assert "Gemeinsame Vision" in " ".join(ueberschriften)
    assert "Ein Kern, viele Instanzen" in " ".join(ueberschriften)
    assert "So steigt ihr ein" in " ".join(ueberschriften)
    schaubild = p.locator("svg.schaubild")
    assert schaubild.is_visible()
    kasten = schaubild.bounding_box()
    seitenbreite = p.locator("main").bounding_box()["width"]
    assert kasten["width"] <= seitenbreite + 1, "das Schaubild bleibt im Textbereich"
    assert p.locator("svg.schaubild .kasten").count() == 4  # Kern und drei Landesinstanzen
    assert p.locator(".spuren .spur-karte").count() == 2  # umgestalten oder neu gründen
    assert p.locator("table.schnittstelle tbody tr").count() >= 5


def test_uebertragungspaket_laedt_herunter(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    with p.expect_download() as ereignis:
        p.locator('a[href="/partner/paket/"]').first.click()
    datei = ereignis.value
    assert datei.suggested_filename.startswith("parlamentplattform-paket-")
    with zipfile.ZipFile(io.BytesIO(open(datei.path(), "rb").read())) as zf:
        assert "SATZUNG_BAUKASTEN.md" in zf.namelist()
        assert "instanz/docker-compose.yml" in zf.namelist()


def test_schnittstellen_adressen_antworten(seite, live_server, demo):
    p = seite()
    for pfad in ("/parameter.json", "/kennzahlen.json", "/umsetzung.json"):
        antwort = p.request.get(f"{live_server.url}{pfad}")
        assert antwort.ok, pfad
        assert antwort.headers.get("access-control-allow-origin") == "*" or pfad == "/umsetzung.json"
        daten = antwort.json()
        if pfad != "/umsetzung.json":
            assert daten["schema_version"] == "1.0" and daten["system_id"] == "at-ddoe"


def test_partner_seite_am_handy(seite, live_server, demo):
    p = seite(viewport=HANDY)
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    breite = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert breite[0] <= breite[1] + 1, "die Seite scrollt nicht waagrecht"
    assert p.locator("svg.schaubild").is_visible()


def test_die_welt_sieht_die_partnerseite_auf_englisch(seite, live_server, demo):
    """FB-M1: Wer nicht ausdrücklich Deutsch möchte, wird auf Englisch begrüßt — auch bei
    Spanisch oder Japanisch. Vorher fiel jede unbekannte Sprache auf Deutsch zurück."""
    for sprache in ("es-ES", "fr-FR", "ja-JP", "en-US"):
        p = seite(sprache=sprache)
        p.goto(f"{live_server.url}/partner/")
        _ruhe(p)
        assert "International partners" in p.locator("h1").inner_text(), sprache
        assert p.locator("html").get_attribute("lang") == "en", sprache

    p = seite(sprache="de-AT")
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    assert "Internationale Partner" in p.locator("h1").inner_text(), "Deutschsprachige bleiben bei Deutsch"
