"""Öffentliche Ortssuche und vorhandener Sitzungsticker im echten Browser."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Mandat, Sitzung
from mitglieder.models import Gemeinde, Mitglied

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("handy,js,sprache", [
    (False, True, "de-AT"),
    (True, False, "de-AT"),
    (False, False, "en-GB"),
    (True, True, "en-GB"),
])
def test_ortsuebersicht_bis_zum_oeffentlichen_ticker(seite, live_server, sichtpruefung, handy, js, sprache):
    ort = Gemeinde.objects.create(kennziffer="40510", name="Beispielort", bezirk="Eferding", bundesland="Oberösterreich")
    Gemeinde.objects.create(kennziffer="41417", name="Beispielort", bezirk="Schärding", bundesland="Oberösterreich")
    mandatar = Mitglied.objects.create_user("Test-Mandatar")
    mandat = Mandat.objects.create(mitglied=mandatar, bezeichnung="Gemeinderat", gemeinde=ort)
    beginn = timezone.now() - timedelta(minutes=5)
    aufgabe = Aufgabe.objects.create(mandat=mandat, titel="Öffentliche Sitzung", sitzungstag=True, frist=beginn)
    sitzung = Sitzung.objects.create(mandat=mandat, aufgabe=aufgabe, beginn=beginn)
    p = seite(js=js, dunkel=handy, reduziert=True, sprache=sprache,
              viewport={"width": 390, "height": 844} if handy else {"width": 1440, "height": 900})
    p.goto(live_server.url + reverse("gemeinde:start"))
    p.locator("#ortssuche").fill("Beispielort")
    p.locator("#ortssuche").press("Enter")
    assert p.get_by_role("link", name="Beispielort (Schärding)", exact=False).is_visible()
    p.get_by_role("link", name="Beispielort (Eferding)", exact=False).press("Enter")
    assert p.get_by_role("heading", name="Beispielort", exact=True).is_visible()
    englisch = sprache.startswith("en")
    hinweis = "This is not an official municipal website." if englisch else "Dies ist keine amtliche Seite der Gemeinde."
    assert p.get_by_text(hinweis, exact=False).is_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    name = f"gemeindeort-{'handy' if handy else 'desktop'}-{'js' if js else 'ohne-js'}-{'en' if englisch else 'de'}"
    p.screenshot(path=str(sichtpruefung / f"{name}.png"), full_page=True)
    p.get_by_role("link", name="Öffentliche Sitzung", exact=False).press("Enter")
    assert p.url.endswith(reverse("mandatare:live", args=[mandat.pk]) + f"?sitzung={sitzung.pk}")
