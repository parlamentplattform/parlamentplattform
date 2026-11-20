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
from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Drosselzaehler, Mitglied, Mitgliedsstatus
from mitglieder.test_verwaltung import admin_anlegen, detail
from uebersicht.models import TagesBesucher
from verfahren.models import Antrag, StimmRegister, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_datenschutzseite_ist_fuer_gaeste_erreichbar_und_freigegeben(client):
    """Der Gründer hat die Erklärung am 29.9.2026 freigegeben, die Berichtigung am 20.11.2026 (E-27)
    — kein Entwurfshinweis mehr; der Stand ist das Freigabedatum."""
    from verfahren.views import DATENSCHUTZ_STAND

    assert DATENSCHUTZ_STAND == "20.11.2026"
    antwort = client.get(reverse("verfahren:datenschutz"))
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    kopf = " ".join(inhalt.split())
    assert "ist ein Entwurf" not in kopf and "keine Zusage" not in kopf
    assert f"Stand: {DATENSCHUTZ_STAND}." in kopf and "— Entwurf" not in kopf
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


def test_startseite_und_meine_stimme_versprechen_keine_geheimheit(client, ordnung):  # noqa: F811
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


#: GP-161: Was je Zweck des Steckplatzes an den Anbieter geht — als Satzteil der Erklärung (Absatz
#: „empfaenger-ki“ oder Datenart „KI-Aufträge“) — und ob die Eingabe öffentlich nachlesbar ist (am
#: Antrag oder im Archivexport). Ein neuer Zweck ohne Eintrag lässt den Test scheitern.
ZWECKE_IN_DER_ERKLAERUNG = {
    Zweck.EINSCHAETZUNG: ("und ihren Entwurfsfassungen, Beratungsbeiträge und die Wünsche der Unterstützer an den Expertenrat", False),
    Zweck.RECHTSBEZUG: ("Titel, Wortlaut und Begründung von Sachanträgen", True),
    Zweck.RECHTSFOLGEN: ("Titel, Wortlaut und Begründung von Sachanträgen", True),
    Zweck.KORREKTUR: ("Beanstandungen öffentlicher Berichte", True),
    Zweck.GEGENUEBERSTELLUNG: ("Beim Absenden eines Sachantrags auf der Seite „Antrag einbringen“ gehen außerdem Titel und Wortlaut Ihres Entwurfs an ihn", False),
    Zweck.AEHNLICHKEIT: ("Beim Absenden eines Sachantrags auf der Seite „Antrag einbringen“ gehen außerdem Titel und Wortlaut Ihres Entwurfs an ihn", False),
    Zweck.PARAMETERVORSCHLAG: ("die Angaben eines Parametertests", False),
}


def test_jeder_zweck_des_steckplatzes_steht_in_der_erklaerung(client, settings, ordnung):  # noqa: F811
    """GP-161: Jeder Zweck hat einen Satzteil in der Erklärung; was nicht als öffentlich nachlesbar
    gilt, zeigen weder Antragsseite noch Archivexport noch Lauf-Archiv."""
    assert set(ZWECKE_IN_DER_ERKLAERUNG) == set(Zweck), "Zweck ohne Eintrag in der Datenschutzerklärung"
    settings.DDOE_KI_ANBIETER = "attrappe"
    text = _ki_absatz(client) + _karte(client, "datenarten")
    for zweck, (satzteil, _oeffentlich) in ZWECKE_IN_DER_ERKLAERUNG.items():
        assert satzteil in text, zweck

    m = mitglied_anlegen("anna")
    antrag = antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    verdeckt = {z: f"VERDECKTE-EINGABE-{z.value}" for z, (_s, oeffentlich) in ZWECKE_IN_DER_ERKLAERUNG.items() if not oeffentlich}
    for zweck, eingabe in verdeckt.items():
        KILauf.objects.create(zweck=zweck, antrag=antrag, angefordert_von=m, eingabe=eingabe, antwort="Antwort",
                              anbieter="attrappe", modell="probe")
    for seite in (
        reverse("verfahren:antrag", args=[antrag.pk]),
        reverse("verfahren:archiv_export", args=[antrag.pk, "json"]),
        reverse("verfahren:archiv_export", args=[antrag.pk, "md"]),
        reverse("verfahren:zukunftswerkstatt"),
    ):
        antwort = client.get(seite)
        assert antwort.status_code == 200, seite
        inhalt = antwort.content.decode()
        for zweck, eingabe in verdeckt.items():
            assert eingabe not in inhalt, (zweck, seite)


def test_ki_texte_nennen_nur_sachantraege_und_keine_nachlese_der_einschaetzung(client, settings):
    """Seit 0.113.0 gehen Titel und Wortlaut von Kandidaturen und Vertrauensfragen nicht mehr an den
    Anbieter (verfahren/aehnlichkeit.py, ki/warteschlange.py); die Eingabe der Einschätzung für die
    Gremien-Werkstatt zeigt keine Seite (nur Rechtsbezug und Rechtsfolgen haben die Klappe)."""
    settings.DDOE_KI_ANBIETER = "attrappe"
    absatz = _ki_absatz(client)
    assert "Begründung von Anträgen" not in absatz and "Beim Absenden auf der Seite" not in absatz
    assert "bei öffentlichen Berichten ist die Eingabe am Antrag nachlesbar" in absatz
    assert "das seine Texte nicht anzeigt" not in absatz
    ki = re.search(r"<strong>KI-Aufträge:</strong>(.*?)</li>", _karte(client, "datenarten")).group(1)
    assert "die Eingabe zeigt die Plattform nicht an" not in ki
    assert "Bei Berichten zu einem Antrag (betroffene Gesetze, Rechtsfolgen) ist die Eingabe am Antrag und im Archivexport öffentlich nachlesbar; das Konto dahinter nicht." in ki
    assert "Eingaben zur Einschätzung für die Gremien-Werkstatt, zu Entwürfen vor dem Einbringen und zu Parametertests zeigt die Plattform nicht an." in ki


def _karte(client, kennung: str) -> str:
    """Der Text einer Karte der Datenschutzseite, Leerraum zusammengezogen."""
    inhalt = " ".join(client.get(reverse("verfahren:datenschutz")).content.decode().split())
    treffer = re.search(rf'id="{kennung}">(.*?)</div>', inhalt)
    assert treffer, kennung
    return treffer.group(1)


def test_speicherdauer_ausschluss_leert_nichts_und_austritt_pseudonymisiert(client):
    """Nur der Austritt leert Name, E-Mail-Adresse und Wohnsitz; der Ausschluss sperrt nur. Was
    bleibt, ist pseudonymisiert („Ehemaliges Mitglied n“ oder das Pseudonym), nicht anonymisiert."""
    m = mitglied_anlegen("erich")
    client.force_login(admin_anlegen())
    client.post(detail(m.pk), {"aktion": "ausschliessen", "grund": "Schiedsgericht, Entscheidung 1/2026"})
    m = Mitglied.objects.get(pk=m.pk)
    assert m.status == Mitgliedsstatus.AUSGESCHLOSSEN and m.email == "erich@example.org"

    karte = _karte(client, "speicherdauer")
    assert "Austritt oder Ausschluss" not in karte and "Wohnsitz anonymisiert" not in karte
    assert "pseudonymisiert, nicht anonymisiert" in karte and "„Ehemaliges Mitglied n“" in karte
    assert "Ausschluss sperrt das Konto" in karte


def test_speicherdauer_nennt_was_der_austritt_am_konto_laesst(client):
    """GP-092, längere Fassung (E-27): Solange die Löschung der Reste nicht gebaut ist (E-41), nennt die
    Erklärung alles, was `austreten` am geschlossenen Konto stehen lässt — der Test prüft beides."""
    from datetime import date
    from decimal import Decimal

    from django.utils import timezone

    from anstoss.models import Anstoss
    from mitglieder.models import Beitragseingang, Gemeindezugang, Postauftrag
    from mitglieder.profil import austreten

    m = mitglied_anlegen("greta")
    client.force_login(m)
    jetzt = timezone.now()
    Mitglied.objects.filter(pk=m.pk).update(mitgliedsnummer=4711, beitragsreferenz_stamm="AB12CD",
                                            ausweis_code="PRUEFCODE", ausweis_ausgestellt_am=jetzt)
    Beitragseingang.objects.create(mitglied=m, betrag=Decimal("24.00"), gebucht_am=date(2026, 11, 2), umsatz_id="U-1")
    Postauftrag.objects.create(mitglied=m, art="willkommen")
    Anstoss.objects.create(text="Bitte prüfen", seite="/", nutzer=m)
    Gemeindezugang.objects.create(konto=m, angemeldet_am=jetzt, alter_erklaert_am=jetzt)
    austreten(Mitglied.objects.get(pk=m.pk), jetzt)

    m = Mitglied.objects.get(pk=m.pk)
    assert m.email == "" and m.mitgliedsnummer == 4711 and m.beitragsreferenz_stamm == "AB12CD"
    assert m.ausweis_code == "PRUEFCODE" and m.last_login is not None
    assert Beitragseingang.objects.filter(mitglied=m).exists() and Postauftrag.objects.filter(mitglied=m).exists()
    assert Anstoss.objects.filter(nutzer=m).exists() and Gemeindezugang.objects.filter(konto=m).exists()

    karte = _karte(client, "speicherdauer")
    assert (
        "eine solche Frist gibt es heute noch nicht. Aus Gründen der Buchhaltung bleiben außerdem Ihre Mitgliedsnummer, "
        "der Stamm Ihrer Zahlungsreferenz und die verbuchten Beitragseingänge (Datum, Betrag, Umsatzkennung) am "
        "geschlossenen Konto sowie die Liste der an Ihr Konto gesandten Nachrichten (ohne Inhalt), Ihre Anstöße mit "
        "Kontobezug, ein Gemeindezugang, der Prüfcode Ihres Mitgliedsausweises und der Zeitpunkt Ihrer letzten "
        "Anmeldung. Die Audit-Kette wird nie gelöscht"
    ) in karte


def test_zahlungsreferenz_haengt_an_der_konto_kennung_nicht_an_der_mitgliedsnummer(client):
    for i in range(3):
        mitglied_anlegen(f"vor{i}")
    m = mitglied_anlegen("zora")
    Mitglied.objects.filter(pk=m.pk).update(mitgliedsnummer=1)
    m.refresh_from_db()
    assert m.pk != 1 and beitragsreferenz(m).startswith(f"DDOE-{m.pk:04d}-")

    karte = _karte(client, "datenarten")
    assert "aus der Mitgliedsnummer" not in karte
    assert "aus der Konto-Kennung und einem festen Stamm" in karte


def test_bankabgleich_nennt_die_daten_der_ueberweisenden_auch_beim_kontoauszug(client, settings):
    settings.DDOE_BANK_SECRET_ID = "id"
    settings.DDOE_BANK_SECRET_KEY = "schluessel"
    inhalt = " ".join(client.get(reverse("verfahren:datenschutz")).content.decode().split())
    bank = re.search(r'id="empfaenger-bank">(.*?)</li>', inhalt).group(1)
    assert "keine Daten von Mitgliedern" not in bank
    assert "Name, IBAN und Verwendungszweck der Überweisenden" in bank
    assert "Kontoauszug" in _karte(client, "datenarten")


def test_lichtbild_ist_kein_profilschalter_und_auch_die_verwaltung_stellt_es_ein(client):
    """Das Profil hat keinen Schalter für das Lichtbild am Mandat; entfernt wird es mit dem Austritt
    (mitglieder/profil.py austreten) — und hochladen kann es auch die Verwaltung."""
    datenarten = _karte(client, "datenarten")
    assert "vom Mandatar selbst eingestellt" not in datenarten
    assert "vom Mandatar selbst oder von der Verwaltung" in datenarten
    rechtsgrundlage = _karte(client, "rechtsgrundlage")
    assert "drei Dinge, die Sie jederzeit im Profil zurücknehmen können" not in rechtsgrundlage
    assert "widerrufen Sie bei der Verwaltung" in rechtsgrundlage and "Austritt" in rechtsgrundlage
    assert "Einwilligungen ändern Sie dort" not in _karte(client, "rechte")


def test_besuche_nennen_tageskennung_und_die_adresse_in_der_drossel(client):
    browser = "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"
    client.get(reverse("verfahren:index"), HTTP_USER_AGENT=browser)
    assert len(TagesBesucher.objects.get().kennung) == 16
    client.post(reverse("mitglieder:login"), {"email": "wer@example.org"}, HTTP_USER_AGENT=browser)
    assert Drosselzaehler.objects.filter(kennung="127.0.0.1").exists()

    karte = _karte(client, "datenarten")
    assert "keine Kennungen" not in karte and "Keine IP-Adressen" not in karte
    assert "Tages-Summen je Seite" not in karte and "je Antrag" in karte
    assert "Besucherkennung" in karte and "rund zwei Stunden" in karte


def test_cookies_nennen_die_rueckmeldung_und_den_browserspeicher(client):
    """Die Standard-Nachrichtenablage legt das Cookie „messages“ an; Erscheinungsbild, Filterleiste,
    Leseposition und Fokus-Modus liegen im Browserspeicher des Geräts (app.js)."""
    client.force_login(mitglied_anlegen("anna"))
    antwort = client.post(reverse("mitglieder:abmelden"))
    assert antwort.cookies["messages"].value

    karte = _karte(client, "cookies")
    # GP-024: die Dauern, die Django ohne eigene Einstellung setzt (config/settings.py setzt keine).
    from django.conf import settings

    assert settings.SESSION_COOKIE_AGE == 14 * 24 * 3600 and "(sessionid, Anmeldung, 14 Tage)" in karte
    assert settings.CSRF_COOKIE_AGE == 52 * 7 * 24 * 3600 and "(csrftoken, ein Jahr)" in karte
    assert settings.LANGUAGE_COOKIE_AGE is None  # bis zum Schließen des Browsers; die Karte nennt keine Dauer
    assert "Drei, alle technisch" not in karte
    for name in ("sessionid", "csrftoken", "django_language", "messages", "Browserspeicher"):
        assert name in karte, name
    rollen = " ".join(client.get(reverse("verfahren:rollen")).content.decode().split())
    assert "keine Cookies außer Session, CSRF und" not in rollen
    assert "der kurzen Rückmeldung nach einer Handlung" in rollen


def test_datenarten_nennen_adresswechsel_ausweis_und_anmeldezeiten(client):
    """GP-024: Adresswechsel (mitglieder/models.py Adresswechsel), Mitgliedsausweis (ausweis_code,
    ausweis_ausgestellt_am) und die Anmeldezeiten des Kontos (date_joined, last_login) stehen in der Liste."""
    m = mitglied_anlegen("anna")
    client.force_login(m)
    m.refresh_from_db()
    assert m.last_login is not None and m.date_joined is not None
    karte = _karte(client, "datenarten")
    for teil in (
        "<strong>Adresswechsel:</strong> wenn die Verwaltung Ihre Anmeldeadresse ändert",
        "Nach einem Austritt bleibt davon nur der Vorgang ohne Adresse.",
        "<strong>Mitgliedsausweis:</strong> ein Prüfcode",
        "damit gedruckte Ausweise gültig bleiben",
        "<strong>Anmeldung:</strong> wann Ihr Konto angelegt wurde und wann Sie sich zuletzt angemeldet haben.",
    ):
        assert teil in karte, teil


def test_datenarten_nennen_fachliste_rollen_ki_und_ueberzeichnen_unterstuetzungen_nicht(client):
    karte = _karte(client, "datenarten")
    for teil in ("Fachliste", "Interessenbindungen", "Honorare", "Gremienrollen", "Lauf-Archiv"):
        assert teil in karte, teil
    assert "Unterstützungen, Beratungsbeiträge, Reaktionen" not in karte
    assert "Unterstützungen und Reaktionen" in karte and "nur die Zahl" in karte
