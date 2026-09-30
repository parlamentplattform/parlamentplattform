"""Bildschirmtests des Sitzungsmodus (FB-L5): Live-Seite und Karte „Sitzung“ — Desktop und Handy, hell
und dunkel, mit und ohne JavaScript; der Ticker lädt mit htmx im Registertakt nach, ohne JavaScript lädt
die Seite selbst neu. Mit `DDOE_SICHTPRUEFUNG=1` landen die Bilder unter docs/sichtpruefung/<version>/."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _ruhe(p, js: bool = True) -> None:
    # Die Marke einer laufenden Sitzung pulsiert endlos — sie zählt nicht als Bewegung, die abklingen muss
    if js:
        p.wait_for_function(
            "() => document.getAnimations().every(a => a.playState !== 'running'"
            " || a.effect.getTiming().iterations === Infinity)"
        )
    else:
        p.wait_for_timeout(800)


@pytest.fixture
def sitzung(demo):
    from django.utils import timezone

    from mandatare.models import Aufgabe, Mandat
    from mandatare.sitzung import meldung_abgeben, sitzung_beginnen
    from mitglieder.models import Mitglied
    from parameter.models import Parameter, erstbestand_sicherstellen
    from verfahren.chat import sitzung_beitrag_schreiben

    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="live-takt-sekunden").update(wert="5")
    mandatar = Mitglied.objects.get(username="demo2")
    mandat = Mandat.objects.create(
        mitglied=mandatar, bezeichnung="Gemeinderat", ebene="gemeinde", gebiet=Mitglied.objects.get(username="demo1").gemeinde
    )
    heute = timezone.localtime().replace(hour=23, minute=59)
    aufgabe = Aufgabe.objects.create(mandat=mandat, titel="Sitzung des Gemeinderats", frist=heute, sitzungstag=True)
    s = sitzung_beginnen(
        mandat, aufgabe, stream="https://tv.example.org/gemeinderat",
        punkte=["Voranschlag 2027", "Radweg an der Landesstraße", "Allfälliges"],
    )
    p1, p2, _ = s.punkte.order_by("nummer")
    meldung_abgeben(s, "Die Sitzung ist eröffnet, 23 von 25 Mitgliedern anwesend.")
    alt = meldung_abgeben(s, "Zum Voranschlag stimme ich dafür, wie von den Mitgliedern beschlossen.", p1, "dafuer")
    meldung_abgeben(s, "Abgestimmt: dafür — angenommen mit 19 zu 4.", p1, "dafuer", True, berichtigt=alt)
    meldung_abgeben(s, "Radweg: Ich werde dagegen stimmen, die Finanzierung fehlt.", p2, "dagegen")
    sitzung_beitrag_schreiben(s, Mitglied.objects.get(username="demo3"), "Wie begründen Sie das Nein beim Radweg?")
    return s


def test_live_seite(seite, live_server, sitzung, sichtpruefung):
    from mandatare.sitzung import meldung_abgeben

    url = f"{live_server.url}/mandatare/{sitzung.mandat_id}/live/"
    for name, kwargs in (
        ("live-desktop-hell", {}),
        ("live-desktop-dunkel", {"dunkel": True}),
        ("live-handy-hell", {"viewport": HANDY}),
        ("live-handy-dunkel", {"viewport": HANDY, "dunkel": True}),
    ):
        p = seite(**kwargs)
        p.goto(url)
        _ruhe(p)
        assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
        p.screenshot(path=str(sichtpruefung / f"{name}.png"), full_page=True)

    # Mit JavaScript: der Stand kommt im Takt nach, ohne dass die Seite neu lädt
    p = seite()
    p.goto(url)
    p.evaluate("window.__gleicheSeite = true")
    meldung_abgeben(sitzung, "Punkt 2 wird vertagt.")
    p.wait_for_selector("text=Punkt 2 wird vertagt.", timeout=15000)
    assert p.evaluate("window.__gleicheSeite === true")

    # Ohne JavaScript: lesbar, Neuladen per <noscript>, Schreiben über ?schreiben=1
    p = seite(js=False)
    p.goto(url)
    assert p.locator("text=angenommen mit 19 zu 4").count() == 1
    assert p.locator("#chat-eingabe").is_hidden()
    p.screenshot(path=str(sichtpruefung / "live-desktop-ohne-js.png"), full_page=True)


def test_karte_sitzung_im_bereich(seite, live_server, sitzung, sichtpruefung):
    mandatar = sitzung.mandat.mitglied
    for name, kwargs in (
        ("sitzung-karte-desktop-hell", {}),
        ("sitzung-karte-desktop-dunkel", {"dunkel": True}),
        ("sitzung-karte-handy-hell", {"viewport": HANDY}),
    ):
        p = seite(als=mandatar, **kwargs)
        p.goto(f"{live_server.url}/mandatare/mein/")
        _ruhe(p)
        assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
        p.screenshot(path=str(sichtpruefung / f"{name}.png"), full_page=True)

    # Melden über das Formular — ohne JavaScript genauso wie mit
    p = seite(als=mandatar, js=False)
    p.goto(f"{live_server.url}/mandatare/mein/")
    p.select_option("#sm-punkt", index=3)
    p.fill("#sm-text", "Allfälliges: keine Wortmeldungen.")
    # Die Handlungskarte trägt einen dauernden Schimmer (kein „stabiles“ Element für Playwright) — force
    p.locator("#sitzung button:has-text('Melden')").first.click(force=True)
    p.wait_for_selector(".meldung-zeile p:has-text('Allfälliges: keine Wortmeldungen.')")


def test_uebersicht_und_kachel(seite, live_server, sitzung, sichtpruefung):
    from mitglieder.models import Mitglied

    p = seite()
    p.goto(f"{live_server.url}/live/")
    _ruhe(p)
    p.screenshot(path=str(sichtpruefung / "live-uebersicht-desktop-hell.png"), full_page=True)
    p = seite(als=Mitglied.objects.get(username="demo1"))
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    kachel = p.locator("#feld-region .kachel.live")
    assert kachel.count() == 1
    p.locator("#feld-region").screenshot(path=str(sichtpruefung / "region-kachel-live.png"))
