"""D-D2 (b) als schlafender Schalter (0.51.0): Voreinstellung verdeckt bis Fristende — nur wo die eingefrorene
Ordnung eines Sachantrags es ab erreichter Mindestbeteiligung freigibt, zeigen Kachel, Antragsseite und
Übersicht die Tendenz. Mandatsfrage, Vertrauensfrage und Kandidatur nie; § 5 Abs 5: der Schalter gilt nur
für Anträge, die danach eingebracht werden."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from verfahren.models import Stimmabgabe, Verfahrensordnung, antrag_einbringen, stimme_abgeben
from verfahren.test_mandatsfrage import eroeffnen, mandat_mit_report
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    REGELN,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

VERDECKT = "Tendenz verdeckt bis Fristende"
BIS_MINDEST = "Tendenz verdeckt bis zur Mindestbeteiligung"


@pytest.fixture
def offen_ordnung():
    """Eine Ordnung mit dem Schalter 1 — so wie sie nach einem Beschluss der Mitgliederversammlung aussähe."""
    return Verfahrensordnung.objects.create(
        policy_id="offen", version=1, regeln={**REGELN, "id": "offen", "tendenz_ab_mindestbeteiligung": 1}, aktiv=True
    )


_N = iter(range(10_000))


def _abstimmung(ordnung, stimmen=(), waehler=40):  # noqa: F811
    """Ein Sachantrag in der Abstimmung mit `waehler` Stimmberechtigten und den angegebenen Stimmen."""
    leute = [mitglied_anlegen(f"w{next(_N)}") for _ in range(waehler)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    in_abstimmung_bringen(antrag, leute[1:3])
    antrag.refresh_from_db()
    for m, s in zip(leute, stimmen, strict=False):
        stimme_abgeben(antrag, m, s)
    return antrag


def _parlament(client):
    return client.get(reverse("verfahren:parlament")).content.decode()


def test_voreinstellung_null_zeigt_nie_die_tendenz(client, ordnung):  # noqa: F811
    antrag = _abstimmung(ordnung, ["ja", "ja", "nein", "ja"])
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert VERDECKT in seite and "Tendenz: " not in seite
    uebersicht = client.get(reverse("uebersicht:index")).content.decode()
    assert VERDECKT in uebersicht and "Tendenz: " not in uebersicht


def test_eins_unter_der_mindestbeteiligung_bleibt_verdeckt(client, offen_ordnung):
    antrag = _abstimmung(offen_ordnung, ["ja"], waehler=40)  # 1 von ≥ 40 < 5 %
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert BIS_MINDEST in seite and "Tendenz: " not in seite


def test_eins_ab_erreichter_mindestbeteiligung_zeigt_die_anteile_ueberall_gleich(client, offen_ordnung):
    antrag = _abstimmung(offen_ordnung, ["ja", "ja", "nein", "enthaltung"], waehler=40)
    erwartet = "Tendenz: 50 % Ja · 25 % Nein · 25 % Enthaltung"
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert erwartet in seite  # ohne JavaScript im HTML
    assert erwartet in client.get(reverse("uebersicht:index")).content.decode()
    from django.utils import timezone

    from verfahren.views import _kachel

    kachel = _kachel(antrag, timezone.now())
    assert kachel["stat"]["tendenz"]["ja"]["prozent"] == 50
    # Die Stimmliste bleibt bis zum Ende verschlossen (§ 5 Abs 3 lit e) — nur die Anteile sind offen.
    assert client.get(reverse("verfahren:export", args=[antrag.pk])).status_code == 409


def test_ein_laufender_antrag_behaelt_seinen_schalter(client, ordnung, offen_ordnung):  # noqa: F811
    """§ 5 Abs 5: Tritt eine Ordnung mit 1 in Kraft, bleibt ein schon eingebrachter Antrag verdeckt."""
    alt = _abstimmung(ordnung, ["ja", "ja", "nein", "ja"])
    Verfahrensordnung.objects.filter(pk=ordnung.pk).update(regeln={**REGELN, "tendenz_ab_mindestbeteiligung": 1})
    alt.refresh_from_db()
    assert alt.policy().tendenz_ab_mindestbeteiligung == 0
    seite = client.get(reverse("verfahren:antrag", args=[alt.pk])).content.decode()
    assert VERDECKT in seite and "Tendenz: " not in seite


def test_mandatsfrage_friert_null_ein_auch_unter_einer_offenen_ordnung(client, offen_ordnung):
    """FB-L5: „D-D2 gilt auch hier: keine Tendenz vor Fristende.“"""
    leute = [mitglied_anlegen(f"mf{i}") for i in range(3)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    antrag = eroeffnen(mandat, aufgabe, offen_ordnung)
    assert antrag.policy().tendenz_ab_mindestbeteiligung == 0
    for m in leute:
        stimme_abgeben(antrag, m, "ja")
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Tendenz: " not in seite


def test_die_uebersicht_fragt_unabhaengig_von_der_zahl_offener_tendenzen(client, offen_ordnung):
    leute = [mitglied_anlegen(f"pool{i}") for i in range(20)]

    def offen():
        antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=offen_ordnung)
        in_abstimmung_bringen(antrag, leute[1:3])
        antrag.refresh_from_db()
        for m in leute[:10]:  # die Hälfte stimmt — die Mindestbeteiligung ist erreicht
            stimme_abgeben(antrag, m, "ja")
        return antrag

    offen()
    with CaptureQueriesContext(connection) as eine:
        client.get(reverse("uebersicht:index"))
    for _ in range(3):
        offen()
    with CaptureQueriesContext(connection) as vier:
        inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert inhalt.count("Tendenz: 100 % Ja") == 4
    assert len(vier) == len(eine), (len(eine), len(vier))
    assert Stimmabgabe.objects.count() == 40


def test_die_regelliste_nennt_den_schalter(ordnung, offen_ordnung):  # noqa: F811
    from verfahren.views import _regeln_lesbar

    zu = _abstimmung(ordnung)
    auf = _abstimmung(offen_ordnung)
    assert dict(_regeln_lesbar(zu.policy()))["Tendenz während der Abstimmung"] == "verdeckt bis Fristende"
    assert dict(_regeln_lesbar(auf.policy()))["Tendenz während der Abstimmung"] == "sichtbar ab erreichter Mindestbeteiligung"
    assert "Tendenz während der Abstimmung" not in dict(_regeln_lesbar(auf.policy(), "mandat"))
