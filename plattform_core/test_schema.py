"""Das sprachneutrale Parameter-Schema (FB-M5): Kennungen, Exporte, Prüfung fremder Exporte."""

from datetime import UTC, datetime

from plattform_core.schema import (
    KENNZAHLEN,
    PARAMETER,
    SCHEMA_KEY_MUSTER,
    SCHEMA_VERSION,
    SYSTEM_ID_MUSTER,
    VERFAHRENSORDNUNG,
    kennzahlen_export,
    parameter_export,
    pruefe_export,
    schema_key,
    turnout_mean,
)

JETZT = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


def test_alle_kennungen_haben_das_format_und_sind_eindeutig():
    kennungen = [k for k, _e, _b in PARAMETER.values()] + [k for k, _e in VERFAHRENSORDNUNG.values()]
    kennungen += [k for k, _e, _b in KENNZAHLEN]
    assert all(SCHEMA_KEY_MUSTER.match(k) for k in kennungen), kennungen
    assert len(set(kennungen)) == len(kennungen)
    assert SCHEMA_VERSION == "1.0"
    assert schema_key("gremien-review-tage") == "draft_loop.review_days"
    assert schema_key("nur-lokal") == ""


def test_system_kennung_muster():
    assert SYSTEM_ID_MUSTER.match("at-ddoe") and SYSTEM_ID_MUSTER.match("se-ddk-2")
    assert not SYSTEM_ID_MUSTER.match("ddoe") and not SYSTEM_ID_MUSTER.match("AT-ddoe")


def test_parameter_export_traegt_kopf_kennungen_und_verfahrensordnung():
    parameter = [
        {"schluessel": "gremien-review-tage", "wert": "14", "einheit": "Tage", "beschreibung": "x", "quelle": "§ 5", "geaendert_am": "2026-09-03"},
        {"schluessel": "nur-lokal", "wert": "1"},
    ]
    ordnungen = [{"id": "sachantrag-standard", "version": 1, "unterstuetzung_schwelle": 3, "beratung_tage": 21, "mindestbeteiligung": 0.05}]
    daten = parameter_export("at-ddoe", "Direkte Demokratie Österreich", "0.36.0", parameter, ordnungen, JETZT)
    assert daten["schema_version"] == "1.0" and daten["system_id"] == "at-ddoe"
    assert daten["software"]["version"] == "0.36.0" and daten["exportiert_am"].startswith("2026-09-03")
    assert daten["parameter"][0]["schema_key"] == "draft_loop.review_days"
    assert daten["parameter"][1]["schema_key"] == ""  # lokale Stellgröße ohne gemeinsame Bedeutung
    werte = {w["schema_key"]: w["wert"] for w in daten["verfahrensordnung"][0]["werte"]}
    assert werte == {"support.threshold": 3, "deliberation.window_days": 21, "vote.min_turnout": 0.05}
    assert pruefe_export(daten) == []


def test_kennzahlen_export_nur_bekannte_kennungen():
    daten = kennzahlen_export("at-ddoe", "DDÖ", "0.36.0", {"members.active": 12, "unbekannt.x": 1}, JETZT)
    assert [k["schema_key"] for k in daten["kennzahlen"]] == ["members.active"]
    assert pruefe_export(daten) == []


def test_turnout_mean():
    assert turnout_mean([]) is None
    assert turnout_mean([0.5, 1.5, -1]) == 0.5  # begrenzt auf [0, 1]


def test_pruefung_beanstandet_kopf_kennung_und_personenbezug():
    assert pruefe_export("x") == ["kein Objekt"]
    fehler = pruefe_export({"system_id": "DDOE", "parameter": [{"schema_key": "Falsch", "email": "a@b"}]})
    assert any("schema_version" in f for f in fehler)
    assert any("system_id" in f for f in fehler)
    assert any("Format" in f for f in fehler) and any("personenbezogen" in f for f in fehler)
    assert pruefe_export({"schema_version": "2.0", "system_id": "at-ddoe"}) == ["Hauptversion 2.0 passt nicht zu 1.0"]
