"""Explizite virtuelle Abrufuhr für Quellen-Tests, ohne echten Zwei-Sekunden-Schlaf."""

from datetime import UTC, datetime, timedelta

import pytest

from faktenbasis import abrufschutz


@pytest.fixture
def abrufuhr(monkeypatch):
    stand = [datetime(2026, 11, 2, 21, 0, tzinfo=UTC)]
    def zeit():
        stand[0] += timedelta(seconds=3)
        return stand[0]
    monkeypatch.setattr(abrufschutz, "_jetzt", zeit)
    return stand
