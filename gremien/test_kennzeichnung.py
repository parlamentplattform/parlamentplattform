"""Z-6 (zu E-10): reine Kennzeichnung am Ratsbeschluss.

Die öffentliche Beschlussseite und die Beschlussliste nennen, mit wie vielen Personen beschlossen wurde,
und — ohne Namen — wenn ein mitstimmendes Ratsmitglied den betroffenen Antrag selbst eingebracht hat.
Kein Stimmverbot, keine Sperre: Ergebnis und Wirkung sind mit und ohne Kennzeichnung gleich (der Gründer
hat am 20.11.2026 entschieden, dass Ratsmitglieder in eigener Sache mitstimmen)."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from gremien.models import Anlass, BeschlussStatus, GremienBeschluss, Gremium
from gremien.test_werkstatt import ANTRAG, mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from verfahren.models import Antrag, antrag_einbringen

pytestmark = pytest.mark.django_db

SATZ = 'Ein mitstimmendes Mitglied hat diesen Antrag eingebracht'


def _fassen(client, leute, antrag):
    client.force_login(leute[0])
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.HERVORHEBUNG, 'antrag': antrag.pk, 'beschreibung': 'Grund.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    for m in leute:
        client.force_login(m)
        client.post(reverse('gremien:beschluss_stimme', args=[beschluss.pk]), {'option': 'dafuer', 'begruendung': 'Ja.'})
    beschluss.refresh_from_db()
    return beschluss


def test_die_kennzeichnung_aendert_weder_ergebnis_noch_wirkung(client, ordnung):  # noqa: F811
    ir = [mitglied_anlegen(f'ir{i}') for i in range(3)]
    for m in ir:
        rolle_geben(m, Gremium.INTEGRITAETSRAT)
    eigener = antrag_einbringen(ir[0], **ANTRAG, ordnung=ordnung)
    fremder = antrag_einbringen(mitglied_anlegen('aussen'), **{**ANTRAG, 'titel': 'Ein anderer Antrag'}, ordnung=ordnung)
    mit = _fassen(client, ir, eigener)
    ohne = _fassen(client, ir, fremder)

    # Ergebnis und Wirkung: gleich.
    assert mit.status == ohne.status == BeschlussStatus.ENTSCHIEDEN
    assert mit.ergebnis == ohne.ergebnis == 'dafuer'
    assert Antrag.objects.get(pk=eigener.pk).hervorgehoben == Antrag.objects.get(pk=fremder.pk).hervorgehoben is True
    assert mit.auswertung().zaehlung == ohne.auswertung().zaehlung

    gast = Client()
    seite_mit = gast.get(reverse('gremien:beschluss', args=[mit.nummer])).content.decode()
    seite_ohne = gast.get(reverse('gremien:beschluss', args=[ohne.nummer])).content.decode()
    assert SATZ in seite_mit and SATZ not in seite_ohne
    assert 'mit 3 Personen beschlossen' in seite_mit and 'mit 3 Personen beschlossen' in seite_ohne
    # Ohne Namen: Der Satz nennt niemanden.
    satz = seite_mit[seite_mit.index(SATZ) - 200: seite_mit.index(SATZ) + len(SATZ) + 20]
    assert ir[0].anzeigename not in satz

    liste = gast.get(reverse('gremien:beschluesse')).content.decode()
    assert liste.count(SATZ) == 1 and liste.count('mit 3 Personen beschlossen') == 2


def test_ein_offener_oder_altbeschluss_ohne_festgehaltene_zahl_nennt_keine_personenzahl(client, ordnung):  # noqa: F811
    """Ohne festgehaltene Auszählung (Altbestand vor 0.115) steht keine Zahl da, statt einer geratenen."""
    ir = [mitglied_anlegen(f'ir{i}') for i in range(3)]
    for m in ir:
        rolle_geben(m, Gremium.INTEGRITAETSRAT)
    antrag = antrag_einbringen(ir[1], **ANTRAG, ordnung=ordnung)
    beschluss = _fassen(client, ir[:1], antrag)  # eine Stimme: noch offen
    assert beschluss.status == BeschlussStatus.OFFEN
    seite = Client().get(reverse('gremien:beschluss', args=[beschluss.nummer])).content.decode()
    assert 'Personen beschlossen' not in seite and SATZ not in seite  # die Antragstellerin hat nicht gestimmt
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(status=BeschlussStatus.ENTSCHIEDEN, ergebnis='dafuer')
    feld = [f.name for f in GremienBeschluss._meta.get_fields() if 'festgehalten' in f.name]
    if feld:
        GremienBeschluss.objects.filter(pk=beschluss.pk).update(**{feld[0]: None})
    seite = Client().get(reverse('gremien:beschluss', args=[beschluss.nummer])).content.decode()
    assert 'Personen beschlossen' not in seite and 'Person beschlossen' not in seite
