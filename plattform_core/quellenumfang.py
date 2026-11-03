"""Technische Herkunftsgrenze von Kontextkandidaten, keine Zuständigkeitsprüfung.

Die Auswahl umfasst vorhandene Bundes- und Landesquellen. Ein freies Antragsgebiet
ist weder verifiziertes Bundesland noch Wahlrechtsregel und filtert hier nichts.
Reihung und Worttreffer bleiben der getrennten Regel quellenauswahl überlassen.
"""

import re

VERSION = 1
UMFANG = "bund_land_ohne_gebietspruefung"
BUNDESLAENDER = {
    "Burgenland": "Burgenland", "Kaernten": "Kärnten", "Niederoesterreich": "Niederösterreich",
    "Oberoesterreich": "Oberösterreich", "Salzburg": "Salzburg", "Steiermark": "Steiermark",
    "Tirol": "Tirol", "Vorarlberg": "Vorarlberg", "Wien": "Wien",
}
_BUND = re.compile(r"NOR[0-9]{8}\Z", re.ASCII)
_LAND = re.compile(r"L[A-Z]{2}[0-9]{8}\Z", re.ASCII)


def dokumentart(ebene, bundesland, kennung):
    """Den ausdrücklichen Herkunftstyp prüfen, niemals aus einem Titel ableiten."""
    if not all(isinstance(s, str) for s in (ebene, bundesland, kennung)):
        raise ValueError("Quellenherkunft")
    if ebene == "Bund" and bundesland == "" and _BUND.fullmatch(kennung):
        return "Bundesnormen"
    if ebene == "Land" and bundesland in BUNDESLAENDER.values() and _LAND.fullmatch(kennung):
        return "Landesnormen"
    raise ValueError("Quellenherkunft")
