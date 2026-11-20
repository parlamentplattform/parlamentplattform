"""Sicherung und Wache (ADR-012, Schritt 2 · 0.52.0): Das Skript ist lesbar und lehnt Fehlbedienung ab;
die Workflows rufen es auf und nennen ihre Secrets nur als Verweis, nie als Wert."""

import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from verfahren import sicherung as s
from verfahren.test_sicherung import JETZT, github, release  # noqa: F401

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


def test_die_workflows_pruefen_nur_die_fertige_sicherung_ohne_datenbankzugang():
    sicherung = (WORKFLOWS / "sicherung.yml").read_text(encoding="utf-8")
    assert "tools/sicherung.sh sichern" not in sicherung and "tools/sicherung.sh probe" in sicherung
    assert "DDOE_SICHERUNG_DATENBANK_URL" not in sicherung
    assert "https://parlament.ddoe.at/sicherung/status.json" in sicherung
    assert "${{ secrets.DDOE_SICHERUNG_TOKEN }}" in sicherung
    assert "postgres://" not in sicherung and "postgresql://" not in sicherung
    for name in ("sicherung.yml", "wache.yml"):
        daten = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        assert daten[True]["schedule"], f"{name} braucht einen Zeitplan"  # YAML liest „on“ als True
    assert yaml.safe_load(sicherung)[True]["schedule"] == [{"cron": "17 4 2 * *"}]


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
    assert "timeout-minutes" in sicherung and "DDOE_SICHERUNG_DATENBANK_URL" not in sicherung


def test_der_postgres_client_wird_signiert_und_ohne_systemaenderungen_bereitgestellt():
    skript = (WURZEL / "tools/postgres_client.sh").read_text(encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(WURZEL / "tools/postgres_client.sh")]).returncode == 0
    assert "B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8" in skript
    assert "signed-by=" in skript and "dpkg-deb --extract" in skript
    assert "sudo" not in skript and "--allow-unauthenticated" not in skript


@pytest.mark.django_db
def test_die_datenschutzerklaerung_nennt_takt_und_frist_der_sicherung(client, github, monkeypatch):  # noqa: F811
    """Die Erklärung sagt, was der Code tut (GP-024): eine Kopie im Monat bei GitHub, unverschlüsselt,
    aufbewahrt so lange, wie `verfahren/sicherung.py` sie behält — Takt und Frist am Code geprüft."""
    inhalt = " ".join(client.get("/datenschutz/").content.decode().split())
    assert "GitHub, Inc." in inhalt and "nicht verschlüsselt" in inhalt
    assert "Einmal im Monat geht eine Kopie" in inhalt and "täglich" not in inhalt
    assert f"Sicherungskopien der Datenbank bleiben {s.AUFBEWAHRUNG_TAGE} Tage;" in inhalt
    assert "90 Tage" not in inhalt

    # Takt: im selben Kalendermonat keine zweite Sicherung, im nächsten wieder eine.
    jetzt = {"wert": JETZT}
    monkeypatch.setattr(s.timezone, "now", lambda: jetzt["wert"])
    s.eine_runde()
    s.eine_runde()
    assert len(github.assets) == 2
    jetzt["wert"] = JETZT + timedelta(days=30)
    s.eine_runde()
    assert len(github.assets) == 4

    # Frist: eine Sicherung bleibt genau so viele Tage, wie die Erklärung nennt.
    def monatssicherung(nummer, alter):
        zeit = JETZT - timedelta(days=alter)
        return release(f"ddoe-sicherung-{zeit:%Y-%m-%dT%H%M%S}Z", id=nummer, body="art=monatlich audit=1")

    github.aufrufe.clear()
    s._aufraeumen(github, [monatssicherung(7, s.AUFBEWAHRUNG_TAGE - 1), monatssicherung(8, s.AUFBEWAHRUNG_TAGE + 1)], JETZT)
    geloescht = [x[0] for x in github.aufrufe if x[1] == "DELETE"]
    assert "/releases/8" in geloescht and "/releases/7" not in geloescht
