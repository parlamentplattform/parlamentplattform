"""Reihung „Meistgelesene Anträge“ (Fahrtenbuch D-C7): die offengelegte Regel, nachgerechnet."""

from hypothesis import given, settings
from hypothesis import strategies as st

from plattform_core.meistgelesen import HOECHSTZAHL, REIHUNG, VERSION, meistgelesene


def test_die_regel_traegt_fassung_sortierung_und_hoechstzahl():
    assert VERSION == 1
    assert REIHUNG == ('-gesamt',)
    assert HOECHSTZAHL == 5


def test_summe_ueber_alle_tage_absteigend_hoechstens_fuenf():
    tageszahlen = [(1, 3), (2, 10), (1, 4), (3, 1), (4, 6), (5, 2), (6, 9), (7, 5)]
    assert meistgelesene(tageszahlen) == [(2, 10), (6, 9), (1, 7), (4, 6), (7, 5)]


def test_ohne_gezaehlte_aufrufe_bleibt_die_liste_leer():
    assert meistgelesene([]) == []


def test_bei_gleicher_summe_legt_die_regel_keine_reihenfolge_fest():
    """Offen benannte Lücke: Gleichstände ordnet die Regel nicht; die Summen stimmen trotzdem."""
    ergebnis = meistgelesene([(1, 5), (2, 5), (3, 5)])
    assert sorted(ergebnis) == [(1, 5), (2, 5), (3, 5)]


@settings(deadline=None)  # unabhängig von der Rechnergeschwindigkeit
@given(st.lists(st.tuples(st.integers(1, 12), st.integers(0, 500)), max_size=60))
def test_eigenschaft_summen_stimmen_und_die_liste_faellt(tageszahlen):
    summen: dict[int, int] = {}
    for antrag, aufrufe in tageszahlen:
        summen[antrag] = summen.get(antrag, 0) + aufrufe
    ergebnis = meistgelesene(tageszahlen)
    assert len(ergebnis) == min(HOECHSTZAHL, len(summen))
    assert all(summen[antrag] == summe for antrag, summe in ergebnis)
    werte = [summe for _antrag, summe in ergebnis]
    assert werte == sorted(werte, reverse=True)
    # Kein Antrag außerhalb der Liste hat mehr Aufrufe als der letzte in der Liste.
    if ergebnis:
        draussen = [s for a, s in summen.items() if a not in dict(ergebnis)]
        assert all(s <= werte[-1] for s in draussen)
