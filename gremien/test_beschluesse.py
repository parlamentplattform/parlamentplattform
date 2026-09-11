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


def test_bei_vergebener_nummer_wird_neu_gezaehlt(monkeypatch):
    """Befund #72: `select_for_update().count()` sperrte nichts — zwei Worker zählten dieselbe
    Zahl, und der zweite scheiterte mit HTTP 500. Das Wettrennen im Zeitraffer: Zwischen Zählen
    und Schreiben schiebt ein Konkurrent dieselbe Nummer ein; `save` bekommt den IntegrityError,
    zählt neu und vergibt die nächste."""
    import gremien.models as gm

    erste = beschluss_anlegen()
    echte = gm.beschlussnummer
    vergeben = []

    def ueberholt(gremium, jahr, laufend):
        nummer = echte(gremium, jahr, laufend)
        vergeben.append(nummer)
        if len(vergeben) == 1:
            GremienBeschluss.objects.create(
                gremium=gremium, gegenstand="Konkurrent", optionen=OPTIONEN, angelegt_von=erste.angelegt_von, nummer=nummer
            )
        return nummer

    monkeypatch.setattr(gm, "beschlussnummer", ueberholt)
    dritter = beschluss_anlegen()
    assert vergeben == [erste.nummer[:-2] + "02", erste.nummer[:-2] + "03"]
    assert dritter.nummer == vergeben[1]
    assert GremienBeschluss.objects.filter(nummer=vergeben[0]).count() == 1
    assert GremienBeschluss.objects.count() == 3


def test_die_nummer_traegt_das_wiener_jahr():
    """Befund #73/#76: Am 1. Jänner um 00:40 MEZ ist es in UTC noch der 31. Dezember — die Nummer
    nannte das alte Jahr, die Begründung am Antrag das neue."""
    from datetime import UTC, datetime

    beschluss = beschluss_anlegen(angelegt_am=datetime(2026, 12, 31, 23, 40, tzinfo=UTC))
    assert beschluss.nummer == "KR-2027-01"


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


def test_die_beschlussliste_rechnet_das_quorum_einmal_je_seite(client):
    """Befund #77: Je Beschluss mit Antrag drei Abfragen (Antrag, EXISTS, COUNT) — linear zum
    Registerwert der Seitengröße, für Gäste. Jetzt ein Nenner-Wörterbuch je Seite; die Regel
    (gelost vorhanden → deren Personen, sonst parteiweite) bleibt dieselbe."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from gremien.models import Rolle, quoren_fuer, standard_ende
    from verfahren.models import Verfahrensordnung, antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG, REGELN

    ordnung_ = Verfahrensordnung.objects.create(policy_id="t", version=1, regeln=REGELN, aktiv=True)
    parteiweit = [mitglied_anlegen(f"pw{next(_ZAEHLER)}") for _ in range(2)]
    for m in parteiweit:
        rolle_geben(m, Gremium.EXPERTENRAT_1)

    def mit_antrag():
        antrag = antrag_einbringen(mitglied_anlegen(f"st{next(_ZAEHLER)}"), **ANTRAG, ordnung=ordnung_)
        gelost = mitglied_anlegen(f"gl{next(_ZAEHLER)}")
        Rolle.objects.create(mitglied=gelost, gremium=Gremium.EXPERTENRAT_1, endet_am=standard_ende(), antrag=antrag)
        Rolle.objects.create(mitglied=gelost, gremium=Gremium.EXPERTENRAT_1, endet_am=standard_ende(), antrag=antrag)
        return beschluss_anlegen(Gremium.EXPERTENRAT_1, antrag=antrag, angelegt_von=gelost)

    erster = mit_antrag()
    ohne = beschluss_anlegen(Gremium.EXPERTENRAT_1)
    with CaptureQueriesContext(connection) as klein:
        assert client.get(reverse("gremien:beschluesse")).status_code == 200
    weitere = [mit_antrag() for _ in range(6)]
    with CaptureQueriesContext(connection) as gross:
        antwort = client.get(reverse("gremien:beschluesse"))
    assert len(gross) == len(klein), f"{len(klein)} → {len(gross)} Abfragen"
    quoren = quoren_fuer([erster, ohne, *weitere])
    assert quoren[erster.pk] == 1 == erster.aktive_rollen(), "gelost: eine Person, auch mit zwei Zeilen"
    assert quoren[ohne.pk] == 9 == ohne.aktive_rollen(), "ohne Antrag: alle Personen des Gremiums (2 + 7)"
    Rolle.objects.filter(antrag=erster.antrag).update(beendet_grund="Austausch")
    assert quoren_fuer([erster])[erster.pk] == 2 == erster.aktive_rollen(), "ohne Geloste: die parteiweiten"
    zeilen = {z["beschluss"].pk: z["auswertung"] for z in antwort.context["beschluesse"]}
    assert zeilen[erster.pk].noetig == erster.auswertung().noetig


def test_der_anlass_entscheidet_ueber_die_wirkung():
    """Ein Anlass ohne Eintrag in der Wirkungstabelle bewirkt nichts — und das ist der Normalfall.

    Die alte Bedingung verzweigte über Gremium und Fremdschlüssel; sie hätte beim zweiten Anlass
    desselben Rates schon nicht mehr getragen."""
    from gremien.models import WIRKUNGEN

    # Jeder Anlass mit Wirkung steht hier; jeder ohne bewirkt nichts außer sich selbst.
    # Seit 0.45 hat jeder Anlass außer INTERN eine Wirkung — ein Anlass, den man wählen
    # kann und der schweigend nichts tut, wäre ein Knopf ohne Draht.
    assert set(WIRKUNGEN) == set(Anlass) - {Anlass.INTERN}
    assert set(WIRKUNGEN) >= {
        Anlass.PRUEFUNG,
        Anlass.HERVORHEBUNG,
        Anlass.HERVORHEBUNG_AUFHEBEN,
        Anlass.ZURUECKWEISUNG,
        Anlass.ZURUECKWEISUNG_AUFHEBEN,
        Anlass.AUSSETZUNG,
        Anlass.AUSSETZUNG_AUFHEBEN,
        Anlass.REGELPRUEFUNG,
    }
    assert Anlass.INTERN not in WIRKUNGEN
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
