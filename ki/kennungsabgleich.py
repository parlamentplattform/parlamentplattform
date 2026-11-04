"""Lesende Kennungsnachlese ausschließlich aus der tatsächlichen damaligen Eingabe."""

import json

from faktenbasis.kontext import pruefen as quellen_pruefen
from ki.eingabevertrag import korrektur as korrekturvertrag
from ki.eingabevertrag import rechtsbezug as rechtsvertrag
from ki.kontext import pruefen as text_pruefen
from ki.models import Zweck
from plattform_core.kennungsabgleich import VERSION, abgleichen
from plattform_core.modellantwort import pruefen as form_pruefen


def fuer_lauf(lauf):
    """Keine Datenbank-/Netzabfrage und kein Rückgriff auf heutige Quellen.

    Nur bekannte öffentliche Promptfassungen mit genau rekonstruierbarer Eingabe;
    eine Prüfsumme allein beweist nicht, dass die Quelle dem Anbieter übergeben wurde.
    """
    basis = {"regel_fassung": VERSION, "rechtlich_verifiziert": False, "zuordnungen": []}
    if lauf.zweck not in {Zweck.RECHTSBEZUG, Zweck.KORREKTUR}:
        raise ValueError("Kein öffentlicher Rechtsbezug")
    if not lauf.erfolgreich or not form_pruefen(lauf.antwort)["gueltig"]:
        return {**basis, "zustand": "antwortformat"}
    k = lauf.kontext if isinstance(lauf.kontext, dict) else {}
    if not k.get("quellen"):
        return {**basis, "zustand": "alt"}
    try:
        t, q = text_pruefen(k.get("text")), quellen_pruefen(k["quellen"])
        if t["antrag"] != lauf.antrag_id or q["text_sha256"] != k["text"]["sha256"]:
            raise ValueError("Falsche Textbindung")
        nummer, ursprungseingabe = rechtsvertrag(k["text"], k["quellen"])
        if lauf.zweck == Zweck.RECHTSBEZUG:
            if lauf.auftrag_version != f"rechtsbezug-v{nummer}" or lauf.eingabe != ursprungseingabe:
                raise ValueError("Kein tatsächlicher Quellenwortlaut")
        else:
            from ki.korrekturkontext import pruefen as korrektur_pruefen

            d = korrektur_pruefen(k.get("korrektur"))
            korrnummer, erwartet = korrekturvertrag(k["korrektur"])
            if (lauf.auftrag_version != f"korrektur-v{korrnummer}" or lauf.eingabe != erwartet or d["eingabe"] != ursprungseingabe
                    or d["text"] != k["text"] or d["quellen"] != k["quellen"] or d["antrag"] != lauf.antrag_id):
                raise ValueError("Kein tatsächlicher Korrekturwortlaut")
        normen = json.loads(lauf.antwort)["normen"]
        zuordnungen = abgleichen(normen, q["quellen"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return {**basis, "zustand": "fehler"}
    return {**basis, "zustand": "geprueft", "text_sha256": k["text"]["sha256"],
            "quellen_sha256": k["quellen"]["sha256"], "zuordnungen": zuordnungen}


def ergaenzen(ergebnis, lauf):
    nachlese = fuer_lauf(lauf)
    ergebnis["kennungsabgleich"] = nachlese
    for n, zuordnung in zip(ergebnis["normen"], nachlese["zuordnungen"], strict=False):
        n["kennungsabgleich"] = zuordnung
    return ergebnis
