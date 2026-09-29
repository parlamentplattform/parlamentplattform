"""Sicherung und Wache (ADR-012, Schritt 2 · 0.52.0): Das Skript ist lesbar und lehnt Fehlbedienung ab;
die Workflows rufen es auf und nennen ihre Secrets nur als Verweis, nie als Wert."""

import subprocess
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parents[1]
SKRIPT = WURZEL / "tools" / "sicherung.sh"
WORKFLOWS = WURZEL / ".github" / "workflows"


def _lauf(*argumente):
    return subprocess.run(["bash", str(SKRIPT), *argumente], capture_output=True, text=True, cwd=WURZEL)


def test_das_skript_ist_gueltiges_bash_und_zeigt_ohne_befehl_die_hilfe():
    assert subprocess.run(["bash", "-n", str(SKRIPT)]).returncode == 0
    ergebnis = _lauf()
    assert ergebnis.returncode == 2 and "sichern" in ergebnis.stdout and "probe" in ergebnis.stdout


def test_ohne_adresse_wird_nichts_gesichert():
    ergebnis = _lauf("sichern")
    assert ergebnis.returncode != 0 and "Datenbank-Adresse fehlt" in ergebnis.stderr


def test_die_workflows_nutzen_das_skript_und_nur_secret_verweise():
    sicherung = (WORKFLOWS / "sicherung.yml").read_text(encoding="utf-8")
    assert "tools/sicherung.sh sichern" in sicherung and "tools/sicherung.sh probe" in sicherung
    assert "${{ secrets.DDOE_SICHERUNG_DATENBANK_URL }}" in sicherung
    assert "${{ secrets.DDOE_SICHERUNG_TOKEN }}" in sicherung
    assert "postgres://" not in sicherung and "postgresql://" not in sicherung
    for name in ("sicherung.yml", "wache.yml"):
        daten = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        assert daten[True]["schedule"], f"{name} braucht einen Zeitplan"  # YAML liest „on“ als True


def test_die_wache_fragt_den_gesundheitscheck():
    wache = (WORKFLOWS / "wache.yml").read_text(encoding="utf-8")
    assert "https://parlament.ddoe.at/gesund/" in wache


def test_sitzungen_und_anmeldelinks_kommen_nicht_in_die_sicherung():
    """Prüfung 0.52.0: Wer die Sicherung liest, soll sich damit nicht als jemand anmelden können."""
    skript = SKRIPT.read_text(encoding="utf-8")
    assert "--exclude-table-data=django_session" in skript
    assert "--exclude-table-data=mitglieder_einmaltoken" in skript


def test_fehler_von_pg_dump_und_pg_restore_bleiben_aus_dem_oeffentlichen_protokoll():
    skript = SKRIPT.read_text(encoding="utf-8")
    assert skript.count('2> "$fehlerdatei"') >= 3
    sicherung = (WORKFLOWS / "sicherung.yml").read_text(encoding="utf-8")
    assert "::add-mask::" in sicherung and "timeout-minutes" in sicherung


def test_eine_kleinere_sicherung_loescht_nichts():
    sicherung = (WORKFLOWS / "sicherung.yml").read_text(encoding="utf-8")
    pruefung = sicherung.index("Nicht kleiner als die letzte Sicherung?")
    assert pruefung < sicherung.index("In das Sicherungs-Repository") < sicherung.index("Ältere Sicherungen entfernen")


@pytest.mark.django_db
def test_die_datenschutzerklaerung_nennt_die_sicherung_bei_github(client):
    """Die Erklärung sagt, was der Code tut: tägliche Kopie bei GitHub, unverschlüsselt, mit Frist."""
    inhalt = client.get("/datenschutz/").content.decode()
    assert "GitHub, Inc." in inhalt and "nicht verschlüsselt" in inhalt and "90 Tage" in inhalt
