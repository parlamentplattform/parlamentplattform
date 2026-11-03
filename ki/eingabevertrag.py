"""Bekannte öffentliche Promptfassungen an ihre tatsächliche Eingabe binden.

Keine Datenbank oder aktuellen Quellen lesen. Historische Quellenfassung1 bleibt
mit ihrem damaligen Prompt und Wortlaut erhalten; neue Herkunft2 bekommt eine
eigene Promptfassung, keine still untergeschobene Änderung alter Aufträge.
"""

import json

from faktenbasis.kontext import eingabe as quellen_eingabe
from faktenbasis.kontext import pruefen as quellen_pruefen
from ki.kontext import eingabe as text_eingabe

VERSION = 1


def rechtsbezug(text, quellen):
    eingabe = text_eingabe(text)
    if not isinstance(quellen, dict):
        raise ValueError("Kein gültiger Quellenvertrag.")
    if not quellen:
        return 1, eingabe
    daten = quellen_pruefen(quellen)
    nummer = {1: 2, 2: 3}[daten["version"]]
    return nummer, eingabe + "\n\n" + quellen_eingabe(quellen, text_sha256=text["sha256"])


def korrektur(rahmen):
    from ki.korrekturkontext import pruefen

    d = pruefen(rahmen)
    ursprung, originaleingabe = rechtsbezug(d["text"], d["quellen"])
    if d["eingabe"] != originaleingabe:
        raise ValueError("Die ursprüngliche öffentliche Eingabe ist nicht eindeutig belegt.")
    nummer = 2 if ursprung == 3 else 1
    return nummer, json.dumps({"urspruengliche_eingabe": d["eingabe"], "urspruengliche_antwort": d["antwort"],
        "beanstandung": d["beanstandung"]["text"]}, ensure_ascii=False, sort_keys=True)
