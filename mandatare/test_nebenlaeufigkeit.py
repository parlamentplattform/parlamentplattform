"""Stufe 2 der Vertrauensfrage unter Nebenläufigkeit (§ 7 Abs 10 lit f, Grundregel 7).

`vertrauensfragen_fortschreiben` läuft aus jeder Vertrauensfrage-Antragsseite, aus den
Mandatarseiten und aus dem Fristen-Wächter — in zwei Workern gleichzeitig. Zwei Aufrufe dürfen
dieselbe Stufe nicht zweimal vollziehen, sonst stünden Rollenende und Ende der Vertretung zweimal
im Rechenschaftsregister. Die Zeilensperre wirkt nur auf PostgreSQL (SQLite serialisiert
ohnehin); darum laufen diese Tests nur dort — die CI fährt sie im Job `pruefen_postgres`.
"""

import threading
import time

import pytest
from django.db import connection, connections

# Das Einmal-Token-Modell liegt in `mitglieder.auth_flows`, nicht in `models.py`; ohne diesen
# Import kennt der Flush der transaktionalen Tests die Tabelle nicht und scheitert am Fremdschlüssel.
import mitglieder.auth_flows  # noqa: F401
from mandatare.models import Vertrauensfrage, vertrauensfragen_fortschreiben
from verfahren.test_vertrauensfrage import _verloren, altmandat, audit, tage  # noqa: F401
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Zeilensperren wirken nur auf PostgreSQL"),
]


@pytest.mark.parametrize("fenster", [0.0, 0.3])
def test_zwei_gleichzeitige_laeufe_vollziehen_stufe_zwei_einmal(ordnung, altmandat, monkeypatch, fenster):  # noqa: F811
    """Das Fenster verzögert nur zwischen Lesen und Schreiben — es gibt es auch ohne Sonde."""
    antrag, ende = _verloren(ordnung, altmandat)
    if fenster:
        echte = Vertrauensfrage.endgueltig_ab

        def langsam(self):
            time.sleep(fenster)
            return echte(self)

        monkeypatch.setattr(Vertrauensfrage, "endgueltig_ab", langsam)
    schranke = threading.Barrier(2)
    ergebnisse, fehler = [], []

    def lauf():
        try:
            schranke.wait(5)
            ergebnisse.append(vertrauensfragen_fortschreiben(ende + tage(40)))
        except Exception as e:  # noqa: BLE001 — der Test berichtet jeden Fehler des Fadens
            fehler.append(f"{type(e).__name__}: {e}")
        finally:
            connections.close_all()

    faeden = [threading.Thread(target=lauf) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(30)
    assert fehler == []
    assert sorted(ergebnisse) == [0, 1]
    assert len(audit("vertrauensfrage_endgueltig")) == 1
    assert len(audit("vertretung_beendet")) == 1
