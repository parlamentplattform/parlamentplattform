"""Ähnlichkeitshinweis (ADR-006, F-35): rein lexikalisch, deterministisch, nachrechenbar."""

from plattform_core.similarity import aehnlichkeit, aehnlichste, normalisieren, trigramme


def test_normalisieren_entfernt_satzzeichen_und_grossschreibung():
    assert normalisieren("Öffentliche  Sitzungs-Protokolle!") == "öffentliche sitzungs protokolle"


def test_identische_texte_haben_aehnlichkeit_eins():
    t = "Sitzungsprotokolle binnen 48 Stunden veröffentlichen"
    assert aehnlichkeit(t, t) == 1.0


def test_voellig_verschiedene_texte_bleiben_unter_der_schwelle():
    assert aehnlichkeit("Radwege in jeder Gemeinde ausbauen", "Wasserzähler quartalsweise ablesen") < 0.18


def test_leere_texte_ergeben_null():
    assert aehnlichkeit("", "irgendwas") == 0.0
    assert aehnlichkeit("...", "irgendwas") == 0.0  # nur Satzzeichen


def test_trigramme_polstern_kurze_woerter():
    # Auch Ein-Buchstaben-Wörter erzeugen Trigramme und fallen nicht unter den Tisch.
    assert trigramme("a") != set()


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
