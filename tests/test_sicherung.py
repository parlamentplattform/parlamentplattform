"""Sicherung und Wache (ADR-012, Schritt 2 · 0.52.0): Das Skript ist lesbar und lehnt Fehlbedienung ab;
die Workflows rufen es auf und nennen ihre Secrets nur als Verweis, nie als Wert."""

import subprocess
from pathlib import Path

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
