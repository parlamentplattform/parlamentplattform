"""GP-041: Die Auswahlfelder der Räte zeigten nur die 50 jüngsten Anträge.

Bei mehr Verfahren war der Vollzug eines älteren Beschlusses über die Oberfläche nicht mehr aussetzbar.
Jetzt findet die Suche über dem Auswahlfeld jeden Antrag nach Titel oder Nummer, und ein Verweis mit
`?antrag=<nummer>` wählt ihn vor — beides ohne JavaScript."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Anlass, GremienBeschluss, Gremium
from gremien.test_werkstatt import ANTRAG, mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from plattform_core import Phase
from verfahren.models import Antrag, antrag_einbringen

pytestmark = pytest.mark.django_db


def _bestand(ordnung, anzahl=2000):  # noqa: F811
    """Der älteste Antrag ist angenommen, danach kommen `anzahl - 1` jüngere."""
    jetzt = timezone.now()
    steller = mitglied_anlegen('steller')
    aeltester = antrag_einbringen(steller, 'Ältester angenommener Antrag', ANTRAG['wortlaut'], ANTRAG['begruendung'], ordnung)
    Antrag.objects.filter(pk=aeltester.pk).update(phase=Phase.ANGENOMMEN.value, phase_beginn=jetzt - timedelta(days=900))
    vorlage = Antrag.objects.get(pk=aeltester.pk)
    juengere = []
    for i in range(anzahl - 1):
        vorlage.pk = None
        vorlage.id = None
        vorlage.titel = f'Jüngerer Antrag {i:04d}'
        vorlage.phase = Phase.UNTERSTUETZUNG.value
        vorlage.phase_beginn = jetzt - timedelta(minutes=i)
        juengere.append(Antrag(**{f.attname: getattr(vorlage, f.attname) for f in Antrag._meta.concrete_fields}))
    Antrag.objects.bulk_create(juengere, batch_size=500)
    return Antrag.objects.get(pk=aeltester.pk)


def _optionen(html: str, select_id: str) -> list[str]:
    auswahl = re.search(rf'<select id="{select_id}"[^>]*>(.*?)</select>', html, re.S).group(1)
    return re.findall(r'<option value="(\d+)"', auswahl)


def test_der_integritaetsrat_setzt_den_vollzug_des_aeltesten_von_2000_antraegen_aus(client, ordnung):  # noqa: F811
    aeltester = _bestand(ordnung)
    ir = [mitglied_anlegen(f'ir{i}') for i in range(3)]
    for m in ir:
        rolle_geben(m, Gremium.INTEGRITAETSRAT)
    client.force_login(ir[0])
    seite = reverse('gremien:integritaet')
    ohne = client.get(seite).content.decode()
    assert str(aeltester.pk) not in _optionen(ohne, 'ir-antrag')  # die Auswahl bleibt kurz …
    assert 'name="antrag_suche"' in ohne  # … und die Suche führt weiter
    gesucht = client.get(seite, {'antrag_suche': 'Ältester angenommener'}).content.decode()
    assert _optionen(gesucht, 'ir-antrag') == [str(aeltester.pk)]
    nach_nummer = client.get(seite, {'antrag_suche': str(aeltester.pk)}).content.decode()
    assert str(aeltester.pk) in _optionen(nach_nummer, 'ir-antrag')
    vorgewaehlt = client.get(seite, {'antrag': aeltester.pk}).content.decode()
    assert f'<option value="{aeltester.pk}" selected>' in vorgewaehlt
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.AUSSETZUNG, 'antrag': _optionen(gesucht, 'ir-antrag')[0], 'beschreibung': 'Vollzug prüfen.'},
    )
    assert GremienBeschluss.objects.filter(anlass=Anlass.AUSSETZUNG, antrag=aeltester).exists()


def test_der_koordinationsrat_findet_jeden_laufenden_antrag(client, ordnung):  # noqa: F811
    aeltester = _bestand(ordnung, anzahl=60)
    Antrag.objects.filter(pk=aeltester.pk).update(phase=Phase.BERATUNG.value)
    kr = mitglied_anlegen('kr0')
    rolle_geben(kr, Gremium.KOORDINATIONSRAT)
    client.force_login(kr)
    seite = reverse('gremien:koordination')
    assert str(aeltester.pk) not in _optionen(client.get(seite).content.decode(), 'hv-antrag')
    gesucht = client.get(seite, {'antrag_suche': 'Ältester'}).content.decode()
    assert _optionen(gesucht, 'hv-antrag') == [str(aeltester.pk)]
    # Unsinn in der Suche ist kein Serverfehler.
    assert client.get(seite, {'antrag_suche': '9' * 40, 'antrag': 'x'}).status_code == 200
