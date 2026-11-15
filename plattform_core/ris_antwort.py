"""Strukturzugriff für eine einzelne Dokumentreferenz der RIS-OGD-Antwort."""


def objekt(daten, feld):
    wert = daten.get(feld)
    return wert if isinstance(wert, dict) else {}


def einzelmetadaten(antwort):
    if not isinstance(antwort, dict):
        return {}
    ergebnis = objekt(objekt(antwort, "OgdSearchResult"), "OgdDocumentResults")
    referenz = ergebnis.get("OgdDocumentReference")
    if isinstance(referenz, list) and len(referenz) == 1:
        referenz = referenz[0]
    if not isinstance(referenz, dict):
        return {}
    return objekt(objekt(referenz, "Data"), "Metadaten")
