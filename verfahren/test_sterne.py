"""FB-C4 / FB-D2 „Alle mit dem Stern zum Favorisieren daneben“: Der Stern steht an jedem Antrag und
jedem Lebensbereich — Mitglieder schalten ihn, Gäste sehen ihn als Weg zur Anmeldung. Überall:
Parlament (Fächer, Feed, Kacheln, Suche), Startseite, Antragsseite, Umsetzungsregister."""

import pytest
from django.urls import reverse

from verfahren.models import Antrag, Kategorie, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _lage(ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    energie = Kategorie.objects.create(slug="energie", name="Energie")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    antrag.kategorien.add(energie)
    Antrag.objects.filter(pk=antrag.pk).update(hervorgehoben=True)
    return anna, antrag


def test_gaeste_sehen_ueberall_einen_stern_der_zur_anmeldung_fuehrt(client, ordnung):  # noqa: F811
    anna, antrag = _lage(ordnung)
    anmelden = reverse("mitglieder:login")
    parlament = client.get("/parlament/").content.decode()
    assert 'class="stern aus gast"' in parlament  # Fächer und Feed
    assert 'class="stern klein aus gast"' in parlament  # Themen-Stern im Kachelkopf
    assert parlament.count(f'href="{anmelden}"') >= 4
    assert "favorisieren/" not in parlament and "abonnieren/" not in parlament  # keine Formulare für Gäste
    assert 'class="stern aus gast"' in client.get("/").content.decode()  # Startseite: Wichtige Abstimmungen
    antragsseite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert f'class="stern aus gast" href="{anmelden}"' in antragsseite
    Antrag.objects.filter(pk=antrag.pk).update(phase="angenommen")
    assert 'class="stern aus gast"' in client.get(reverse("verfahren:umsetzung")).content.decode()


def test_mitglieder_schalten_den_stern_ueberall(client, ordnung):  # noqa: F811
    anna, antrag = _lage(ordnung)
    client.force_login(anna)
    parlament = client.get("/parlament/").content.decode()
    assert "gast" not in parlament.split('id="feld-filter"')[1].split("</section>")[0]
    assert f'action="/antrag/{antrag.pk}/favorisieren/"' in parlament
    assert 'action="/kategorien/energie/abonnieren/"' in parlament
    assert 'aria-pressed="false"' in parlament
    start = client.get("/").content.decode()
    assert f'action="/antrag/{antrag.pk}/favorisieren/"' in start
    client.post(reverse("verfahren:favorisieren", args=[antrag.pk]), {"weiter": "/"})
    assert 'aria-pressed="true"' in client.get("/").content.decode()
    Antrag.objects.filter(pk=antrag.pk).update(phase="angenommen")
    register = client.get(reverse("verfahren:umsetzung")).content.decode()
    assert f'action="/antrag/{antrag.pk}/favorisieren/"' in register and 'aria-pressed="true"' in register
