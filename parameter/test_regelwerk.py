"""Das Regelverzeichnis (§ 2 Abs 6) und sein Wächter.

Die Satzung verlangt vier Dinge von jeder automatisierten Sortierung oder Auswahl: offengelegt,
versioniert, nachrechenbar, mit Datum und Begründung dokumentiert. Diese Tests halten das
Verzeichnis dagegen — vor allem gegen den Ordner `plattform_core` selbst: Eine Regel, die dort
entsteht und hier fehlt, wäre eine unveröffentlichte Regel, und genau die verbietet der Absatz.
"""

from __future__ import annotations

import pathlib

import pytest
from django.urls import reverse

from plattform_core.regelwerk import (
    KEINE_REGEL,
    VERSION,
    Wirkung,
    als_dict,
    nach_wirkung,
    verzeichnis,
    zaehlung,
)

KERN = pathlib.Path(__file__).resolve().parent.parent / "plattform_core"


def test_kein_modul_bleibt_unverzeichnet():
    """Der Wächter: Jede Datei in plattform_core steht im Verzeichnis oder in der Ausnahmeliste.

    Stillschweigen ist die eine Möglichkeit, die es nicht gibt. Ein Modul, das reiht oder
    auswählt und nirgends verzeichnet ist, wäre eine unveröffentlichte Regel (§ 2 Abs 6)."""
    dateien = {
        p.name for p in KERN.glob("*.py") if not p.name.startswith("test_")
    }
    verzeichnet = {r.modul for r in verzeichnis()} | set(KEINE_REGEL)
    fehlend = sorted(dateien - verzeichnet)
    assert not fehlend, (
        "Diese Module stehen weder im Verzeichnis noch in KEINE_REGEL "
        f"(plattform_core/regelwerk.py): {fehlend}"
    )


def test_das_verzeichnis_nennt_keine_datei_die_es_nicht_gibt():
    dateien = {p.name for p in KERN.glob("*.py")}
    erfunden = sorted({r.modul for r in verzeichnis()} - dateien)
    assert not erfunden, f"Verzeichnet, aber nicht vorhanden: {erfunden}"


def test_jede_regel_traegt_datum_und_begruendung():
    """§ 2 Abs 6 wörtlich: „mit Datum und Begründung öffentlich zu dokumentieren"."""
    ohne = [
        f"{r.modul} ({'ohne Datum' if not r.seit else 'ohne Begründung'})"
        for r in verzeichnis()
        if not r.seit or not r.grund
    ]
    assert not ohne, "Ohne Datum oder Begründung:\n  " + "\n  ".join(ohne)


def test_was_reiht_oder_entscheidet_ist_versioniert():
    """„… nach offengelegten, versionierten und nachrechenbaren Regeln."

    Wer keine Fassung führt, kann keine Änderung daran dokumentieren — und eine Regel ohne
    dokumentierbare Änderung ist genau das, was der Absatz ausschließt."""
    ohne = [
        f"{r.modul} ({r.wirkung.value})"
        for r in verzeichnis()
        if r.wirkung.muss_versioniert_sein and r.fassung is None
    ]
    assert not ohne, "Reiht oder entscheidet, führt aber keine Fassung:\n  " + "\n  ".join(ohne)


def test_die_genannte_fassung_steht_wirklich_im_modul():
    """Eine Fassungsnummer, die nur im Verzeichnis steht, ist eine Behauptung."""
    falsch = []
    for r in verzeichnis():
        if r.fassung is None:
            continue
        quelle = (KERN / r.modul).read_text(encoding="utf-8")
        if f"VERSION = {r.fassung}" not in quelle:
            falsch.append(f"{r.modul}: Verzeichnis sagt {r.fassung}")
    assert not falsch, "Fassung stimmt nicht mit dem Modul überein:\n  " + "\n  ".join(falsch)


def test_jede_bindende_regel_sagt_wie_man_sie_nachrechnet():
    """Nachrechenbar ist die dritte Forderung des Absatzes — bei allem, was bindet, zwingend."""
    stumm = [
        r.modul
        for r in verzeichnis()
        if r.wirkung is Wirkung.ENTSCHEIDET and not r.nachrechenbar.strip()
    ]
    assert not stumm, f"Bindend, aber ohne Angabe zum Nachrechnen: {stumm}"


def test_die_ausnahmeliste_begruendet_jede_ausnahme():
    ohne = [modul for modul, grund in KEINE_REGEL.items() if not grund.strip()]
    assert not ohne, f"Ausnahme ohne Begründung: {ohne}"


def test_die_momentaufnahme_traegt_alles_was_die_pruefung_braucht():
    """Der Vermerk „geprüft am …" ist ohne die Liste, auf die er sich bezieht, wertlos."""
    daten = als_dict()
    assert len(daten) == len(verzeichnis())
    for zeile in daten:
        assert {"modul", "titel", "wirkung", "fassung", "seit", "grund"} <= set(zeile)


@pytest.mark.django_db
def test_die_seite_zeigt_alle_regeln_nach_wirkung(client):
    inhalt = client.get(reverse("parameter:regeln")).content.decode()
    for r in verzeichnis():
        assert r.titel in inhalt, f"Regel fehlt auf der Seite: {r.titel}"
    for wirkung, _regeln in nach_wirkung():
        assert wirkung.value in inhalt
    assert str(zaehlung()["regeln"]) in inhalt
    assert str(VERSION) in inhalt
