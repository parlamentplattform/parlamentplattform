"""Betrieb (Cluster D der Gesamtprüfung 0.45): Was in Produktion still schiefgehen würde.

Drei Dinge, die keine Fachfunktion sind und deshalb bisher kein Test hielt: dass ein
Serverfehler mit DEBUG=0 überhaupt irgendwo steht (Befund #17), dass der Gesundheitscheck die
Datenbank berührt (Befund #94) und dass der App-Rahmen mit Manifest-Speicher rendert, bevor der
Deploy es herausfindet (Befund #98). Dazu der Deploy-Systemcheck ohne offene Warnung (Befund #97).
"""

from __future__ import annotations

import io
import logging
import os
import pathlib
import subprocess
import sys

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import path

WURZEL = pathlib.Path(__file__).resolve().parent.parent


# ── Befund #17: Serverfehler landen auf stderr — unabhängig von DEBUG ─────────────────────


def _wirft(request):
    raise RuntimeError("absichtlich kaputt (Test)")


urlpatterns = [path("kaputt/", _wirft)]


@pytest.mark.django_db
def test_serverfehler_steht_mit_traceback_auf_stderr(settings):
    """Die 500-Seite verspricht „Er ist protokolliert". Ohne eigene LOGGING-Einstellung stimmte
    das nicht: Djangos Standard-Handler filtert auf DEBUG=1, und der Mail-Handler hat keine
    Empfänger. Hier wird der Strom des stderr-Handlers kurz umgeleitet und die Anfrage gestellt —
    der Traceback muss dort ankommen, mit DEBUG aus (Tests laufen ohne DEBUG)."""
    settings.ROOT_URLCONF = __name__
    assert settings.DEBUG is False
    logger = logging.getLogger("django.request")
    handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
    assert not handler.filters, "der Handler darf nicht auf DEBUG filtern (RequireDebugTrue)"
    assert logger.propagate is False  # sonst doppelt über den django-Logger
    puffer = io.StringIO()
    alt = handler.setStream(puffer)
    try:
        antwort = Client(raise_request_exception=False).get("/kaputt/")
    finally:
        handler.setStream(alt)
    assert antwort.status_code == 500
    protokoll = puffer.getvalue()
    assert "Internal Server Error: /kaputt/" in protokoll
    assert "RuntimeError: absichtlich kaputt (Test)" in protokoll  # der Traceback, nicht nur die Zeile


def test_wurzel_logger_schreibt_ab_warning():
    """Die `log.exception`-Aufrufe der Apps (SMTP-Fehler, Besuchszählung) brauchen einen Handler,
    sonst greift Pythons lastResort nur, solange niemand sonst einen Handler setzt."""
    wurzel = logging.getLogger()
    assert wurzel.level == logging.WARNING
    assert any(isinstance(h, logging.StreamHandler) for h in wurzel.handlers)


# ── Befund #94: /gesund/ berührt die Datenbank ─────────────────────────────────────────────


@pytest.mark.django_db
def test_gesund_antwortet_ok_mit_datenbank(client):
    antwort = client.get("/gesund/")
    assert antwort.status_code == 200 and antwort.json() == {"status": "ok"}


@pytest.mark.django_db
def test_gesund_meldet_503_ohne_datenbank(client, monkeypatch):
    """Render hält einen Dienst für gesund, solange /gesund/ 200 sagt. Fällt die Datenbank aus,
    muss die Antwort 503 sein — sonst bleibt eine tote Instanz stehen und ein Deploy, dessen
    neue Instanz die Datenbank nicht erreicht, löst die alte ab."""
    from django.db import DatabaseError, connection

    def kaputt(*args, **kwargs):
        raise DatabaseError("Verbindung verweigert (Test)")

    monkeypatch.setattr(connection, "cursor", kaputt)
    antwort = client.get("/gesund/")
    assert antwort.status_code == 503 and antwort.json() == {"status": "datenbank"}


# ── Befund #98: Manifest-Speicher — der App-Rahmen rendert mit gefülltem Manifest ─────────


@pytest.mark.django_db
def test_app_rahmen_rendert_mit_manifest_speicher(settings, tmp_path, client):
    """Mit `ManifestStaticFilesStorage` wirft `{% static %}` in Produktion für jede Datei, die im
    Manifest fehlt (manifest_strict). Die Tests laufen ohne DDOE_STATIK und sähen das nie —
    hier wird das Manifest gefüllt und der Rahmen gerendert, damit ein hängender Verweis vor dem
    Deploy auffällt und nicht in der dockerCommand-Kette. Geprüft wird Djangos eigene
    Manifest-Klasse, von der WhiteNoises Speicher erbt; WhiteNoise selbst ist lokal nicht Pflicht."""
    settings.STATIC_ROOT = tmp_path / "static"
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }
    call_command("collectstatic", interactive=False, verbosity=0)
    assert (tmp_path / "static" / "staticfiles.json").exists()
    for pfad in ("/", "/parlament/", "/uebersicht/", "/rollen/", "/parameter/"):
        antwort = client.get(pfad)
        assert antwort.status_code == 200, pfad
        inhalt = antwort.content.decode()
        # Die Verweise tragen den Inhalts-Hash — genau das erlaubt lange Cache-Zeiten.
        assert "verfahren/js/htmx.min.js" not in inhalt and "verfahren/js/htmx.min." in inhalt, pfad


# ── Befund #97: `check --deploy` ohne offene Warnung ───────────────────────────────────────


def test_deploy_systemcheck_ohne_warnung():
    """CLAUDE.md § 5 Punkt 2: `check --deploy` ohne neue Warnung. Der Check läuft nur mit
    DEBUG=0 sinnvoll — die Sicherheitseinstellungen greifen erst dann (settings.py). Genau so
    ruft ihn die CI auf; W021 (HSTS-Preload) ist begründet gestillt, alles andere muss stoppen."""
    umgebung = {
        **os.environ,
        "DDOE_DEBUG": "0",
        "DDOE_SECRET_KEY": "x7Qm2LpZ9vRtB4nWc8HsJ1KdF6gYa3EeUoI5TrNbVzXqPmLkOjHgFdSaQwErTyUiOp",
        "DDOE_ALLOWED_HOSTS": "parlament.ddoe.at",
    }
    umgebung.pop("DDOE_STATIK", None)  # WhiteNoise ist auf dem Arbeitsplatz nicht Pflicht
    lauf = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=WURZEL,
        env=umgebung,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "1 silenced" in lauf.stdout + lauf.stderr  # W021 — und nur W021
