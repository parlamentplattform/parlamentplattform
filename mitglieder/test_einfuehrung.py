"""Die Einführung nach der Bestätigung (F-53): drei Schritte, überspringbar."""

import re

import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from mitglieder.test_views import ANMELDUNG, botschutz
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _stammdaten(db):
    call_command("gemeinden_laden")
    call_command("kategorien_laden")


def test_bestaetigungslink_fuehrt_in_die_einfuehrung(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    link = re.search(r"http://testserver(/\S+)", mail.outbox[0].body).group(1)
    antwort = client.get(link, follow=True)
    assert antwort.request["PATH_INFO"] == reverse("mitglieder:einfuehrung", args=[1])
    inhalt = antwort.content.decode()
    assert "Finden Sie Ihre Lebensbereiche" in inhalt
    assert "Einführung überspringen" in inhalt  # nichts ist Pflicht (§ 2 Abs 6)
    assert len(antwort.context["saeulen"]) == 4


def test_einfuehrung_verlangt_anmeldung_und_kennt_nur_drei_schritte(client):
    antwort = client.get(reverse("mitglieder:einfuehrung", args=[1]))
    assert antwort.status_code == 302  # anonym -> Login
    client.force_login(mitglied_anlegen())
    assert client.get(reverse("mitglieder:einfuehrung", args=[9])).status_code == 404


def test_schritt_zwei_zeigt_eine_laufende_abstimmung(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    abstimmung = in_abstimmung_bringen(antrag_fixture(leute[0], ordnung), leute[1:])
    client.force_login(leute[0])
    antwort = client.get(reverse("mitglieder:einfuehrung", args=[2]))
    assert antwort.context["abstimmung"] == abstimmung
    assert "Pseudonym" in antwort.content.decode()


def antrag_fixture(mitglied, ordnung):  # noqa: F811
    from verfahren.models import antrag_einbringen

    return antrag_einbringen(mitglied, **ANTRAG, ordnung=ordnung)


def test_schritt_drei_fuehrt_zum_beitrag(client):
    client.force_login(mitglied_anlegen())
    inhalt = client.get(reverse("mitglieder:einfuehrung", args=[3])).content.decode()
    assert "hnliche laufende Antr" in inhalt  # erklärt den Ähnlichkeitshinweis
    assert reverse("mitglieder:willkommen") in inhalt  # Abschluss: Beitrags-QR
