"""Wächter für die Abgrenzung (GP-108): Jede Seite unter /gemeinde/ort/<kennziffer>/ sagt, dass sie keine
amtliche Seite der Gemeinde ist — auf Deutsch und auf Englisch."""

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Gemeindeprojekt, Gemeindeprojektstand, Mandat, Ratsinitiative
from mitglieder.gemeinde_urls import urlpatterns
from mitglieder.models import Gemeinde
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

SATZ = {"de": "Dies ist keine amtliche Seite der Gemeinde.", "en": "This is not an official municipal website."}


@pytest.fixture
def ort():
    gemeinde = Gemeinde.objects.create(kennziffer="40510", name="Gleichort", bezirk="Eferding", bundesland="oberoesterreich")
    mandat = Mandat.objects.create(mitglied=mitglied_anlegen("ratsmitglied"), bezeichnung="Gemeinderat", gemeinde=gemeinde)
    projekt = Gemeindeprojekt.objects.create(mandat=mandat, gemeinde=gemeinde)
    Gemeindeprojektstand.objects.create(
        projekt=projekt, lage="vorgestellt", titel="Radweg", quelle="https://gemeinde.example.org/a.pdf", stand_am=timezone.localdate(),
    )
    initiative = Ratsinitiative.objects.create(
        mandat=mandat, gemeinde=gemeinde, art=Ratsinitiative.Art.values[0], titel="Radweg", text="Vorhaben."
    )
    return gemeinde, {"projekt": projekt.pk, "ratsinitiative": initiative.pk}


def _seiten_des_orts(gemeinde, kennungen):
    seiten = []
    for muster in urlpatterns:
        if "<str:kennziffer>" not in str(muster.pattern):
            continue
        argumente = {"kennziffer": gemeinde.kennziffer}
        if "<int:pk>" in str(muster.pattern):
            argumente["pk"] = kennungen[muster.name]
        seiten.append(reverse(f"gemeinde:{muster.name}", kwargs=argumente))
    return seiten


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_jede_seite_des_orts_traegt_den_abgrenzungssatz(client, ort, sprache):
    gemeinde, kennungen = ort
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = sprache
    seiten = _seiten_des_orts(gemeinde, kennungen)
    assert len(seiten) >= 7
    for url in seiten:
        antwort = client.get(url)
        assert antwort.status_code == 200, url
        assert SATZ[sprache] in antwort.content.decode(), url
