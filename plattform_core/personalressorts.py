"""Bekannte Ressorttabelle mit Methodik lesen, keine Kapazitäten oder Prognosen bilden."""

import re

VERSION = 1
REIHUNG = ("-stichtag", "-erfasst_am", "-pk")
RESSORTS = (
    "Sonstige oberste Organe", "Bundeskanzleramt", "Inneres",
    "Europäische und internationale Angelegenheiten", "Justiz", "Landesverteidigung", "Finanzen",
    "Wohnen, Kunst, Kultur, Medien und Sport", "Arbeit, Soziales, Gesundheit, Pflege und Konsumentenschutz",
    "Bildung", "Frauen, Wissenschaft und Forschung", "Wirtschaft, Energie und Tourismus",
    "Innovation, Mobilität und Infrastruktur",
    "Land- und Forstwirtschaft, Klima- und Umweltschutz, Regionen und Wasserwirtschaft",
)
_ZAHL = r"(?:0|[1-9][0-9]{0,2}(?:\.[0-9]{3})*)"


def _text(text):
    if not isinstance(text, str) or not text or len(text) > 20_000:
        raise ValueError("ressort_text")
    # Nur die beiden tatsächlich nachgewiesenen Umbrüche innerhalb eines Wortes.
    # Land-/Klima- mit anschließendem 'und' bleiben unverändert.
    text = re.sub(r"For\s*-\s*schung", "Forschung", text)
    text = re.sub(r"Infra\s*-\s*struktur", "Infrastruktur", text)
    return " ".join(text.split())


def aus_text(tabellenseite, methodikseite):
    t, m = _text(tabellenseite), _text(methodikseite)
    if not re.match(r"(?:Das Personal des Bundes 2026\s*30|30\s*Das Personal des Bundes 2026)\b", t):
        raise ValueError("ressort_seite")
    if ("9 Technischer Annex" not in m
            or "Aufgrund von Rundungen ergeben sich an einigen Stellen leichte Unterschiede zur Gesamtsumme." not in m
            or not re.search(r"9\.1 Bezugszeitraum .*?31\.12\.2025\.", m)
            or "9.2 Datenabgrenzung" not in m or "9.3 Messgröße" not in m
            or not re.search(r"Vollbeschäftigtenäqui\s*-?\s*valente", m)
            or "auf Basis von VBÄ berechnet." not in m):
        raise ValueError("ressort_methodik")
    kopf = re.search(
        r"Tabelle 7: Verteilung des Bundespersonals in den Ressorts, Stichtag 31\.12\.2025 "
        r"Ressort Gesamt in der Zentralstelle in nachge\s*ordneten Dienststellen ", t,
    )
    if kopf is None:
        raise ValueError("ressort_spalten")
    teil, ende, _ = t[kopf.end():].partition(" Die strategische Planung")
    if not ende:
        raise ValueError("ressort_tabellenende")
    zeilen, position = [], 0
    for name in RESSORTS:
        spalten = 1 if name == RESSORTS[0] else 3
        muster = re.escape(name) + " " + " ".join([rf"({_ZAHL})"] * spalten) + r"(?: |$)"
        treffer = re.compile(muster, flags=re.ASCII).match(teil, position)
        if treffer is None:
            raise ValueError("ressort_zeile")
        zahlen = [int(s.replace(".", "")) for s in treffer.groups()]
        zeilen.append({"ressort": name, "gesamt": zahlen[0],
            "zentralstelle": zahlen[1] if spalten == 3 else None,
            "nachgeordnet": zahlen[2] if spalten == 3 else None})
        position = treffer.end()
    gesamt = re.fullmatch(rf"Gesamt ({_ZAHL}) ({_ZAHL}) ({_ZAHL})", teil[position:], flags=re.ASCII)
    if gesamt is None:
        raise ValueError("ressort_gesamt")
    werte = [int(s.replace(".", "")) for s in gesamt.groups()]
    return {"datenjahr": 2025, "stichtag": "2025-12-31", "einheit": "VBÄ", "ressorts": zeilen,
        "gesamt": dict(zip(("gesamt", "zentralstelle", "nachgeordnet"), werte, strict=True))}
