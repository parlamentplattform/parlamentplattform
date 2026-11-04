"""Alle fünf Pflichtprüfungen müssen die tatsächliche Auslieferung sperren können."""

from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parent.parent


@pytest.fixture
def jobs():
    return yaml.safe_load((WURZEL / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["jobs"]


@pytest.mark.parametrize("freigabejob", ["ausrollen", "nicht_ausgerollt"])
@pytest.mark.parametrize("pruefjob,python", [
    ("pruefen", "3.11"), ("pruefen", "3.12"),
    ("pruefen_postgres", None), ("pruefen_sicherung", None), ("sichtpruefung", None),
], ids=["python311", "python312", "postgres", "sicherung", "browser"])
def test_jede_pflichtpruefung_sperrt_deploy_und_erreicht_den_alarm(jobs, freigabejob, pruefjob, python):
    assert pruefjob in jobs[freigabejob]["needs"], f"{freigabejob} wartet nicht auf {pruefjob}"
    if python is not None:
        assert python in jobs[pruefjob]["strategy"]["matrix"]["python-version"]


@pytest.mark.parametrize("pruefjob", ["pruefen", "pruefen_postgres", "pruefen_sicherung", "sichtpruefung"])
def test_pflichtpruefungen_ignorieren_keine_fehler(jobs, pruefjob):
    job = jobs[pruefjob]
    assert not job.get("continue-on-error", False)
    assert all(not schritt.get("continue-on-error", False) for schritt in job["steps"])


def test_deploy_bleibt_auf_mainpush_begrenzt_und_umgeht_keinen_fehlstatus(jobs):
    bedingung = jobs["ausrollen"]["if"]
    assert "github.ref == 'refs/heads/main'" in bedingung
    assert "github.event_name == 'push'" in bedingung
    assert "always(" not in bedingung and "failure(" not in bedingung and "cancelled(" not in bedingung
    assert "failure()" in jobs["nicht_ausgerollt"]["if"]
