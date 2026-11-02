"""Beide neuen Angaben funktionieren einschließlich Registrierung ohne JavaScript."""

import time

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse

from mitglieder.botschutz import SITZUNGSSCHLUESSEL
from mitglieder.models import Mitglied, Wohnsitzart

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("art,kennung,viewport", [
    (Wohnsitzart.OHNE_FESTEN_WOHNSITZ, "ohne-festen-wohnsitz", {"width": 1440, "height": 1000}),
    (Wohnsitzart.AUSLAND, "wohnsitz-im-ausland", {"width": 390, "height": 844}),
])
def test_registrierung_ohne_ort_auch_ohne_javascript(seite, live_server, sichtpruefung, art, kennung, viewport):
    p = seite(js=False, viewport=viewport, reduziert=True)
    p.goto(live_server.url + reverse("mitglieder:registrieren"))
    p.get_by_label("Vorname", exact=True).fill("Eva")
    p.get_by_label("Nachname", exact=True).fill("Muster")
    p.get_by_label("E-Mail-Adresse", exact=True).fill("wohnsitz@example.org")
    p.get_by_label("Geburtsjahr", exact=True).fill("1990")
    p.get_by_label("Wohnsitz", exact=True).select_option(art)
    assert p.get_by_label("Wohnsitz-Gemeinde", exact=True).get_attribute("required") is None
    p.screenshot(path=str(sichtpruefung / f"registrierung-{kennung}-ohne-js.png"), full_page=True)
    p.locator('[name="grundsaetze"]').focus()
    p.locator('[name="grundsaetze"]').press("Space")
    assert p.locator('[name="grundsaetze"]').is_checked()
    # Dieselbe Menschlichkeitsprüfung wie im echten Browser, mit zurückgesetzter Mindestwartezeit.
    cookie = next(c["value"] for c in p.context.cookies() if c["name"] == "sessionid")
    sitzung = SessionStore(session_key=cookie)
    aufgaben = sitzung[SITZUNGSSCHLUESSEL]
    kennung_aufgabe = p.locator('[name="pruefung"]').input_value()
    aufgabe = aufgaben[kennung_aufgabe]
    aufgabe["t"] = time.time() - 10
    sitzung[SITZUNGSSCHLUESSEL] = aufgaben
    sitzung.save()
    p.locator('[name="rechenfrage"]').fill(str(aufgabe["a"] + aufgabe["b"]))
    knopf = p.get_by_role("button", name="Beitritt beantragen", exact=True)
    knopf.focus()
    knopf.press("Enter")
    assert p.locator(".fehlerliste").count() == 0
    person = Mitglied.objects.get(email="wohnsitz@example.org")
    assert person.wohnsitz_art == art and person.wohnsitz_id is None
    assert not person.is_active
