"""Mehrsprachigkeit (F-33): Deutsch als Standard, Englisch per Umschalter oder Browsersprache."""

import pytest
from django.urls import reverse

from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

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
        "/uebersicht/", "/umsetzung/", "/zukunftswerkstatt/", "/mitgliedschaft/",
    ):
        assert f'href="{ziel}"' in inhalt, ziel
    assert "KI schlägt vor, entscheidet nie" in inhalt  # die Grundsätze stehen am Einstieg
    assert "Die Wege durch die Plattform" in inhalt  # das Flussdiagramm der Prozesse
    assert 'class="fluss"' in inhalt and "ENTWURFSSCHLEIFE" in inhalt


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


def test_arbeitsbereiche_ohne_erklaer_und_werbesaetze(client):
    """Vorgabe 2.9.: Erklärt und beworben wird nur, wo Nichtmitglieder lesen —
    das Parlament und die Gremien-Arbeitsbereiche bleiben Werkzeug."""
    inhalt = client.get("/parlament/").content.decode()
    assert "Vier Bereiche, ein Grundsatz" not in inhalt
    assert "Richtschnur für DDÖ-Mandatsträger" not in inhalt
    assert "Hervorhebung nur durch begründeten" not in inhalt
    assert "Gereiht nach Ihren offenen Reglern" not in inhalt


def test_partner_seite_oeffentlich_und_zweisprachig(client):
    """P9-Erststufe (§ 12): Einladung, Fahrplan der Zusammenarbeit, Kontakt.

    Deutsch ausdrücklich anfordern: Ohne Sprachangabe antwortet diese Seite auf Englisch,
    weil ihre Zielgruppe außerhalb des deutschen Sprachraums sitzt (FB-M1)."""
    inhalt = client.get(reverse("verfahren:partner"), headers={"accept-language": "de"}).content.decode()
    assert "Labor der Demokratien" in inhalt
    assert "Software bereitstellen" in inhalt and "Parameter gemeinsam erheben" in inhalt
    assert "mailto:plattform@ddoe.at" in inhalt
    assert "Partner-Konto" in inhalt  # die kommende Rolle ist angekündigt
    inhalt = client.get(reverse("verfahren:partner"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "laboratory of democracies" in inhalt.lower() or "Laboratory of democracies" in inhalt
    fusszeile = client.get("/parlament/").content.decode()
    assert 'href="/partner/"' in fusszeile  # unaufdringlich über die Fußzeile


def test_uebersicht_zeigt_ki_verbrauch(client):
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert "KI-Verbrauch des Modell-Steckplatzes" in inhalt
    assert "archivierte Läufe" in inhalt and "Monatswechsel" in inhalt


# ── Gesamtprüfung 0.45 (Cluster D): Katalog und Seiten stimmen überein ────────────────────


def test_mehrzeilige_absaetze_sind_auf_englisch_uebersetzt(client):
    """Befund #58: Vierzehn von Hand geschriebene Katalogeinträge trugen rohe Zeilenumbrüche;
    die .mo führte gekürzte Schlüssel, und die Absätze blieben auf Englisch deutsch — auf der
    Willkommensseite, unter /rollen/, /regeln/, /gremien/fachliste/, /gremien/beschluesse/ und
    auf der 404-Seite. Hier werden genau diese Seiten auf Englisch gerendert."""
    en = {"HTTP_ACCEPT_LANGUAGE": "en"}
    faelle = [
        ("/", "The platform knows fourteen roles", "Die Plattform kennt vierzehn Rollen"),
        (reverse("verfahren:rollen"), "The general meeting is this platform", "was die Software heute davon kann, steht hier daneben"),
        (reverse("verfahren:rollen"), "This page is built from a versioned table", "Diese Seite entsteht aus einer versionierten Tabelle"),
        (reverse("parameter:regeln"), "The statute permits automated systems", "Die Satzung erlaubt automatisierte Systeme"),
        (reverse("parameter:regeln"), "This register is written by hand", "Dieses Verzeichnis ist von Hand geschrieben"),
        (reverse("gremien:fachliste"), "drawn from this roster", "Aus dieser Liste wird der Expertenrat"),
        (reverse("gremien:beschluesse"), "Every decision of a council appears here", "Jeder Beschluss eines Rates steht hier"),
        ("/diese-seite-gibt-es-nicht/", "Perhaps the link is out of date", "Vielleicht ist der Verweis veraltet"),
    ]
    for pfad, englisch, deutsch in faelle:
        inhalt = client.get(pfad, **en).content.decode()
        assert englisch in inhalt, f"{pfad}: englischer Absatz fehlt ({englisch!r})"
        assert deutsch not in inhalt, f"{pfad}: deutscher Absatz auf der englischen Seite ({deutsch!r})"


def test_nachgetragene_texte_sind_kompiliert():
    """Befunde #60, #61, #62, #63, #88: Texte, die mit `_()` oder `{% translate %}` markiert
    waren und trotzdem keinen (passenden) Katalogeintrag hatten — der Schlüssel der
    „Passt alles"-Zeile endete auf `%` statt `%%`, der Hilfetext der Gemeinde trug ein
    Leerzeichen vor dem Punkt. Geprüft wird die kompilierte .mo, nicht die .po."""
    from django.utils import translation
    from django.utils.translation import gettext, ngettext

    with translation.override("en"):
        assert gettext("Das kann nur, wer eine aktive Rolle im Integritätsrat hat.").startswith("Only someone")
        assert gettext("Stimme abgegeben — sie steht mit Ihrem Namen öffentlich.") == "Vote cast — it is public with your name."
        assert gettext("Frist %(frist)s") == "Deadline %(frist)s"
        assert gettext("%(a)s von %(n)s nötigen Stimmen") == "%(a)s of %(n)s votes needed"
        assert gettext("%(wert)s %% der Frist verstrichen") == "%(wert)s %% of the deadline elapsed"
        assert gettext("Sicherheitsaufgabe als Bild") == "Security task as an image"
        assert gettext("Die Auslosung ansehen →") == "View the draw →"
        assert gettext('„Passt alles": %(ja)s 👍 / %(nein)s 👎 = %(anteil)s %%').startswith('„Fine as it is"')
        assert gettext('„Passt alles": %(ja)s 👍 / %(nein)s 👎 (%(anteil)s %%)').endswith("(%(anteil)s %%)")
        assert gettext(
            "Bitte aus dem amtlichen Gemeindeverzeichnis wählen — Bezirk und Bundesland "
            "ordnen wir dann automatisch zu. Mit der ID Austria erfolgt das später amtlich."
        ).startswith("Please pick from the official municipal register")
        for deutsch, englisch in [("Eingebracht", "Submitted"), ("Fassung", "Version"), ("Prüfung", "Review"), ("Runde", "Round")]:
            assert gettext(deutsch) == englisch
        assert ngettext("Eine aktive Rolle", "%(n)s aktive Rollen", 3) == "%(n)s active roles"


def test_fristring_und_gemeindehilfe_auf_englisch(client):
    """Laufzeitprobe zu #61 und #63: das aria-label des Fristrings (in jeder Kachel mit Restfrist)
    und der Hilfetext im Registrierungsformular kommen auf Englisch englisch an. Der Ring wird
    direkt gerendert — entscheidend ist, dass Djangos Schlüssel `%(wert)s %% …` im Katalog steht."""
    from django.template.loader import render_to_string
    from django.utils import translation

    with translation.override("en"):
        svg = render_to_string("verfahren/_ring.html", {"wert": 42})
    assert "der Frist verstrichen" not in svg
    assert 'aria-label="42 % of the deadline elapsed"' in svg
    inhalt = client.get(reverse("mitglieder:registrieren"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Bitte aus dem amtlichen Gemeindeverzeichnis" not in inhalt
    assert "Please pick from the official municipal register" in inhalt


def test_markdown_export_auf_englisch_ist_nicht_gemischt(client, ordnung):  # noqa: F811
    """Befund #88: Der Markdown-Export eines Antrags war halb englisch, halb deutsch — zwölf
    Beschriftungen hatten keinen Katalogeintrag."""
    from verfahren.models import antrag_einbringen

    antrag = antrag_einbringen(mitglied_anlegen("exporttest"), **ANTRAG, ordnung=ordnung)
    text = client.get(
        reverse("verfahren:archiv_export", args=[antrag.pk, "md"]), HTTP_ACCEPT_LANGUAGE="en"
    ).content.decode()
    assert "Submitted:" in text and "## Version 1" in text
    for deutsch in ("Eingebracht:", "Unterstützungen", "## Fassung", "Beiträge"):
        assert deutsch not in text, f"deutsch im englischen Export: {deutsch}"


def test_datentabellen_werden_uebersetzt_wo_der_katalog_es_kann(client):
    """Befund #90: /rollen/, /regeln/ und /parameter/ trugen englische Überschriften über rein
    deutschen Datentabellen ohne Übersetzungsweg. Jetzt laufen die Datentexte per
    `{% translate variable %}` durch den Katalog — was dort steht, kommt englisch an, und ein
    Hinweis am Seitenkopf sagt ehrlich, dass die Einträge selbst noch deutsch vorliegen."""
    from parameter.models import erstbestand_sicherstellen

    erstbestand_sicherstellen()
    hinweis = "currently available in German only"
    en = {"HTTP_ACCEPT_LANGUAGE": "en"}
    rollen = client.get(reverse("verfahren:rollen"), **en).content.decode()
    assert hinweis in rollen
    assert 'title="available"' in rollen and 'title="planned"' in rollen  # Stand.name_de über den Katalog
    regeln = client.get(reverse("parameter:regeln"), **en).content.decode()
    assert hinweis in regeln
    assert ">decides <span" in regeln and "The result is binding" in regeln  # Wirkung über den Katalog
    register = client.get(reverse("parameter:liste"), **en).content.decode()
    assert hinweis in register
    assert '<span class="meta">Days</span>' in register  # Einheit über den Katalog
    # Auf Deutsch gibt es nichts zu erklären — der Hinweis erscheint nicht.
    for pfad in (reverse("verfahren:rollen"), reverse("parameter:regeln"), reverse("parameter:liste")):
        assert "nur auf Deutsch vor" not in client.get(pfad, HTTP_ACCEPT_LANGUAGE="de").content.decode()
