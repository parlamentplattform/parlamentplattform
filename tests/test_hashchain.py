"""Audit-Hash-Kette: Jede Manipulation muss auffallen."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core import GENESIS, ereignis_hash, kette_pruefen

EREIGNIS = st.dictionaries(
    keys=st.sampled_from(["typ", "antrag", "wert", "zeit", "akteur"]),
    values=st.one_of(st.text(max_size=30), st.integers(-(10**6), 10**6), st.booleans()),
    min_size=1,
    max_size=5,
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


def test_vorgaenger_zuordnung_folgt_der_kette():
    """Befund #9: Die Spalte `vorgaenger` wird aus der bestehenden Kette gefüllt — der erste
    Eintrag hängt am Startwert, jeder weitere am Hash seines Vorgängers."""
    from plattform_core.hashchain import vorgaenger_zuordnen

    kette = kette_bauen([{"typ": "a"}, {"typ": "b"}, {"typ": "c"}])
    hashes = [h for _e, h in kette]
    assert vorgaenger_zuordnen(hashes) == [GENESIS, hashes[0], hashes[1]]
    assert vorgaenger_zuordnen([]) == []


def test_eine_gegabelte_kette_wird_gemeldet_statt_kaschiert():
    from plattform_core.hashchain import KettenFehler, vorgaenger_zuordnen

    with pytest.raises(KettenFehler):
        vorgaenger_zuordnen(["h1", "h1", "h2"])  # zwei Einträge mit identischem Hash → zwei am selben Kopf


def test_die_offenlegung_verspricht_keine_veroeffentlichung_die_es_nicht_gibt():
    """Befund #57: Die Modul-Docstring — auf /regeln/ als Offenlegung nach § 2 Abs 6 verzeichnet —
    stützte die Manipulationserkennung auf einen „täglich veröffentlichten Kettenkopf“, den
    kein Codepfad erzeugt. Öffentliche Texte sagen, was der Code tut."""
    from plattform_core import hashchain

    text = hashchain.__doc__
    assert "täglich" not in text and "veröffentlichte Kettenkopf" not in text
    assert "geplant" in text and "noch nicht gebaut" in text


def test_kanonisierung_ist_reihenfolgeunabhaengig():
    a = ereignis_hash(GENESIS, {"a": 1, "b": 2})
    b = ereignis_hash(GENESIS, {"b": 2, "a": 1})
    assert a == b


# --- kette_nachrechnen (Schritt 2 · 0.52.0): mit Vorgänger-Spalte, Nummern und Fortsetzung ------------


def kette_mit_nummern(ereignisse, start=GENESIS, ab=1):
    zeilen, kopf = [], start
    for i, e in enumerate(ereignisse, start=ab):
        h = ereignis_hash(kopf, e)
        zeilen.append((i, e, kopf, h))
        kopf = h
    return zeilen


def test_leere_kette_ist_intakt():
    from plattform_core.hashchain import kette_nachrechnen

    befund = kette_nachrechnen([])
    assert befund.intakt and befund.geprueft == 0 and befund.kopf == GENESIS and befund.bruch is None


@given(st.lists(EREIGNIS, min_size=1, max_size=12))
def test_jede_unveraenderte_kette_ist_intakt_und_endet_am_kopf(ereignisse):
    from plattform_core.hashchain import kette_nachrechnen

    zeilen = kette_mit_nummern(ereignisse)
    befund = kette_nachrechnen(zeilen)
    assert befund.intakt and befund.geprueft == len(zeilen)
    assert befund.kopf == zeilen[-1][3] and befund.letzte_nummer == zeilen[-1][0]


@given(st.lists(EREIGNIS, min_size=2, max_size=12), st.data())
def test_ein_veraenderter_inhalt_wird_mit_seiner_nummer_gemeldet(ereignisse, daten):
    from plattform_core.hashchain import kette_nachrechnen

    zeilen = kette_mit_nummern(ereignisse)
    i = daten.draw(st.integers(0, len(zeilen) - 1))
    nummer, e, vorg, h = zeilen[i]
    zeilen[i] = (nummer, {**e, "manipuliert": True}, vorg, h)
    befund = kette_nachrechnen(zeilen)
    assert not befund.intakt and befund.bruch == nummer and befund.grund == "hash"
    assert befund.geprueft == i


def test_ein_entfernter_eintrag_bricht_am_vorgaenger():
    from plattform_core.hashchain import kette_nachrechnen

    zeilen = kette_mit_nummern([{"typ": "a"}, {"typ": "b"}, {"typ": "c"}])
    befund = kette_nachrechnen([zeilen[0], zeilen[2]])
    assert not befund.intakt and befund.bruch == 3 and befund.grund == "vorgaenger"
    assert befund.kopf == zeilen[0][3] and befund.letzte_nummer == 1


def test_die_pruefung_setzt_an_einem_stand_fort():
    from plattform_core.hashchain import kette_nachrechnen

    zeilen = kette_mit_nummern([{"typ": "a"}, {"typ": "b"}, {"typ": "c"}])
    erster = kette_nachrechnen(zeilen[:2])
    weiter = kette_nachrechnen(zeilen[2:], start_hash=erster.kopf, start_nummer=erster.letzte_nummer)
    assert weiter.intakt and weiter.geprueft == 1 and weiter.kopf == zeilen[2][3]
    leer = kette_nachrechnen([], start_hash=erster.kopf, start_nummer=2)
    assert leer.intakt and leer.letzte_nummer == 2 and leer.kopf == erster.kopf
