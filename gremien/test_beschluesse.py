"""Interne Beschlüsse: Nummer, Anlass, Öffentlichkeit (FB-I4, § 6 Abs 9, § 5 Abs 10 lit b).

Die Beschlüsse eines Rates sind kein Interna-Ordner. § 6 Abs 9 verlangt Öffentlichkeit mit
Namen, § 5 Abs 10 lit b spricht vom „veröffentlichten, begründeten Beschluss". Ein Beschluss,
den nur das beschließende Gremium lesen kann, ist nicht veröffentlicht — deshalb prüfen diese
Tests vor allem, was ein **Gast** sieht.
"""

import itertools
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import (
    Anlass,
    BeschlussStatus,
    GremienBeschluss,
    Gremium,
    beschlussnummer,
)
from gremien.test_werkstatt import mitglied_anlegen, rolle_geben  # noqa: F401

pytestmark = pytest.mark.django_db

OPTIONEN = [{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}]


#: Laufende Nummer fuer die Testmitglieder — mitglied_anlegen verlangt einen freien Namen.
_ZAEHLER = itertools.count()


def beschluss_anlegen(gremium=Gremium.KOORDINATIONSRAT, **felder):
    wer = felder.pop("angelegt_von", None) or mitglied_anlegen(f"anlegerin{next(_ZAEHLER)}")
    return GremienBeschluss.objects.create(
        gremium=gremium,
        gegenstand=felder.pop("gegenstand", "Ob wir uns monatlich treffen"),
        optionen=felder.pop("optionen", OPTIONEN),
        angelegt_von=wer,
        **felder,
    )


def test_die_nummer_ist_zitierfaehig_und_zaehlt_je_gremium_und_jahr():
    """„IR-2026-04" muss man am Telefon sagen können — und wiederfinden."""
    assert beschlussnummer("integritaetsrat", 2026, 4) == "IR-2026-04"
    assert beschlussnummer("koordinationsrat", 2026, 12) == "KR-2026-12"
    erste = beschluss_anlegen()
    zweite = beschluss_anlegen()
    dritte = beschluss_anlegen(gremium=Gremium.INTEGRITAETSRAT)
    jahr = timezone.now().year
    assert erste.nummer == f"KR-{jahr}-01"
    assert zweite.nummer == f"KR-{jahr}-02"
    assert dritte.nummer == f"IR-{jahr}-01"  # je Gremium eine eigene Zählung


def test_die_nummer_bleibt_beim_speichern_stehen():
    """Sonst wanderte die Kennung unter einer Begründung weg, die sie zitiert."""
    b = beschluss_anlegen()
    nummer = b.nummer
    b.gegenstand = "Neuer Gegenstand"
    b.save()
    b.refresh_from_db()
    assert b.nummer == nummer


def test_ein_gast_sieht_die_beschluesse_mit_namen_und_begruendung(client):
    """§ 6 Abs 9 — ohne Anmeldung, denn wer in einem Rat sitzt, entscheidet über andere."""
    korat = mitglied_anlegen("koordinatorin")
    rolle_geben(korat, Gremium.KOORDINATIONSRAT)
    b = beschluss_anlegen(angelegt_von=korat, gegenstand="Ob wir die Sitzung verschieben")
    client.force_login(korat)
    client.post(
        reverse("gremien:beschluss_stimme", args=[b.pk]),
        {"option": "dafuer", "begruendung": "Der Termin kollidiert mit der Mitgliederversammlung."},
    )
    client.logout()
    inhalt = client.get(reverse("gremien:beschluesse")).content.decode()
    assert "Ob wir die Sitzung verschieben" in inhalt
    assert korat.anzeigename in inhalt
    assert "kollidiert mit der Mitgliederversammlung" in inhalt
    assert b.nummer in inhalt


def test_die_einzelseite_findet_ueber_die_nummer(client):
    b = beschluss_anlegen()
    antwort = client.get(reverse("gremien:beschluss", args=[b.nummer]))
    assert antwort.status_code == 200
    assert b.gegenstand in antwort.content.decode()
    assert client.get(reverse("gremien:beschluss", args=["KR-2026-99"])).status_code == 404


def test_ein_gast_kann_nicht_abstimmen(client):
    b = beschluss_anlegen()
    client.post(
        reverse("gremien:beschluss_stimme", args=[b.pk]), {"option": "dafuer", "begruendung": "x"}
    )
    assert b.stimmen.count() == 0


def test_die_liste_laesst_sich_nach_gremium_filtern(client):
    beschluss_anlegen(gremium=Gremium.KOORDINATIONSRAT, gegenstand="Sache des Koordinationsrats")
    beschluss_anlegen(gremium=Gremium.INTEGRITAETSRAT, gegenstand="Sache des Integritätsrats")
    inhalt = client.get(reverse("gremien:beschluesse"), {"gremium": "integritaetsrat"}).content.decode()
    assert "Sache des Integritätsrats" in inhalt and "Sache des Koordinationsrats" not in inhalt


def test_der_anlass_entscheidet_ueber_die_wirkung():
    """Ein Anlass ohne Eintrag in der Wirkungstabelle bewirkt nichts — und das ist der Normalfall.

    Die alte Bedingung verzweigte über Gremium und Fremdschlüssel; sie hätte beim zweiten Anlass
    desselben Rates schon nicht mehr getragen."""
    from gremien.models import WIRKUNGEN

    assert set(WIRKUNGEN) == {Anlass.PRUEFUNG}
    b = beschluss_anlegen(gremium=Gremium.KOORDINATIONSRAT, anlass=Anlass.INTERN)
    korat = mitglied_anlegen("rat")
    rolle_geben(korat, Gremium.KOORDINATIONSRAT)
    b.stimmen.create(mitglied=korat, option="dafuer", begruendung="Ja.")
    assert b.abschliessen() is True
    b.refresh_from_db()
    assert b.status == BeschlussStatus.ENTSCHIEDEN and b.ergebnis == "dafuer"


def test_ein_leeres_gremium_beschliesst_nichts():
    """Läuft die Rolle vor dem Fristende ab, entscheidet die Stimme nicht allein."""
    rat = mitglied_anlegen("scheidend")
    rolle = rolle_geben(rat, Gremium.KOORDINATIONSRAT)
    b = beschluss_anlegen(frist=timezone.now() + timedelta(days=1))
    b.stimmen.create(mitglied=rat, option="dafuer", begruendung="Noch im Amt.")
    rolle.endet_am = timezone.localdate() - timedelta(days=1)
    rolle.save(update_fields=["endet_am"])
    b.frist = timezone.now() - timedelta(minutes=1)
    b.save(update_fields=["frist"])
    assert b.abschliessen() is True
    b.refresh_from_db()
    assert b.status == BeschlussStatus.OHNE_ERGEBNIS and b.ergebnis == ""


def test_das_admin_setzt_keine_hervorhebung():
    """§ 5 Abs 10 lit b: „sie erfolgt niemals durch einen Algorithmus“ — und ebenso wenig durch
    einen Haken im Verwaltungswerkzeug. Aufmerksamkeit ist die härteste Währung der Plattform."""
    from verfahren.admin import AntragAdmin

    assert "hervorgehoben" in AntragAdmin.readonly_fields
    assert "hervorhebung_begruendung" in AntragAdmin.readonly_fields
