"""Die Stundengrenze der Textgegenüberstellung zählt nur Versuche, die den Anbieter erreichen (GP-207). Nie Netz."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

from types import SimpleNamespace

import pytest

from ki.gegenueberstellungen import anfordern
from ki.models import SteckplatzZugang
from ki.test_gegenueberstellungen import anfrage, modell  # noqa: F401
from ki.test_vergleichskontext import lage  # noqa: F401
from mitglieder.models import Drosselzaehler
from parameter.models import Parameter
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_belegter_steckplatz_verbraucht_keine_stundengrenze(lage, modell, monkeypatch):
    monkeypatch.setattr('mitglieder.botschutz.time', SimpleNamespace(time=lambda: 1800000000))
    Parameter.objects.create(schluessel='gegenueberstellung-je-stunde', wert='5')
    SteckplatzZugang.objects.update_or_create(name='anbieter', defaults={'belegt': True})
    for _ in range(5):
        assert anfordern(*anfrage(lage)).meldung == 'steckplatz_stumm'
    mitglied = lage[1]
    zaehler = Drosselzaehler.objects.filter(zweck='gegenueberstellung', kennung=f'konto:{mitglied.pk}')
    assert sum(zaehler.values_list('anzahl', flat=True)) == 0 and not modell
    SteckplatzZugang.objects.filter(name='anbieter').update(belegt=False)
    assert anfordern(*anfrage(lage)).status == 'fertig' and len(modell) == 1
