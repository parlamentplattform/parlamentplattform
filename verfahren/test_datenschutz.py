"""Die Datenschutzerklärung (Bestandsaufnahme 28.9.2026, C3) — und die ehrlichen Texte drumherum.

Die Seite sagt nur, was der Code tut: Der Absatz zum KI-Anbieter erscheint nur mit angeschlossenem
Steckplatz, der zum Kontoinformationsdienst nur mit hinterlegtem Schlüsselpaar. Sie ist für Gäste
erreichbar, aus der Fußzeile, der Registrierung und dem Anstoß-Widget verlinkt — und die Startseite
verspricht keine Geheimheit mehr, die ADR-003 ausdrücklich nicht zusagt (C1).
"""

from __future__ import annotations

import re
import uuid

import pytest
from django.urls import reverse

from ki.models import KILauf, Zweck
from verfahren.models import Antrag, StimmRegister, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_datenschutzseite_ist_fuer_gaeste_erreichbar_und_als_entwurf_gekennzeichnet(client):
    antwort = client.get(reverse("verfahren:datenschutz"))
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert "Entwurf" in inhalt
    for pflicht in (
        "Direkte Demokratie Österreich",
        "Unterfreundorf 17",
        "502117",
        "plattform@ddoe.at",
        "Art 9 Abs 2 lit d",
        "Render Services, Inc.",
        "World4You",
        "Datenschutzbehörde",
        "§ 8 Abs 6",
        'id="cookies"',
    ):
        assert pflicht in inhalt, pflicht
    # Ehrlich zur Löschfrist (D-K5b offen) — kein Versprechen einer Frist, die es nicht gibt.
    assert "noch nicht" in inhalt


def test_ki_absatz_erscheint_nur_mit_angeschlossenem_steckplatz(client, settings):
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    assert 'id="empfaenger-ki"' not in client.get(reverse("verfahren:datenschutz")).content.decode()
    settings.DDOE_KI_ANBIETER = "attrappe"
    inhalt = client.get(reverse("verfahren:datenschutz")).content.decode()
    assert 'id="empfaenger-ki"' in inhalt and "attrappe" in inhalt


def test_bank_absatz_erscheint_nur_mit_hinterlegtem_schluesselpaar(client, settings):
    settings.DDOE_BANK_SECRET_ID = ""
    settings.DDOE_BANK_SECRET_KEY = ""
    assert 'id="empfaenger-bank"' not in client.get(reverse("verfahren:datenschutz")).content.decode()
    settings.DDOE_BANK_SECRET_ID = "id"
    settings.DDOE_BANK_SECRET_KEY = "schluessel"
    assert 'id="empfaenger-bank"' in client.get(reverse("verfahren:datenschutz")).content.decode()


def test_fusszeile_registrierung_und_anstoss_verlinken_die_erklaerung(client):
    ziel = reverse("verfahren:datenschutz")
    start = client.get(reverse("verfahren:index")).content.decode()
    assert f'href="{ziel}">Datenschutz</a>' in start  # Fußzeile
    registrierung = client.get(reverse("mitglieder:registrieren")).content.decode()
    assert "Keine Weitergabe" not in registrierung
    assert "Weitergabe nur an unsere Dienstleister" in registrierung
    assert f'<a href="{ziel}">Datenschutzerklärung</a>' in registrierung
    parlament = client.get(reverse("verfahren:parlament")).content.decode()
    assert "<footer" not in parlament  # das Parlament hat keine Fußzeile (FB-A1) …
    assert ziel in parlament  # … der Link steht dort im Anstoß-Widget


def test_startseite_und_meine_stimme_versprechen_keine_geheimheit(client):
    """C1: ADR-003 sagt „pseudonym-offen“, der Betreiber kann zuordnen — die Startseite darf nicht
    „keinem Menschen zuzuordnen“ behaupten, und das Flussdiagramm nennt die Stufe nicht „geheim“."""
    inhalt = client.get(reverse("verfahren:index")).content.decode()
    assert "keinem Menschen zuzuordnen" not in inhalt
    assert "Tage · geheim" not in inhalt and "geheim · mehreren" not in inhalt
    assert "pseudonym-offen" in inhalt and "nicht kryptografisch geheim" in inhalt
    assert "Tage · pseudonym" in inhalt and "pseudonym · mehreren zustimmbar" in inhalt


def test_kein_text_verspricht_ein_zugriffsprotokoll_auf_das_stimmregister(client, ordnung):  # noqa: F811
    """Kein Code-Pfad protokolliert einen Lesezugriff auf das Stimmregister (Seite „Meine Stimme“,
    Parlament, Betreiberzugriff auf die Datenbank). Startseite, Datenschutzerklärung und „Meine
    Stimme“ dürfen deshalb nur „zugriffsbeschränkt“ sagen, nicht „protokolliert“."""
    m = mitglied_anlegen("anna")
    antrag = antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    StimmRegister.objects.create(antrag=antrag, mitglied=m, pseudonym=uuid.uuid4())
    client.force_login(m)
    for seite in (
        reverse("verfahren:eigene_stimme", args=[antrag.pk]),
        reverse("verfahren:index"),
        reverse("verfahren:datenschutz"),
    ):
        inhalt = " ".join(client.get(seite).content.decode().split())
        assert "zugriffsbeschränkt" in inhalt, seite
        assert "Zugriff wird protokolliert" not in inhalt, seite
        assert "zugriffsbeschränkt und protokolliert" not in inhalt, seite


def _ki_absatz(client) -> str:
    inhalt = " ".join(client.get(reverse("verfahren:datenschutz")).content.decode().split())
    treffer = re.search(r'id="empfaenger-ki">(.*?)</li>', inhalt)
    assert treffer, "Absatz zum KI-Anbieter fehlt"
    return treffer.group(1)


def test_der_entwurf_geht_vor_dem_einbringen_an_den_anbieter_und_die_texte_sagen_es(client, settings, ordnung):  # noqa: F811
    """Stufe 2 der Ähnlichkeit schickt Titel und Wortlaut des noch nicht eingebrachten Entwurfs an
    den Anbieter; der Lauf bleibt im Archiv, auch wenn das Mitglied danach nicht einbringt. Das
    Verhalten bleibt (Entscheidung vom 29.9.2026) — Datenschutzerklärung und Einbringen-Seite sagen
    es, statt nur von „ohnehin öffentlichen“ Texten zu sprechen."""
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag_einbringen(mitglied_anlegen("bernd"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    m = mitglied_anlegen("anna")
    client.force_login(m)
    entwurf = "Ein Entwurfssatz, der nie eingebracht wird."
    antwort = client.post(
        reverse("verfahren:einbringen"),
        {
            "titel": ANTRAG["titel"],
            "wortlaut": f"{ANTRAG['wortlaut']} {entwurf}",
            "begruendung": "",
            "ebene": "bund",
            "art": "sache",
        },
    )
    assert antwort.status_code == 200 and Antrag.objects.count() == 1  # Hinweis, nichts eingebracht
    lauf = KILauf.objects.get(zweck=Zweck.AEHNLICHKEIT, antrag=None, angefordert_von=m)
    assert entwurf in lauf.eingabe

    absatz = _ki_absatz(client)
    assert "ohnehin öffentlich" not in absatz
    assert "Entwurf" in absatz and "Lauf-Archiv" in absatz

    satz = "zum Bedeutungsvergleich an den KI-Anbieter"
    einbringen = " ".join(client.get(reverse("verfahren:einbringen")).content.decode().split())
    assert satz in einbringen and "attrappe" in einbringen
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    assert satz not in client.get(reverse("verfahren:einbringen")).content.decode()
