"""Öffentliches Audit, erste Behebungsrunde nach der Gesamtprüfung (0.113.0).

GP-011: Die Begründung einer Rückgabe durch Gruppe 2 nennt die Prüfenden mit Namen — öffentlich geschwärzt.
GP-210: Während der Abstimmung trägt ein Stimm-Ereignis öffentlich nur das Tagesdatum.
GP-158: Angezeigt wird die versiegelte Zeit; eine Abweichung der Spalte meldet die Prüfung."""

import pytest

from verfahren.audit_oeffentlich import MASKE, ereignis_oeffentlich

pytestmark = pytest.mark.django_db


# --- GP-011 ---------------------------------------------------------------------------------------


def test_die_rueckgabe_durch_gruppe_2_nennt_oeffentlich_keinen_pruefenden():
    alt = {
        'typ': 'vorschlag_zurueckgegeben',
        'antrag': 7,
        'runde': 2,
        'grund': 'Gruppe 2: Petra Probekind: mit Begründung zurückgeben — Die Kriterien fehlen.',
    }
    oeffentlich, geschwaerzt = ereignis_oeffentlich(alt)
    assert geschwaerzt
    assert oeffentlich['grund'] == MASKE
    assert 'Probekind' not in str(oeffentlich)


def test_die_rueckgabe_aus_dem_abstimmungs_chat_bleibt_lesbar():
    rechnung = {
        'typ': 'vorschlag_zurueckgegeben',
        'antrag': 7,
        'runde': 2,
        'grund': 'Der Abstimmungs-Chat gibt zurück: 3 von 10 (30 %, Schwelle 50 %).',
    }
    oeffentlich, geschwaerzt = ereignis_oeffentlich(rechnung)
    assert not geschwaerzt
    assert oeffentlich['grund'] == rechnung['grund']
