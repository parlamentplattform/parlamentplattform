"""Das Hauptfenster in vier Bereichen (§ 5 Abs 10, F-40 bis F-43)."""

import pytest
from django.urls import reverse

from verfahren.models import Antrag, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


# --- Bereich a: Favoriten (F-41) -----------------------------------------------


def test_favorit_laesst_sich_setzen_und_entfernen(client, ordnung):  # noqa: F811
    autorin, anna = mitglied_anlegen("autorin"), mitglied_anlegen()
    antrag = antrag_einbringen(autorin, **ANTRAG, ordnung=ordnung)
    url = reverse("verfahren:favorisieren", args=[antrag.pk])

    assert client.post(url).status_code == 302  # anonym -> Login
    assert antrag.favoriten.count() == 0

    client.force_login(anna)
    client.post(url)
    assert antrag.favoriten.filter(mitglied=anna).exists()
    client.post(url)  # erneut: entfernen
    assert antrag.favoriten.count() == 0


def test_favorit_weiterleitung_nur_auf_interne_pfade(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen()
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    client.force_login(anna)
    url = reverse("verfahren:favorisieren", args=[antrag.pk])
    antwort = client.post(url, {"weiter": "https://boese.example"})
    assert antwort.url.startswith("/antrag/")  # externes Ziel wird ignoriert
    antwort = client.post(url, {"weiter": "//boese.example"})
    assert antwort.url.startswith("/antrag/")
    antwort = client.post(url, {"weiter": "/"})
    assert antwort.url == "/"


def test_gemerkte_antraege_bleiben_am_stern_erkennbar(client, ordnung):  # noqa: F811
    """Bereich a ist seit 1.9. abends der Fächer selbst; gemerkte Anträge
    tragen ihren Stern weiterhin überall (Kacheln, Antragsseite)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    laufend = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    anna = mitglied_anlegen()
    laufend.favoriten.create(mitglied=anna)

    client.force_login(anna)
    antwort = client.get(reverse("verfahren:parlament"))
    assert laufend.pk in antwort.context["meine_favoriten"]
    assert 'class="faecher"' in antwort.content.decode()  # das Feld gehört dem Fächer


# --- Bereich b: Hervorhebung (F-42) ---------------------------------------------


def test_hervorgehobene_antraege_erscheinen_im_bereich_b(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen()
    normal = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    wichtig = antrag_einbringen(anna, "Wichtig für alle", "Wortlaut.", "", ordnung)
    Antrag.objects.filter(pk=wichtig.pk).update(
        hervorgehoben=True, hervorhebung_begruendung="Beschluss IR-2026-01."
    )
    antwort = client.get(reverse("verfahren:parlament"))
    kacheln = antwort.context["wichtige_kacheln"]
    assert [k["antrag"].pk for k in kacheln] == [wichtig.pk]
    assert normal.pk not in [k["antrag"].pk for k in kacheln]
    assert "Beschluss IR-2026-01." in antwort.content.decode()


# --- Bereich c: regionale Ebenen (F-43) -----------------------------------------


def test_regionale_antraege_erscheinen_im_bereich_c(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen()
    antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)  # Bund
    regional = antrag_einbringen(
        anna,
        "Photovoltaik am Gemeindeamt",
        "Wortlaut.",
        "",
        ordnung,
        ebene="gemeinde",
        gebiet="St. Marienkirchen an der Polsenz",
    )
    antwort = client.get(reverse("verfahren:parlament"))
    gemeinde_zeile = next(z for z in antwort.context["region_zeilen"] if z["ebene"] == "gemeinde")
    assert [k["antrag"].pk for k in gemeinde_zeile["kacheln"]] == [regional.pk]
    assert "St. Marienkirchen an der Polsenz" in antwort.content.decode()


def test_regionaler_antrag_ist_an_die_eigene_region_gebunden(client, ordnung):  # noqa: F811
    """F-43: Das Gebiet kommt IMMER aus dem Wohnsitzprofil — freie Eingaben werden ignoriert."""
    client.force_login(mitglied_anlegen())
    daten = {**ANTRAG, "ebene": "gemeinde", "gebiet": "Wien"}  # Manipulationsversuch
    antwort = client.post(reverse("verfahren:einbringen"), daten)
    assert antwort.status_code == 302
    antrag = Antrag.objects.get()
    assert antrag.ebene == "gemeinde"
    assert antrag.gebiet == "St. Marienkirchen an der Polsenz"  # Wohnsitz, nicht „Wien“

    antwort = client.post(
        reverse("verfahren:einbringen"),
        {**ANTRAG, "titel": "Zweiter", "ebene": "land", "trotzdem": "1"},  # Ähnlichkeitshinweis überspringen
    )
    assert Antrag.objects.get(titel="Zweiter").gebiet == "Oberösterreich"


def test_ohne_wohnsitz_keine_regionale_ebene(client, ordnung):  # noqa: F811
    client.force_login(mitglied_anlegen("ohne", gemeinde="", bundesland=""))
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde"})
    assert antwort.status_code == 200  # ungültige Wahl -> Formular erneut
    assert Antrag.objects.count() == 0


def test_einbringen_ohne_ebene_ist_bundesweit(client, ordnung):  # noqa: F811
    client.force_login(mitglied_anlegen())
    client.post(reverse("verfahren:einbringen"), ANTRAG)  # kein ebene-Feld im POST
    assert Antrag.objects.get().ebene == "bund"


# --- Bereich d: Ähnlichkeitsübersicht mit Beteiligung (§ 5 Abs 10 lit d) --------


def test_aehnlichkeitshinweis_zeigt_beteiligung(client, ordnung):  # noqa: F811
    autorin = mitglied_anlegen("autorin")
    bestehend = antrag_einbringen(autorin, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    bestehend.unterstuetzungen.create(mitglied=mitglied_anlegen("anna"))
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(
        reverse("verfahren:einbringen"),
        {**ANTRAG, "titel": "Sitzungsprotokolle binnen 24 Stunden veröffentlichen"},
    )
    assert antwort.status_code == 200
    hinweis = antwort.context["aehnliche"][0]
    assert hinweis["beteiligung"] == 1
    assert "Beteiligung" in antwort.content.decode()
