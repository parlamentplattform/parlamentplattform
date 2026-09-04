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
    register = [k for k, _e, _b in PARAMETER.values()]
    ordnung = [k for k, _e in VERFAHRENSORDNUNG.values()]
    kennzahlen = [k for k, _e, _b in KENNZAHLEN]
    assert all(SCHEMA_KEY_MUSTER.match(k) for k in register + ordnung + kennzahlen)

    # Innerhalb einer Karte ist jede Kennung einmalig …
    for name, karte in (("Register", register), ("Verfahrensordnung", ordnung), ("Kennzahlen", kennzahlen)):
        assert len(set(karte)) == len(karte), f"{name}: doppelte Kennung"

    # … zwischen Register und Verfahrensordnung ist Gleichheit dagegen die Aussage (FB-J1):
    # Die Stellgröße `verfahren-unterstuetzung-tage` speist das Policy-Feld
    # `unterstuetzung_frist_tage`; dass beide `support.window_days` heißen, sagt einer
    # Partnerinstanz, dass es dieselbe Größe ist.
    gemeinsam = set(register) & set(ordnung)
    assert "support.window_days" in gemeinsam and "vote.window_days" in gemeinsam
    assert not (set(kennzahlen) & (set(register) | set(ordnung))), "Kennzahlen messen, sie stellen nicht"

    assert SCHEMA_VERSION == "1.1"
    assert schema_key("gremien-review-tage") == "support.review_days"
    assert schema_key("expertenrat-erstvorschlag-tage") == "council.first_draft_days"
    assert schema_key("nur-lokal") == ""


#: Zwei Stellgrößen tragen bewusst eine andere Kennung als das Policy-Feld, das sie speisen.
#: Beide Male ist der Wert derselbe, die Aussage aber nicht — und die Kennung beschreibt die
#: Aussage, nicht die Zahl.
ABWEICHENDE_KENNUNG = {
    # 21 Tage sind zugleich die Frist des Expertenrats und die Mindestdauer der Beratung
    # (FB-J1). Für eine Partnerinstanz ohne Expertenrat zählt die Beratungsdauer, für eine
    # mit Expertenrat die Frist — darum behalten beide Sichten ihren eigenen Namen.
    "beratung_tage": "die Frist des Expertenrats ist zugleich die Mindestdauer der Beratung",
    # Das Register führt Prozent als ganze Zahl (5), die Verfahrensordnung einen Anteil (0.05).
    # Verschiedene Einheiten brauchen verschiedene Kennungen, sonst rechnet jemand falsch.
    "mindestbeteiligung": "Register in Prozent, Verfahrensordnung als Anteil",
}


def test_jede_stellgroesse_der_verfahrensordnung_hat_dieselbe_kennung_wie_ihr_registerwert():
    """FB-J1: Was der Knopf „neue Fassung aus dem Register" überträgt, soll im Schema als
    dasselbe erkennbar sein — sonst kann eine Partnerinstanz die Werte nicht zuordnen.

    Die zwei begründeten Ausnahmen stehen in ABWEICHENDE_KENNUNG; wer eine dritte einführt,
    muss sie dort begründen und stolpert vorher über diesen Test."""
    from plattform_core.policy import REGISTER_ZUORDNUNG

    for feld, (registerschluessel, _wandler) in REGISTER_ZUORDNUNG.items():
        if feld not in VERFAHRENSORDNUNG or registerschluessel not in PARAMETER:
            continue
        aus_ordnung = VERFAHRENSORDNUNG[feld][0]
        aus_register = PARAMETER[registerschluessel][0]
        if feld in ABWEICHENDE_KENNUNG:
            assert aus_ordnung != aus_register, (
                f"{feld} steht als Ausnahme in ABWEICHENDE_KENNUNG, trägt aber dieselbe "
                f"Kennung — dann gehört der Eintrag entfernt."
            )
            continue
        assert aus_ordnung == aus_register, (
            f"{feld} heißt in der Verfahrensordnung {aus_ordnung}, "
            f"im Register aber {aus_register} — dieselbe Größe, zwei Namen. "
            f"Wenn das Absicht ist, gehört eine Begründung in ABWEICHENDE_KENNUNG."
        )


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
    assert daten["schema_version"] == "1.1" and daten["system_id"] == "at-ddoe"
    assert daten["software"]["version"] == "0.36.0" and daten["exportiert_am"].startswith("2026-09-03")
    assert daten["parameter"][0]["schema_key"] == "support.review_days"
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
    assert pruefe_export({"schema_version": "2.0", "system_id": "at-ddoe"}) == [
        f"Hauptversion 2.0 passt nicht zu {SCHEMA_VERSION}"
    ]
    # Eine Nebenversion desselben Hauptstands wird angenommen — 1.1 ergänzt 1.0, bricht es nicht
    assert pruefe_export({"schema_version": "1.0", "system_id": "at-ddoe"}) == []
