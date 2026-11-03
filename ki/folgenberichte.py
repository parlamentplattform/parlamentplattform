"""Vollständige qualitative Berichte lesen; Form und Quellenidentität trennen."""

from django.utils.translation import gettext_lazy as _

from ki import folgenkontext
from ki.models import Zweck
from plattform_core.kennungsabgleich import VERSION as ABGLEICHFASSUNG
from plattform_core.kennungsabgleich import abgleichen
from plattform_core.rechtsfolgen import pruefen as form_pruefen


def vertrag(lauf):
    """Tatsächlichen ursprünglichen oder korrigierten Input prüfen, ohne Datenbank."""
    if lauf.zweck == Zweck.RECHTSFOLGEN:
        from ki.folgenauftraege import antwort_pruefen

        return antwort_pruefen(lauf)
    from ki.eingabevertrag import korrektur
    from ki.folgenkorrekturkontext import pruefen

    k = lauf.kontext if isinstance(lauf.kontext, dict) else {}
    d = pruefen(k.get("korrektur"))
    nummer, eingabe = korrektur(k["korrektur"])
    if (lauf.zweck != Zweck.KORREKTUR or not lauf.erfolgreich or nummer != 3
            or set(k) != {"text", "quellen", "folgen", "korrektur", "auftrag", "versuch"}
            or type(k.get("auftrag")) is not int or k["auftrag"] < 1
            or type(k.get("versuch")) is not int or k["versuch"] < 1
            or lauf.auftrag_version != "korrektur-v3" or lauf.eingabe != eingabe
            or d["antrag"] != lauf.antrag_id or k.get("folgen") != d["folgen"]
            or k.get("text") != d["text"] or k.get("quellen") != d["quellen"]):
        raise ValueError("Keine eindeutig gebundene Folgen-Nachrechnung.")
    return form_pruefen(lauf.antwort, **folgenkontext.antwortangebot(d["folgen"]))


def fuer_lauf(lauf):
    from ki.rechtsbezug import AENDERUNGEN, UNSICHERHEITEN

    if not lauf.erfolgreich and lauf.zweck == Zweck.RECHTSFOLGEN:
        from ki.folgenauftraege import grundlage_pruefen

        grundlage_pruefen(lauf)
        form = None
    else:
        form = vertrag(lauf)
    rahmen = lauf.kontext["folgen"]
    d = folgenkontext.pruefen(rahmen)
    ergebnis = {"folgenbericht": True, "formatpruefung": form, "normen": [], "personal": [],
                "judikatur": "", "exekutive": "", "hinweis": "", "unsicherheit": "unbekannt",
                "unsicherheit_wort": UNSICHERHEITEN["unbekannt"], "quellen": [], "personalfolgen": "nicht_bestimmbar",
                "kennungsabgleich": {"regel_fassung": ABGLEICHFASSUNG, "rechtlich_verifiziert": False,
                                     "zustand": "antwortformat", "zuordnungen": []},
                "text_sha256": d["text"]["sha256"], "folgen_sha256": rahmen["sha256"]}
    ergebnis["personalstand"] = d["personal"]
    if form is None or not form["gueltig"]:
        return ergebnis  # keine gut aussehende Teilantwort aus fehlerhaftem JSON
    daten = form["daten"]
    quellen = d["quellen"]["quellen"]
    # Die neue Antwort behauptet keine Herkunftsebene. Diese darf nur aus exakt
    # derselben angebotenen vollständigen Dokumentkennung stammen, nie aus Titeln.
    normen = []
    for index in form["darstellungsfolge"]["normen"]:
        n = daten["normen"][index]
        ebenen = {q.get("ebene", "Bund") for q in quellen if q["ris_id"] == n["ris_id"]}
        normen.append({**n, "kennung": n["ris_id"], "begruendung": n["grund"], "verifiziert": False,
                       "ebene": next(iter(ebenen)) if len(ebenen) == 1 else "",
                       "aenderung_wort": AENDERUNGEN[n["aenderung"]]})
    abgleich = abgleichen(normen, quellen)
    for n, z in zip(normen, abgleich, strict=True):
        n["kennungsabgleich"] = z
    personal = [daten["personal"][i] for i in form["darstellungsfolge"]["personal"]]
    return {**ergebnis, "normen": normen, "judikatur": daten["judikatur"]["text"],
            "exekutive": daten["exekutive"]["text"],
            "personal": [{**p, "bereich_wort": _("unbestimmt") if p["bereich"] == "unbestimmt" else p["bereich"]}
                         for p in personal],
            "quellen": daten["quellen"], "unsicherheit": daten["unsicherheit"],
            "unsicherheit_wort": UNSICHERHEITEN[daten["unsicherheit"]],
            "kennungsabgleich": {"regel_fassung": ABGLEICHFASSUNG, "rechtlich_verifiziert": False,
                                 "zustand": "geprueft", "zuordnungen": abgleich}}
