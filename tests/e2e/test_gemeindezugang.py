"""Der echte Gemeindeweg bleibt zugänglich, ohne Partei-Rechte auszulösen."""

import re
import time

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from mitglieder.botschutz import SITZUNGSSCHLUESSEL
from mitglieder.models import Gemeindezugang, Mitglied

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("handy,js,sprache", [
    (False, True, "de-AT"), (True, False, "de-AT"),
    (False, False, "en-GB"), (True, True, "en-GB"),
])
def test_gemeindeanmeldung_bis_zur_bestaetigung(seite, live_server, sichtpruefung, handy, js, sprache):
    call_command("gemeinden_laden", verbosity=0)
    p = seite(js=js, dunkel=handy, reduziert=True, sprache=sprache,
              viewport={"width": 390, "height": 844} if handy else {"width": 1440, "height": 1000})
    p.goto(live_server.url + reverse("gemeinde:anmelden"))
    englisch = sprache.startswith("en")
    assert p.locator("h1").inner_text() == ("Create a municipal account" if englisch else "Gemeindekonto anlegen")
    p.locator('[name="email"]').fill("einwohner-browser@example.org")
    p.locator('[name="anzeigename"]').fill("Einwohnerin")
    p.locator('[name="geburtsdatum"]').fill("1990-11-01")
    p.locator('[name="gemeinde"]').fill("St. Marienkirchen an der Polsenz (Eferding)")
    for name in ("meldung", "datenschutz"):
        p.locator(f'[name="{name}"]').focus()
        p.locator(f'[name="{name}"]').press("Space")
        assert p.locator(f'[name="{name}"]').is_checked()
    cookie = next(c["value"] for c in p.context.cookies() if c["name"] == "sessionid")
    sitzung = SessionStore(session_key=cookie)
    aufgaben = sitzung[SITZUNGSSCHLUESSEL]
    kennung = p.locator('[name="pruefung"]').input_value()
    aufgabe = aufgaben[kennung]
    aufgabe["t"] = time.time() - 10
    sitzung[SITZUNGSSCHLUESSEL] = aufgaben
    sitzung.save()
    p.locator('[name="rechenfrage"]').fill(str(aufgabe["a"] + aufgabe["b"]))
    bildname = f"gemeindekonto-{'handy' if handy else 'desktop'}-{'js' if js else 'ohne-js'}-{'en' if englisch else 'de'}"
    p.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    p.screenshot(path=str(sichtpruefung / f"{bildname}-anmeldung.png"), full_page=True)
    knopf = p.locator('main form button[type="submit"]')
    # Tastatur und echte native Übermittlung, auch ohne JavaScript.
    with p.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/gemeinde/anmelden/")) as post:
        knopf.focus()
        knopf.press("Enter")
    assert post.value.status == 200
    m = Mitglied.objects.get(email="einwohner-browser@example.org")
    assert not m.parteikonto and not m.is_active and m.beitritt is None
    assert mail.outbox
    link = re.search(r"https?://[^\s]+/gemeinde/bestaetigen/[A-Za-z0-9_-]+/", mail.outbox[-1].body).group()
    p.goto(link)
    assert p.url.endswith(reverse("gemeinde:konto"))
    assert p.locator("h1").inner_text() == ("My municipal account" if englisch else "Mein Gemeindezugang")
    assert p.locator('a[href="/beitrag/"]').count() == 0
    assert p.locator('a[href="/einbringen/"]').count() == 0
    m.refresh_from_db()
    assert m.is_active and m.beitritt is None and m.mitgliedsnummer is None
    assert Gemeindezugang.objects.get(konto=m).bestaetigt_am is not None
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    p.screenshot(path=str(sichtpruefung / f"{bildname}-konto.png"), full_page=True)
