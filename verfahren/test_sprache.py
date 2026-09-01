"""Mehrsprachigkeit (F-33): Deutsch als Standard, Englisch per Umschalter oder Browsersprache."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_standard_ist_deutsch(client):
    inhalt = client.get("/").content.decode()
    assert "Antrag einbringen" in inhalt
    assert "Wir sind das Werkzeug." in inhalt  # Willkommensseite
    inhalt = client.get("/parlament/").content.decode()
    assert "WeicherFilter" in inhalt and "Meine Region" in inhalt  # Vier-Felder-Parlament (P1)


def test_umschalter_wechselt_auf_englisch_und_zurueck(client):
    antwort = client.post(reverse("set_language"), {"language": "en", "next": "/parlament/"}, follow=True)
    inhalt = antwort.content.decode()
    assert "Submit a motion" in inhalt  # Navigation
    assert "My region" in inhalt  # Vier-Felder-Parlament (P1)
    assert "Become a member" in inhalt
    assert 'lang="en"' in inhalt

    antwort = client.post(reverse("set_language"), {"language": "de", "next": "/parlament/"}, follow=True)
    assert "Meine Favoriten" in antwort.content.decode()


def test_browsersprache_englisch_wird_erkannt(client):
    inhalt = client.get("/parlament/", HTTP_ACCEPT_LANGUAGE="en-GB,en;q=0.9").content.decode()
    assert "Important votes" in inhalt  # Vier-Felder-Parlament (P1)


def test_willkommen_und_parlament_sind_getrennte_seiten(client, django_user_model):
    """P1-Leitidee: „/" ist der erklärende Einstieg (auch übers Header-Logo),
    „/parlament/" die Arbeitsansicht — für Gäste wie Mitglieder."""
    inhalt = client.get("/").content.decode()
    assert "Wir sind das Werkzeug." in inhalt
    assert 'class="parlament"' not in inhalt  # das Raster wohnt nicht auf der Willkommensseite

    inhalt = client.get("/parlament/").content.decode()
    assert 'class="parlament"' in inhalt
    assert "als Gast" in inhalt  # Gast-Hinweisleiste

    nutzer = django_user_model.objects.create_user(username="willa", password="x")
    client.force_login(nutzer)
    inhalt = client.get("/").content.decode()
    assert "Wir sind das Werkzeug." in inhalt  # auch Mitglieder sehen den Einstieg


def test_willkommensseite_erklaert_das_system(client):
    """Der Einstieg erklärt das Verfahren Schritt für Schritt und stellt
    alle Bereiche mit Link vor — der Überblick über die ganze Plattform."""
    inhalt = client.get("/").content.decode()
    assert "So funktioniert das System" in inhalt
    for schritt in ("Einbringen", "Unterstützen", "Beraten", "Abstimmen", "Nachrechnen und umsetzen"):
        assert schritt in inhalt
    assert "Alle Bereiche im Überblick" in inhalt
    for ziel in (
        "/parlament/", "/einbringen/", "/mandatare/", "/gremien/",
        "/kategorien/", "/uebersicht/", "/umsetzung/", "/zukunftswerkstatt/", "/mitgliedschaft/",
    ):
        assert f'href="{ziel}"' in inhalt, ziel
    assert "KI schlägt vor, entscheidet nie" in inhalt  # die Grundsätze stehen am Einstieg


def test_uebersichtsseite_auf_englisch(client):
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert "The platform in numbers" in inhalt
    assert "without cookies" in inhalt  # auch die Zählerklärung ist übersetzt


def test_registrierungsformular_auf_englisch(client):
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    inhalt = client.get(reverse("mitglieder:registrieren")).content.decode()
    assert "Year of birth" in inhalt
    assert "Municipality of residence" in inhalt
    assert "Security question" in inhalt


def test_zukunftswerkstatt_oeffentlich_und_zweisprachig(client):
    """Die Aufklärungsseite (F-60ff., § 6 Abs 11): ohne Login lesbar, deutsch wie englisch."""
    antwort = client.get(reverse("verfahren:zukunftswerkstatt"))
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert "Die Zukunftswerkstatt" in inhalt
    assert "Die KI schlägt vor, sie entscheidet nie." in inhalt
    assert "plattform@ddoe.at" in inhalt

    antwort = client.get(reverse("verfahren:zukunftswerkstatt"), HTTP_ACCEPT_LANGUAGE="en")
    inhalt = antwort.content.decode()
    assert "The AI proposes, it never decides." in inhalt
    assert "laboratory of democracies" in inhalt

    # Die alte Adresse bleibt gültig und leitet dauerhaft weiter (keine toten Links).
    assert client.get("/staatssimulation/").status_code == 301


def test_mitgliedschaftsseite_oeffentlich_und_zweisprachig(client):
    """Das Schaufenster der Mitgliedschaft: plakative Rechte, der Weg zum Beschluss, ehrlich."""
    antwort = client.get(reverse("mitglieder:mitgliedschaft"))
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert "Was Sie als Mitglied können" in inhalt
    assert "Vom Antrag zum Beschluss" in inhalt
    assert "StaatsSimulation" in inhalt

    antwort = client.get(reverse("mitglieder:mitgliedschaft"), HTTP_ACCEPT_LANGUAGE="en")
    inhalt = antwort.content.decode()
    assert "What you can do as a member" in inhalt
    assert "One person, one vote" in inhalt


def test_nav_heisst_parlament(client):
    inhalt = client.get(reverse("verfahren:index")).content.decode()
    assert ">Parlament</a>" in inhalt
    inhalt = client.get(reverse("verfahren:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert ">Parliament</a>" in inhalt
