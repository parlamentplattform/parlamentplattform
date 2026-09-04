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

SCHEMA_VERSION = "1.1"

# Kennung eines Systems: <Ländercode>-<Kurzname>, z. B. at-ddoe, de-kipartei, se-ddk
SYSTEM_ID_MUSTER = re.compile(r"^[a-z]{2}-[a-z0-9][a-z0-9-]{1,30}$")
SCHEMA_KEY_MUSTER = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

# Registerschlüssel (Instanz, deutsch) → (Schema-Kennung, Einheit, Bedeutung — englisch, sprachneutral)
PARAMETER = {
    "aehnlichkeit-schwelle-prozent": (
        "similarity.threshold_percent", "percent",
        "Similarity above which the platform points to an existing motion when submitting a new one",
    ),
    "aehnlichkeit-treffer": (
        "similarity.max_hits", "motions",
        "How many similar motions are shown when submitting",
    ),
    "kategorien-je-antrag": (
        "areas_of_life.per_motion", "areas",
        "How many areas of life a motion is assigned to automatically",
    ),
    "kategorien-regel": (
        "areas_of_life.rule_version", "rule version",
        "Version of the assignment rule for areas of life (keyword lists, no AI)",
    ),
    "chat-zeichen-hoechstzahl": (
        "deliberation.post_max_chars", "characters",
        "Maximum length of a post in the deliberation chat",
    ),
    "chat-bearbeitungsfenster-minuten": (
        "deliberation.edit_window_minutes", "minutes",
        "How long an author may still edit their own post",
    ),
    "kritik-mindestzeichen": (
        "draft_loop.criticism_min_chars", "characters",
        "Minimum length of a criticism so it counts as a change request to the expert council",
    ),
    "weicherfilter-regel": (
        "soft_filter.rule_version", "rule version",
        "Version of the member-controlled ordering rule (nine sliders, neutral by default)",
    ),
    "weicherfilter-profile-hoechstzahl": (
        "soft_filter.max_profiles", "profiles",
        "How many personal filter profiles a member may store",
    ),
    "faecher-regel": (
        "areas_fan.rule_version", "rule version",
        "Version of the layout algorithm for the areas-of-life fan",
    ),
    "faecher-kinder-hoechstzahl": (
        "areas_fan.max_children", "branches",
        "How many sub-branches a branch shows before it must be fanned out",
    ),
    "kacheln-hervorgehoben": (
        "tiles.highlighted", "tiles",
        "How many highlighted votes the important-votes field shows",
    ),
    "kacheln-abgeschlossen": (
        "tiles.completed", "entries",
        "How many completed procedures appear in the feed",
    ),
    "suche-treffer-hoechstzahl": (
        "areas_fan.max_search_hits", "hits",
        "Maximum number of hits shown by the search in the areas-of-life fan",
    ),
    "gespraeche-liste-hoechstzahl": (
        "conversations.list_limit", "conversations",
        "How many conversations the panel shows at once; the counter covers all of them",
    ),
    "archiv-audit-anzeige": (
        "archive.audit_display_limit", "events",
        "How many audit events the archive timeline shows; the export always contains all",
    ),
    "ki-antwort-hoechsttokens": (
        "ai.max_response_tokens", "tokens",
        "Maximum length of a model response",
    ),
    "anstoss-mindestabstand-sekunden": (
        "feedback.min_interval_seconds", "seconds",
        "Waiting time between two feedback messages from the same person",
    ),
    "anstoss-tagesgrenze": (
        "feedback.daily_limit", "messages",
        "How many feedback messages a person may send per day",
    ),
    "gremien-pruefung-tage": (
        "council.review_days", "days",
        "How long the second expert group has to check a proposal with implementation or procurement relevance",
    ),
    "gremien-beschluss-tage": (
        "council.decision_days", "days",
        "Default deadline for an internal decision in a council body",
    ),
    "verfahren-unterstuetzung-schwelle": (
        "support.threshold", "supporters",
        "Number of supporters a motion needs to enter deliberation",
    ),
    "verfahren-unterstuetzung-tage": (
        "support.window_days", "days",
        "Days a motion has to reach the support threshold",
    ),
    "expertenrat-erstvorschlag-tage": (
        "council.first_draft_days", "days",
        "Days the expert council has for its first proposal; also the minimum deliberation period",
    ),
    "verfahren-abstimmung-tage": (
        "vote.window_days", "days",
        "Duration of the final vote",
    ),
    "verfahren-mindestbeteiligung-prozent": (
        "vote.min_turnout_percent", "percent",
        "Share of eligible members that must take part for a result to stand",
    ),
    "verfahren-wiedereinbringung-monate": (
        "motion.resubmission_block_months", "months",
        "Months before a rejected or lapsed motion may be resubmitted verbatim",
    ),
    "gremien-review-tage": (
        "support.review_days", "days",
        "Days the supporters have to accept a draft or return it with a concrete wish (draft loop)",
    ),
    "gremien-ueberarbeitung-tage": (
        "council.rework_days", "days",
        "Days the expert council has to revise a draft after it was returned",
    ),
    "gremien-hoechstrunden": (
        "council.max_rounds", "rounds",
        "Maximum number of draft-loop rounds before the proposal goes to the final vote",
    ),
    "gremien-rollen-dauer-tage": (
        "bodies.role_term_days", "days",
        "Regular term of a body role (public call, confirmation by the assembly, automatic expiry)",
    ),
    "vorschlag-annahme-prozent": (
        "draft_loop.acceptance_percent", "percent",
        "Approval share the „fine as it is\" post must exceed in the proposal chat so the draft "
        "goes to the final vote (it must also rank first)",
    ),
    "vorschlag-chat-reihung": (
        "draft_loop.chat_ordering_version", "rule version",
        "Version of the proposal-chat ordering rule (engagement-v1: engagement desc, then approval "
        "share, then time)",
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
