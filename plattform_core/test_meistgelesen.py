"""Reihung „Meistgelesene Anträge“ (Fahrtenbuch D-C7): die offengelegte Regel, nachgerechnet."""

from hypothesis import given, settings
from hypothesis import strategies as st

from plattform_core.meistgelesen import HOECHSTZAHL, REIHUNG, VERSION, meistgelesene


def test_die_regel_traegt_fassung_sortierung_und_hoechstzahl():
    assert VERSION == 1
    assert REIHUNG == ('-gesamt', 'antrag')
    assert HOECHSTZAHL == 5


def test_summe_ueber_alle_tage_absteigend_hoechstens_fuenf():
    tageszahlen = [(1, 3), (2, 10), (1, 4), (3, 1), (4, 6), (5, 2), (6, 9), (7, 5)]
    assert meistgelesene(tageszahlen) == [(2, 10), (6, 9), (1, 7), (4, 6), (7, 5)]


def test_ohne_gezaehlte_aufrufe_bleibt_die_liste_leer():
    assert meistgelesene([]) == []


def test_bei_gleicher_summe_steht_die_kleinere_antragsnummer_vorn():
    """GP-134: Gleichstände stehen in fester Reihenfolge, gleich in welcher Folge die Zahlen kommen."""
    assert meistgelesene([(3, 5), (1, 5), (2, 5)]) == [(1, 5), (2, 5), (3, 5)]
    assert meistgelesene([(9, 2), (4, 1), (2, 1), (4, 1), (7, 2)]) == [(4, 2), (7, 2), (9, 2), (2, 1)]


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
    assert ergebnis == sorted(ergebnis, key=lambda paar: (-paar[1], paar[0]))
    # Kein Antrag außerhalb der Liste hat mehr Aufrufe als der letzte in der Liste.
    if ergebnis:
        draussen = [s for a, s in summen.items() if a not in dict(ergebnis)]
        assert all(s <= werte[-1] for s in draussen)


def test_das_verzeichnis_nennt_die_reihenfolge_bei_gleichstand():
    """GP-134: Die festgeschriebene Reihenfolge steht im Verzeichnis, offene Fragen bleiben Lücke."""
    from plattform_core.regelwerk import REGELN

    (regel,) = [r for r in REGELN if r.modul == 'meistgelesen.py']
    assert 'bei gleicher Summe die kleinere Antragsnummer zuerst' in regel.nachrechenbar
    assert '21.11.2026' in regel.grund
    assert 'derselben Person' in regel.luecke and 'dann entscheidet die Datenbank' not in regel.luecke
