"""Audit-Hash-Kette: Jede Manipulation muss auffallen."""

from hypothesis import given
from hypothesis import strategies as st

from plattform_core import GENESIS, ereignis_hash, kette_pruefen

EREIGNIS = st.dictionaries(
    keys=st.sampled_from(["typ", "antrag", "wert", "zeit", "akteur"]),
    values=st.one_of(st.text(max_size=30), st.integers(-10**6, 10**6), st.booleans()),
    min_size=1, max_size=5,
)


def kette_bauen(ereignisse):
    eintraege, aktuell = [], GENESIS
    for e in ereignisse:
        aktuell = ereignis_hash(aktuell, e)
        eintraege.append((e, aktuell))
    return eintraege


def test_leere_kette_ist_gueltig():
    assert kette_pruefen([]) == (True, None)


def test_beispielkette_ist_gueltig():
    kette = kette_bauen([{"typ": "antrag_eingebracht", "antrag": 1}, {"typ": "stimme", "antrag": 1}])
    assert kette_pruefen(kette) == (True, None)


@given(st.lists(EREIGNIS, min_size=1, max_size=12))
def test_eigenschaft_intakte_ketten_werden_akzeptiert(ereignisse):
    assert kette_pruefen(kette_bauen(ereignisse)) == (True, None)


@given(st.lists(EREIGNIS, min_size=1, max_size=12), st.data())
def test_eigenschaft_jede_inhaltsaenderung_wird_erkannt(ereignisse, data):
    """Wird irgendein Ereignis nachträglich verändert, meldet die Prüfung
    genau diesen Index (oder einen früheren, nie einen späteren)."""
    kette = kette_bauen(ereignisse)
    index = data.draw(st.integers(0, len(kette) - 1))
    ereignis, gespeichert = kette[index]
    manipuliert = dict(ereignis)
    manipuliert["typ"] = str(manipuliert.get("typ", "")) + "_MANIPULIERT"
    kette[index] = (manipuliert, gespeichert)
    ok, fehler_index = kette_pruefen(kette)
    assert not ok
    assert fehler_index == index


def test_kanonisierung_ist_reihenfolgeunabhaengig():
    a = ereignis_hash(GENESIS, {"a": 1, "b": 2})
    b = ereignis_hash(GENESIS, {"b": 2, "a": 1})
    assert a == b
