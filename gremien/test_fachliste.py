"""Die öffentliche Fachliste und der Lostopf (§ 6 Abs 7, FB-I1).

Die Satzung verlangt eine „öffentlich geführte Liste", aus der die Fachleute je Antrag
ausgelost werden — samt „Offenlegung von Interessenbindungen und Honoraren". Ohne diese Liste
wäre das Los eine Auswahl unter Unbekannten.
"""

from __future__ import annotations

import itertools
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Fachliste, Gremium, lostopf_der_fachliste, unvereinbar
from gremien.test_werkstatt import mitglied_anlegen, rolle_geben  # noqa: F401
from plattform_core.losziehung import ziehen
from verfahren.models import Kategorie

pytestmark = pytest.mark.django_db

_ZAEHLER = itertools.count()


def eintragen(name: str | None = None, fachgebiete=(), **felder) -> Fachliste:
    mitglied = mitglied_anlegen(name or f"fach{next(_ZAEHLER)}")
    eintrag = Fachliste.objects.create(mitglied=mitglied, **felder)
    for slug in fachgebiete:
        kategorie, _ = Kategorie.objects.get_or_create(
            slug=slug, defaults={"name": slug.capitalize()}
        )
        eintrag.fachgebiete.add(kategorie)
    return eintrag


def test_jeder_eintrag_bekommt_einen_stabilen_schluessel():
    """Mit ihm rechnet die Ziehung — er muss bleiben, auch wenn der Name geht."""
    eintrag = eintragen()
    schluessel = eintrag.schluessel
    assert schluessel.startswith("F-") and len(schluessel) == 10
    eintrag.interessenbindungen = "Vorstand eines Verkehrsvereins"
    eintrag.save()
    eintrag.refresh_from_db()
    assert eintrag.schluessel == schluessel


def test_nach_widerruf_steht_der_schluessel_statt_des_namens():
    """§ 8 Abs 4: „nach Widerruf werden die betroffenen Inhalte pseudonymisiert, wobei der
    sachliche Inhalt … erhalten bleibt." Loswert und Platz bleiben also nachrechenbar."""
    eintrag = eintragen("frau-mueller")
    assert eintrag.anzeigename == eintrag.mitglied.anzeigename
    eintrag.einwilligung_widerrufen_am = timezone.localdate()
    eintrag.save(update_fields=["einwilligung_widerrufen_am"])
    assert eintrag.anzeigename == eintrag.schluessel


def test_die_liste_steht_oeffentlich_mit_interessenbindungen_und_honoraren(client):
    """§ 6 Abs 7 nennt beides ausdrücklich — und die Liste ist ohne Anmeldung zu lesen."""
    eintragen(
        fachgebiete=["verkehr"],
        interessenbindungen="Beirat einer Verkehrsplanungsgesellschaft",
        honorare="Gutachten für die Stadt Linz, 2025, 3.400 Euro",
    )
    inhalt = client.get(reverse("gremien:fachliste")).content.decode()
    assert "Beirat einer Verkehrsplanungsgesellschaft" in inhalt
    assert "Gutachten für die Stadt Linz" in inhalt
    assert "Verkehr" in inhalt


def test_wer_im_integritaetsrat_sitzt_lost_nicht_mit():
    """§ 6 Abs 3 lit a: „Seine Mitglieder dürfen keinem anderen Rat angehören.\"

    Geprüft wird am Lostopf, nicht in der Ansicht: Wer es dort vergisst, hat es nie."""
    eintrag = eintragen()
    assert unvereinbar(eintrag.mitglied) == ""
    rolle_geben(eintrag.mitglied, Gremium.INTEGRITAETSRAT)
    assert "Integritätsrats" in unvereinbar(eintrag.mitglied)
    kandidat = next(k for k in lostopf_der_fachliste() if k.schluessel == eintrag.schluessel)
    assert kandidat.ausgeschlossen is True


def test_wer_ein_mandat_ausuebt_lost_nicht_mit():
    from mandatare.models import Mandat

    eintrag = eintragen()
    Mandat.objects.create(mitglied=eintrag.mitglied, bezeichnung="Gemeinderat")
    assert "Mandat" in unvereinbar(eintrag.mitglied)


def test_ein_beendetes_mandat_hindert_nicht():
    from mandatare.models import Mandat

    eintrag = eintragen()
    Mandat.objects.create(
        mitglied=eintrag.mitglied,
        bezeichnung="Gemeinderat",
        beendet=timezone.localdate() - timedelta(days=1),
    )
    assert unvereinbar(eintrag.mitglied) == ""


def test_ein_gestrichener_eintrag_bleibt_lesbar_lost_aber_nicht_mehr():
    """Grundregel 7: Aus dem Eintrag wurde vielleicht schon gelost — dann muss er bleiben."""
    eintrag = eintragen(gestrichen_am=timezone.localdate(), gestrichen_grund="Auf eigenen Wunsch.")
    kandidat = eintrag.als_kandidat()
    assert kandidat.ausgeschlossen is True and kandidat.ausschlussgrund == "gestrichen"
    assert Fachliste.objects.filter(pk=eintrag.pk).exists()


def test_aus_der_fachliste_laesst_sich_wirklich_ziehen():
    """Der Weg vom Modell in den Kern — ohne Django-Objekte in der Rechnung."""
    for _ in range(8):
        eintragen(fachgebiete=["verkehr"])
    kandidaten = lostopf_der_fachliste()
    ziehung = ziehen("a" * 64, kandidaten, [3], fachgebiete=["verkehr"])
    assert len(ziehung.gruppen[0]) == 3
    gezogen = {p.schluessel for p in ziehung.plaetze}
    assert gezogen <= set(Fachliste.objects.values_list("schluessel", flat=True))


def test_die_unvereinbarkeit_kostet_nicht_zwei_abfragen_je_kopf(client):
    """Befund #44: Liste und Lostopf prüften je Eintrag Integritätsrat und Mandat einzeln —
    bei 2.000 Fachleuten 4.000 Abfragen je Aufruf, und der Lostopf läuft in der Anfrage eines
    beliebigen Besuchers. Jetzt zwei Mengen für alle: Die Zahl der Abfragen wächst nicht mit."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    rolle_geben(eintragen().mitglied, Gremium.INTEGRITAETSRAT)
    for _ in range(4):
        eintragen(fachgebiete=("verkehr",))
    with CaptureQueriesContext(connection) as klein:
        assert client.get(reverse("gremien:fachliste")).status_code == 200
    with CaptureQueriesContext(connection) as topf_klein:
        lostopf_der_fachliste()
    for _ in range(20):
        eintragen(fachgebiete=("verkehr", "bildung"))
    with CaptureQueriesContext(connection) as gross:
        antwort = client.get(reverse("gremien:fachliste"))
    with CaptureQueriesContext(connection) as topf_gross:
        topf = lostopf_der_fachliste()
    assert len(gross) == len(klein), f"Liste: {len(klein)} → {len(gross)} Abfragen"
    assert len(topf_gross) == len(topf_klein), f"Lostopf: {len(topf_klein)} → {len(topf_gross)} Abfragen"
    assert antwort.context["gefuehrt"] == 24  # die Regel gilt weiter: der Integritätsrat lost nicht mit
    assert sum(1 for k in topf if k.ausgeschlossen) == 1
    assert {"verkehr", "bildung"} <= {slug for k in topf for slug in k.fachgebiete}


def test_die_seite_sagt_ehrlich_dass_der_bestellweg_fehlt(client):
    """§ 6 Abs 8 verlangt Ausschreibung und Bestätigung durch die Mitgliederversammlung.

    Beides gibt es nicht — und die Seite behauptet es auch nicht."""
    eintragen()
    inhalt = client.get(reverse("gremien:fachliste")).content.decode()
    assert "noch\nnicht" in inhalt or "noch nicht" in inhalt
    assert "trägt die Verwaltung die Liste ein" in inhalt
