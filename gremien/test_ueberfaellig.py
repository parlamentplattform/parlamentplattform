"""GP-025, Rest aus dem Gegenlesen: „überfällig seit“ auch im Ratsbereich für jeden Beschluss mit
verstrichener Umsetzungsfrist — nicht nur für die zwölf zuletzt entschiedenen — und auf „Mein Gremium“
für die Person, der die Umsetzung zugewiesen ist.

Gezeigt wird nur, was die öffentliche Beschlussseite schon zeigt (Zuweisung, Frist, „überfällig seit“).
Die Fristen liegen fest in der Vergangenheit; der Test hängt nicht am heutigen Datum."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import JA_NEIN, BeschlussStatus, GremienBeschluss, Gremium
from gremien.test_koordination import korat
from gremien.test_werkstatt import rolle_geben
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

ALT = datetime(2024, 3, 1, 12, tzinfo=timezone.get_current_timezone())


def _entschieden(gremium, von, gegenstand, entschieden_am, **felder):
    """Ein entschiedener Beschluss wie aus dem Altbestand: Zuweisung und Frist direkt am Beschluss."""
    return GremienBeschluss.objects.create(
        gremium=gremium, gegenstand=gegenstand, optionen=JA_NEIN, angelegt_von=von, angelegt_am=entschieden_am,
        frist=entschieden_am, status=BeschlussStatus.ENTSCHIEDEN, ergebnis='dafuer', entschieden_am=entschieden_am,
        **felder,
    )


def test_der_ratsbereich_zeigt_auch_aeltere_ueberfaellige_beschluesse(client):
    leute = korat()
    alt = _entschieden(
        Gremium.KOORDINATIONSRAT, leute[0], 'Protokollvorlage überarbeiten', ALT,
        umsetzung_durch=leute[1], umsetzung_frist=date(2024, 4, 1),
    )
    for i in range(13):  # dreizehn jüngere Entscheidungen verdrängen ihn aus den zwölf zuletzt entschiedenen
        _entschieden(Gremium.KOORDINATIONSRAT, leute[0], f'Jüngere Sache {i}', ALT + timedelta(days=30 + i))
    client.force_login(leute[2])
    html = client.get(reverse('gremien:koordination')).content.decode()
    assert alt.nummer in html and 'Protokollvorlage überarbeiten' in html
    assert 'überfällig seit 02.04.2024' in html


def test_ein_beschluss_ohne_verstrichene_frist_rueckt_nicht_nach_vorn(client):
    leute = korat()
    ohne_frist = _entschieden(Gremium.KOORDINATIONSRAT, leute[0], 'Ganz alte Sache', ALT)
    for i in range(13):
        _entschieden(Gremium.KOORDINATIONSRAT, leute[0], f'Jüngere Sache {i}', ALT + timedelta(days=30 + i))
    client.force_login(leute[2])
    html = client.get(reverse('gremien:koordination')).content.decode()
    assert ohne_frist.nummer not in html


def test_mein_gremium_zeigt_der_zugewiesenen_person_ihre_ueberfaelligen_umsetzungen(client):
    leute = korat()
    beschluss = _entschieden(
        Gremium.KOORDINATIONSRAT, leute[0], 'Protokollvorlage überarbeiten', ALT,
        umsetzung_durch=leute[1], umsetzung_frist=date(2024, 4, 1),
    )
    # Eine Rolle allein führte bisher ohne Umweg in den Bereich — mit einer überfälligen Umsetzung nicht.
    client.force_login(leute[1])
    antwort = client.get(reverse('gremien:mein'))
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert reverse('gremien:beschluss', args=[beschluss.nummer]) in html
    assert 'überfällig seit 02.04.2024' in html
    assert reverse('gremien:koordination') in html  # der Weg in den Bereich bleibt
    # Wer nichts Überfälliges zugewiesen hat, geht wie bisher direkt in den Bereich.
    client.force_login(leute[2])
    assert client.get(reverse('gremien:mein')).url == reverse('gremien:koordination')


def test_mein_gremium_zeigt_keine_fremden_und_keine_offenen_fristen(client):
    leute = korat()
    andere = mitglied_anlegen('andere')
    rolle_geben(andere, Gremium.INTEGRITAETSRAT)
    _entschieden(
        Gremium.KOORDINATIONSRAT, leute[0], 'Fremde Umsetzung', ALT,
        umsetzung_durch=leute[1], umsetzung_frist=date(2024, 4, 1),
    )
    _entschieden(
        Gremium.INTEGRITAETSRAT, leute[0], 'Noch nicht fällig', ALT,
        umsetzung_durch=andere, umsetzung_frist=date(2999, 12, 31),
    )
    client.force_login(andere)
    assert client.get(reverse('gremien:mein')).url == reverse('gremien:integritaet')
