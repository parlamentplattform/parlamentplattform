"""Wächter für Migrationen, die Verfahrensdaten berühren (Grundregel 7)."""

from importlib import import_module

from django.db import migrations


def test_die_rueckwaertsmigration_0003_loescht_keine_voten():
    """Befund #74: Die Rückwärtsfunktion löschte ALLE Systembeiträge — samt der Reaktionen, die im
    Abstimmungs-Chat das Votum der Unterstützer sind (FB-G6). Rückwärts geschieht jetzt nichts,
    wie in verfahren/0011 und 0013."""
    modul = import_module("gremien.migrations.0003_voten_in_den_abstimmungschat")
    (operation,) = modul.Migration.operations
    assert isinstance(operation, migrations.RunPython)
    assert operation.reverse_code is migrations.RunPython.noop
    assert not hasattr(modul, "zurueck")
