"""Das sprachneutrale Parameter-Schema (FB-M5, FB-M6; Satzung § 12 Abs 5): die Brücke zwischen
den Landesinstanzen der ParlamentPlattform.

Jedes Land betreibt seine eigene Instanz mit eigenem Parameterregister (deutsche, spanische,
norwegische … Schlüssel und Beschreibungen). Getauscht wird nur, was überall dasselbe bedeutet:
eine **Schema-Kennung** je Stellgröße (englisch, stabil, mit Punkten gegliedert), ihre Einheit und
ihr Wert — plus aggregierte Kennzahlen. Niemals personenbezogene Daten (§ 8, Art 9 DSGVO).

Dieses Modul ist rein (kein Django): Es definiert das Schema, baut die Exporte aus Rohdaten und
prüft fremde Exporte. Die Django-Ansichten (`/parameter.json`, `/kennzahlen.json`) rufen es auf;
`docs/SCHEMA.md` ist die lesbare Fassung, ADR-009 die Entscheidung. Versioniert nach SemVer:
neue Kennungen erhöhen die Nebenversion, umgedeutete Kennungen die Hauptversion.
"""

from __future__ import annotations

import re
from statistics import mean

SCHEMA_VERSION = "1.0"

# Kennung eines Systems: <Ländercode>-<Kurzname>, z. B. at-ddoe, de-kipartei, se-ddk
SYSTEM_ID_MUSTER = re.compile(r"^[a-z]{2}-[a-z0-9][a-z0-9-]{1,30}$")
SCHEMA_KEY_MUSTER = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

# Registerschlüssel (Instanz, deutsch) → (Schema-Kennung, Einheit, Bedeutung — englisch, sprachneutral)
PARAMETER = {
    "gremien-review-tage": (
        "draft_loop.review_days", "days",
        "Days the supporters have to accept a draft or return it with a concrete wish (draft loop)",
    ),
    "gremien-ueberarbeitung-tage": (
        "draft_loop.revision_days", "days",
        "Days the expert council has to revise a draft after it was returned",
    ),
    "gremien-hoechstrunden": (
        "draft_loop.max_rounds", "rounds",
        "Maximum number of draft-loop rounds before the proposal goes to the final vote",
    ),
    "gremien-rollen-dauer-tage": (
        "bodies.role_term_days", "days",
        "Regular term of a body role (public call, confirmation by the assembly, automatic expiry)",
    ),
    "ki-monatstokens": (
        "ai.monthly_token_budget", "tokens/month",
        "Hard monthly token budget of the model slot (cost cap of the future workshop)",
    ),
}

# Felder der Verfahrensordnung (Policy) → (Schema-Kennung, Einheit)
VERFAHRENSORDNUNG = {
    "unterstuetzung_schwelle": ("support.threshold", "supporters"),
    "unterstuetzung_frist_tage": ("support.window_days", "days"),
    "beratung_tage": ("deliberation.window_days", "days"),
    "abstimmung_tage": ("vote.window_days", "days"),
    "mindestbeteiligung": ("vote.min_turnout", "share"),
    "mehrheitsbasis": ("vote.majority_basis", "enum"),
    "wiedereinbringung_sperre_monate": ("motion.resubmission_block_months", "months"),
}

# Aggregierte Kennzahlen (Kennung, Einheit, Bedeutung) — nie personenbezogen
KENNZAHLEN = (
    ("members.active", "count", "Active member accounts"),
    ("motions.total", "count", "Motions submitted (without formally rejected ones)"),
    ("motions.by_phase", "map", "Motions per phase: support, deliberation, vote, adopted, rejected, lapsed"),
    ("votes.completed", "count", "Completed votes (adopted or rejected after a vote)"),
    ("votes.turnout_mean", "share", "Mean turnout of completed votes: ballots cast / eligible members"),
    ("implementation.by_status", "map", "Adopted motions per implementation status"),
    ("areas_of_life.active", "count", "Active areas of life (nodes of the category tree)"),
)
KENNZAHL_KENNUNGEN = {k for k, _e, _b in KENNZAHLEN}


def schema_key(register_schluessel: str) -> str:
    """Schema-Kennung zu einem Registerschlüssel — leer, wenn der Eintrag nur lokal gilt."""
    eintrag = PARAMETER.get(register_schluessel)
    return eintrag[0] if eintrag else ""


def _kopf(system_id: str, system_name: str, software_version: str, jetzt) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "system_id": system_id,
        "system_name": system_name,
        "software": {
            "name": "ParlamentPlattform",
            "version": software_version,
            "quelle": "https://github.com/parlamentplattform/parlamentplattform",
            "lizenz": "AGPL-3.0-or-later",
        },
        "exportiert_am": jetzt.isoformat() if hasattr(jetzt, "isoformat") else str(jetzt),
    }


def parameter_export(system_id, system_name, software_version, parameter, ordnungen, jetzt) -> dict:
    """Baut `/parameter.json`. `parameter`: Folge von Mappings mit schluessel, wert, einheit,
    beschreibung, quelle, geaendert_am (ISO), optional schema_key; `ordnungen`: Folge von
    Mappings mit id, version und den Policy-Feldern (siehe VERFAHRENSORDNUNG)."""
    daten = _kopf(system_id, system_name, software_version, jetzt)
    daten["parameter"] = []
    for p in parameter:
        kennung = p.get("schema_key") or schema_key(p["schluessel"])
        daten["parameter"].append({
            "schema_key": kennung,
            "schluessel": p["schluessel"],
            "wert": p["wert"],
            "einheit": p.get("einheit", ""),
            "beschreibung": p.get("beschreibung", ""),
            "quelle": p.get("quelle", ""),
            "geaendert_am": p.get("geaendert_am", ""),
        })
    daten["verfahrensordnung"] = [
        {
            "id": o.get("id", ""),
            "version": o.get("version", 0),
            "werte": [
                {"schema_key": kennung, "einheit": einheit, "wert": o[feld]}
                for feld, (kennung, einheit) in VERFAHRENSORDNUNG.items()
                if feld in o
            ],
        }
        for o in ordnungen
    ]
    return daten


def kennzahlen_export(system_id, system_name, software_version, werte: dict, jetzt) -> dict:
    """Baut `/kennzahlen.json` aus einem Mapping Kennung → Wert (nur bekannte Kennungen)."""
    daten = _kopf(system_id, system_name, software_version, jetzt)
    daten["kennzahlen"] = [
        {"schema_key": kennung, "einheit": einheit, "wert": werte[kennung]}
        for kennung, einheit, _b in KENNZAHLEN
        if kennung in werte
    ]
    return daten


def turnout_mean(anteile) -> float | None:
    """Mittlere Beteiligung aus Anteilen (abgegeben / stimmberechtigt), gerundet — None ohne Daten."""
    werte = [min(1.0, max(0.0, float(a))) for a in anteile]
    return round(mean(werte), 4) if werte else None


def pruefe_export(daten) -> list[str]:
    """Prüft einen (fremden) Export gegen das Schema — Rückgabe: Liste der Beanstandungen (leer = gut).
    Die Regeln sind bewusst mild: unbekannte Kennungen sind erlaubt (Nebenversionen), fehlender
    Kopf, falsche System-Kennung oder personenbezogene Felder sind Fehler."""
    fehler: list[str] = []
    if not isinstance(daten, dict):
        return ["kein Objekt"]
    version = str(daten.get("schema_version", ""))
    if not version:
        fehler.append("schema_version fehlt")
    elif version.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        fehler.append(f"Hauptversion {version} passt nicht zu {SCHEMA_VERSION}")
    system_id = str(daten.get("system_id", ""))
    if not SYSTEM_ID_MUSTER.match(system_id):
        fehler.append(f"system_id „{system_id}“ entspricht nicht <ländercode>-<kurzname>")
    verboten = {"email", "e_mail", "name", "pseudonym", "mitglied", "member", "user"}
    for block in ("parameter", "kennzahlen"):
        eintraege = daten.get(block, [])
        if not isinstance(eintraege, list):
            fehler.append(f"{block} ist keine Liste")
            continue
        for i, e in enumerate(eintraege):
            if not isinstance(e, dict):
                fehler.append(f"{block}[{i}] ist kein Objekt")
                continue
            kennung = str(e.get("schema_key", ""))
            if kennung and not SCHEMA_KEY_MUSTER.match(kennung):
                fehler.append(f"{block}[{i}]: Kennung „{kennung}“ hat kein gültiges Format")
            if verboten & {k.lower() for k in e}:
                fehler.append(f"{block}[{i}]: personenbezogenes Feld")
    return fehler
