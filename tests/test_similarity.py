"""Ähnlichkeitshinweis (ADR-006, ADR-011, F-35): Stufe 1b lexikalisch auf Wort-Ebene — deterministisch,
nachrechenbar. Die Tiefe (Gründer-Beispiele, Hypothesis, Kosinus) steht in plattform_core/test_similarity.py."""

from plattform_core.similarity import aehnlichkeit, aehnlichste, normalisieren, stammform, woerter


def test_normalisieren_entfernt_satzzeichen_und_grossschreibung():
    assert normalisieren("Öffentliche  Sitzungs-Protokolle!") == "öffentliche sitzungs protokolle"


def test_identische_texte_haben_aehnlichkeit_eins():
    t = "Sitzungsprotokolle binnen 48 Stunden veröffentlichen"
    assert aehnlichkeit(t, t) == 1.0


def test_voellig_verschiedene_texte_bleiben_unter_der_schwelle():
    assert aehnlichkeit("Radwege in jeder Gemeinde ausbauen", "Wasserzähler quartalsweise ablesen") < 0.30


def test_leere_texte_ergeben_null():
    assert aehnlichkeit("", "irgendwas") == 0.0
    assert aehnlichkeit("...", "irgendwas") == 0.0  # nur Satzzeichen
    assert aehnlichkeit("die der das", "irgendwas") == 0.0  # nur Stoppwörter


def test_woerter_streichen_floskeln_und_kuerzen_auf_die_stammform():
    text = "Die Bundesregierung wird aufgefordert, Protokolle aller Sitzungen zu veröffentlichen."
    assert woerter(text) == ["protokoll", "sitzung", "veröffentlich"]
    assert stammform("Ort") == "Ort"  # unter fünf Zeichen bleibt alles
    assert stammform("radwege") == "radweg"


def test_aehnlichste_sortiert_absteigend_und_bricht_gleichstand_per_id():
    text = "Protokolle aller Sitzungen veröffentlichen"
    kandidaten = [
        (7, "Protokolle aller Sitzungen veröffentlichen"),  # identisch
        (3, "Protokolle aller Sitzungen veröffentlichen"),  # identisch, kleinere ID
        (9, "Radwege ausbauen und Bäume pflanzen"),  # unähnlich
    ]
    treffer = aehnlichste(text, kandidaten)
    assert [kid for kid, _ in treffer] == [3, 7]  # gleicher Score -> kleinere ID zuerst
    assert all(score == 1.0 for _, score in treffer)


def test_aehnlichste_respektiert_limit_und_schwelle():
    text = "Öffentliche Verkehrsmittel im Ort takten"
    kandidaten = [(i, f"Öffentliche Verkehrsmittel im Ort takten, Variante {i}") for i in range(10)]
    treffer = aehnlichste(text, kandidaten, limit=3)
    assert len(treffer) == 3
    assert aehnlichste("", kandidaten) == []
    assert aehnlichste(text, [(1, "")]) == []
