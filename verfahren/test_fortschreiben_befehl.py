"""`verfahren_fortschreiben` — der Befehl für einen Cron (Befund #33).

Die Phasenautomatik hängt an Seitenaufrufen; Fristen wirken zwar rückwirkend zum Fristzeitpunkt,
aber je später jemand hinsieht, desto später sieht man das Ergebnis."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_der_befehl_wertet_faellige_fristen_aus_und_ist_idempotent(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("stellerin"), **ANTRAG, ordnung=ordnung)
    for name in ("u1", "u2"):
        antrag.unterstuetzungen.create(mitglied=mitglied_anlegen(name))
    antrag.fortschreiben()
    antrag.phase_beginn = timezone.now() - timedelta(days=22)  # beratung_tage = 21
    antrag.save(update_fields=["phase_beginn"])
    ruhend = antrag_einbringen(mitglied_anlegen("andere"), **ANTRAG, ordnung=ordnung)

    ausgabe = StringIO()
    call_command("verfahren_fortschreiben", stdout=ausgabe)
    antrag.refresh_from_db()
    ruhend.refresh_from_db()
    assert antrag.phase == "abstimmung" and ruhend.phase == "unterstuetzung"
    assert "1 Übergänge" in ausgabe.getvalue()

    ausgabe = StringIO()
    call_command("verfahren_fortschreiben", stdout=ausgabe)
    assert "0 Übergänge" in ausgabe.getvalue()
