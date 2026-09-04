"""FB-M5 (§ 12 Abs 5): /parameter.json und /kennzahlen.json im sprachneutralen Schema — Kopf,
Kennungen, Verfahrensordnung, kein Personenbezug, CORS-offen."""

import json

import pytest
from django.urls import reverse

from plattform_core.schema import SCHEMA_VERSION, pruefe_export
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_parameter_export_traegt_kopf_und_kennungen(client):
    antwort = client.get(reverse("parameter:export"))
    assert antwort["Access-Control-Allow-Origin"] == "*"
    daten = json.loads(antwort.content)
    assert daten["schema_version"] == SCHEMA_VERSION and daten["system_id"] == "at-ddoe"
    assert daten["software"]["name"] == "ParlamentPlattform" and daten["software"]["version"]
    kennungen = {p["schema_key"] for p in daten["parameter"]}
    assert {"support.review_days", "council.max_rounds", "ai.monthly_token_budget"} <= kennungen
    assert {"schluessel", "wert", "einheit", "beschreibung", "quelle", "geaendert_am"} <= set(daten["parameter"][0])
    assert pruefe_export(daten) == []


def test_verfahrensordnung_im_export(client, ordnung):  # noqa: F811
    daten = json.loads(client.get(reverse("parameter:export")).content)
    assert daten["verfahrensordnung"], "die aktive Verfahrensordnung steht im Export"
    werte = {w["schema_key"]: w["wert"] for w in daten["verfahrensordnung"][0]["werte"]}
    assert "support.threshold" in werte and "vote.min_turnout" in werte and "deliberation.window_days" in werte


def test_kennzahlen_export_ohne_personenbezug(client, ordnung):  # noqa: F811
    antwort = client.get(reverse("parameter:kennzahlen"))
    assert antwort["Access-Control-Allow-Origin"] == "*"
    daten = json.loads(antwort.content)
    kennzahlen = {k["schema_key"]: k for k in daten["kennzahlen"]}
    assert {
        "members.active", "motions.total", "motions.by_phase", "votes.completed",
        "votes.turnout_mean", "implementation.by_status", "areas_of_life.active",
    } <= set(kennzahlen)
    assert isinstance(kennzahlen["motions.by_phase"]["wert"], dict)
    assert isinstance(kennzahlen["implementation.by_status"]["wert"], dict)
    assert pruefe_export(daten) == []
    text = json.dumps(daten)
    for wort in ("email", "pseudonym", "username", "anzeigename"):
        assert wort not in text
