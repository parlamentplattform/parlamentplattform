'''Folgewelle 0.115.0, Paket Oberfläche: Zuarbeit und Auflagen der ersten Welle an der Antragsseite,
an Kacheln und Ansichten des Pakets verfahren (GP-138, GP-049, GP-050, GP-003, GP-100, GP-078, GP-129,
GP-199 und Registerwerte).'''

from datetime import timedelta

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from verfahren.models import Antrag, antrag_einbringen, stimme_abgeben
from verfahren.test_siegel_stimmliste import _abstimmung, _zettel_einschleusen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _seite(client, antrag, **get):
    antwort = client.get(reverse('verfahren:antrag', args=[antrag.pk]), get)
    assert antwort.status_code == 200
    return antwort.content.decode()


# --- GP-138: angehaltene Auszählung und ausgewiesene Überzahl ---------------------------------------


def test_die_antragsseite_zeigt_den_befund_einer_angehaltenen_auszaehlung(client, ordnung):  # noqa: F811
    antrag, leute = _abstimmung(ordnung)
    _zettel_einschleusen(antrag)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    client.force_login(leute[4])

    inhalt = _seite(client, antrag)
    antrag.refresh_from_db()
    assert antrag.auszaehlung_angehalten() is not None
    assert 'id="auszaehlung-angehalten"' in inhalt and 'Auszählung angehalten' in inhalt
    assert 'Stimmzettel ohne Registerzeile: 1' in inhalt
    assert 'Stimmzettel: 4, Stimm-Ereignisse in der Audit-Kette: 3' in inhalt
    # Keine Abstimmen-Karte mehr, deren Knöpfe nichts bewirken; keine Namen im Befund
    assert 'id="abstimmen"' not in inhalt
    befund = inhalt.split('id="auszaehlung-angehalten"', 1)[1].split('</div>', 1)[0]
    assert all(m.anzeigename not in befund for m in leute)


def test_die_angehaltene_zustimmungswahl_bietet_kein_zustimmen_mehr(client, ordnung):  # noqa: F811
    import uuid

    from verfahren.models import BewerbungsZustimmung
    from verfahren.test_siegel_stimmliste import _wahl

    antrag, leute, (b1, _b2) = _wahl(ordnung)
    BewerbungsZustimmung._base_manager.bulk_create([BewerbungsZustimmung(bewerbung=b1, pseudonym=uuid.uuid4())])
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=60))
    client.force_login(leute[2])

    inhalt = _seite(client, antrag)
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung' and antrag.auszaehlung_angehalten() is not None
    assert 'Stimmzettel ohne Registerzeile: 1' in inhalt
    assert reverse('verfahren:kandidatur_zustimmen', args=[antrag.pk, b1.pk]) not in inhalt


def test_die_kachel_nennt_die_angehaltene_auszaehlung(ordnung):  # noqa: F811
    from verfahren.views import _kachel

    antrag, _leute = _abstimmung(ordnung)
    _zettel_einschleusen(antrag)
    ende = antrag.phase_beginn + timedelta(days=8)
    assert antrag.fortschreiben(ende) is False
    k = _kachel(antrag, ende)
    assert k['frist_abgelaufen'] and k['angehalten']
    html = render_to_string('verfahren/_kachel.html', {'k': k, 'ziel': '#feld-x', 'feld': 'x'})
    assert 'Auszählung angehalten' in html and 'wird ausgewertet' not in html


def test_die_kachel_ohne_halt_bleibt_wie_bisher(ordnung):  # noqa: F811
    from verfahren.views import _kachel

    antrag, _leute = _abstimmung(ordnung)
    ende = antrag.phase_beginn + timedelta(days=8)
    k = _kachel(antrag, ende)
    assert k['frist_abgelaufen'] and not k['angehalten']


def test_das_ergebnis_nennt_mehr_stimmen_als_festgestellte_stimmberechtigte(client, ordnung):  # noqa: F811
    from mitglieder.models import Identitaetsstufe, Mitglied

    leute = [mitglied_anlegen(f'u{i}') for i in range(3)]
    spaet = mitglied_anlegen('spaet', stufe=Identitaetsstufe.UNGEPRUEFT)
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    Mitglied.objects.filter(pk=spaet.pk).update(
        identitaetsstufe=Identitaetsstufe.GEPRUEFT, geprueft_seit=antrag.stimmberechtigung_stichtag
    )
    spaet.refresh_from_db()
    for m in [*leute, spaet]:
        stimme_abgeben(antrag, m, 'ja')
    assert antrag.fortschreiben(antrag.phase_beginn + timedelta(days=8)) is True

    inhalt = _seite(client, antrag)
    assert 'Mehr Stimmen als festgestellte Stimmberechtigte (4 zu 3)' in inhalt


def test_ein_ergebnis_ohne_abweichung_nennt_keine_ueberzahl(client, ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    assert antrag.fortschreiben(antrag.phase_beginn + timedelta(days=8)) is True
    inhalt = _seite(client, antrag)
    assert 'Mehr Stimmen als festgestellte' not in inhalt and 'Auszählung angehalten' not in inhalt
