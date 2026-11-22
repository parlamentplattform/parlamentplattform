'''Der Weg durch die Werkstatt im Archiv eines Antrags (Reste der Gesamtprüfung GP-008 und GP-011).

GP-008: Eine Zurückweisung legt die Entwurfsschleife mit dem Status „angenommen“ still. Das Archiv
nannte das „zur Endabstimmung übergeben“, obwohl nichts übergeben wurde; und es verschwieg, dass die
Frist des Koordinationsrats über einen Austauschantrag während einer aufgehobenen Zurückweisung ruhte.

GP-011: Bis 0.112 wurde die Begründung eines Urteils der Gruppe 2 mit den Namen der Prüfenden
gespeichert. Die Antragsseite liest sie seit 0.113 aus den Stimmen; das Archiv zeigte den alten Text
weiter — der Name überlebte dort Widerruf und Austritt.'''

import json

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Anlass, EntwurfsStatus, Pruefung
from gremien.test_integritaet import _austausch_zurueckgewiesen_und_aufgehoben, beschluss_fassen, rat
from gremien.test_pruefung import pruef_lage, stimme
from gremien.test_werkstatt import einreichen, ordnung, werkstatt_lage  # noqa: F401
from verfahren import archiv as archivkern

pytestmark = pytest.mark.django_db

RUHT = 'ruht — der Vorschlag wurde nicht übernommen'
UEBERGEBEN = 'zur Endabstimmung übergeben'


# --- GP-008 -----------------------------------------------------------------------------------------


def test_das_archiv_nennt_einen_ruhenden_entwurf_nicht_uebergeben(client, ordnung):  # noqa: F811
    leute = rat()
    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, 'Gesetzwidrig.')
    entwurf.refresh_from_db()
    antrag.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.ANGENOMMEN and not entwurf.vorschlag_uebernommen()
    (block,) = archivkern.entwurf_bloecke(antrag)
    assert str(block['status']) == RUHT
    (im_export,) = json.loads(archivkern.als_json(antrag))['entwurf']
    assert im_export['status'] == RUHT
    markdown = archivkern.als_markdown(antrag)
    assert RUHT in markdown and UEBERGEBEN not in markdown
    client.logout()
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    zone = seite[seite.index('class="archiv"'):]
    assert RUHT in zone and UEBERGEBEN not in zone


def test_ein_uebernommener_vorschlag_heisst_im_archiv_weiter_uebergeben(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import frist_verstreichen

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben_bis_zum_stand()
    entwurf.refresh_from_db()
    antrag.refresh_from_db()
    assert entwurf.vorschlag_uebernommen()
    (block,) = archivkern.entwurf_bloecke(antrag)
    assert str(block['status']) == UEBERGEBEN


def test_das_archiv_gibt_die_gehemmte_austauschfrist_aus(client, ordnung):  # noqa: F811
    antrag, _entwurf, pruefung, _korat, _urteil, _aufhebung = _austausch_zurueckgewiesen_und_aufgehoben(
        client, ordnung, 18
    )
    gehemmt = int(pruefung.frist_gehemmt.total_seconds())
    assert gehemmt > 17 * 86400
    (im_export,) = json.loads(archivkern.als_json(antrag))['entwurf'][0]['pruefungen']
    assert im_export['frist_gehemmt_sekunden'] == gehemmt
    assert im_export['austausch_frist'] == pruefung.austausch_frist.isoformat()
    frist = f'{timezone.localtime(pruefung.austausch_frist):%d.%m.%Y %H:%M}'
    zeile = next(z for z in archivkern.als_markdown(antrag).split('\n') if 'Koordinationsrat' in z)
    assert frist in zeile and 'gehemmt' in zeile


def test_ohne_hemmung_nennt_das_archiv_keine_gehemmte_frist(client, ordnung):  # noqa: F811
    '''Altbestand und der Regelfall: Die Spalte steht auf null — das Archiv sagt 0 und nennt bei einem
    Urteil, das kein Austauschantrag ist, keine Frist des Koordinationsrats.'''
    antrag, entwurf, _er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    for pruefer in gruppe2:
        stimme(client, beschluss, pruefer, 'zurueck', 'Kein Vergleichsangebot vorhanden.')
    antrag.refresh_from_db()
    (im_export,) = json.loads(archivkern.als_json(antrag))['entwurf'][0]['pruefungen']
    assert im_export['frist_gehemmt_sekunden'] == 0 and im_export['austausch_frist'] is None
    assert 'gehemmt' not in archivkern.als_markdown(antrag)


# --- GP-011 -----------------------------------------------------------------------------------------


def _altes_urteil_mit_namen(client, ordnung):  # noqa: F811
    '''Ein Urteil der Gruppe 2, dessen Begründung wie vor 0.113 gespeichert ist: mit den Namen.'''
    antrag, entwurf, _er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    petra, ohne = gruppe2
    stimme(client, beschluss, petra, 'zurueck', 'Die Vergabekriterien fehlen völlig.')
    stimme(client, beschluss, ohne, 'zurueck', 'Kein Vergleichsangebot vorhanden.')
    pruefung = Pruefung.objects.get(entwurf=entwurf)
    option = beschluss.name_von('zurueck')
    Pruefung.objects.filter(pk=pruefung.pk).update(
        begruendung=(
            f'Petra Probekind: {option} — Die Vergabekriterien fehlen völlig.\n\n'
            f'Mitglied {ohne.pk}: {option} — Kein Vergleichsangebot vorhanden.'
        )
    )
    antrag.refresh_from_db()
    return antrag, ohne


def test_das_archiv_zeigt_eine_alte_pruefbegruendung_ohne_namen(client, ordnung):  # noqa: F811
    antrag, ohne = _altes_urteil_mit_namen(client, ordnung)
    (pruefung,) = archivkern.entwurf_bloecke(antrag)[0]['pruefungen']
    for text in (pruefung['begruendung'], archivkern.als_json(antrag), archivkern.als_markdown(antrag)):
        assert 'Probekind' not in text and f'Mitglied {ohne.pk}' not in text
        assert 'Die Vergabekriterien fehlen völlig.' in text and 'Kein Vergleichsangebot vorhanden.' in text
    client.logout()
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    zone = seite[seite.index('class="archiv"'):]
    assert 'Probekind' not in zone and f'Mitglied {ohne.pk}' not in zone
    assert 'Die Vergabekriterien fehlen völlig.' in zone


def test_ein_vermerk_ohne_stimmen_bleibt_im_archiv_wie_er_ist(client, ordnung):  # noqa: F811
    '''Blieb die Prüfung ohne Ergebnis, gibt es keine Stimmbegründungen — der Vermerk steht weiter da.'''
    from datetime import timedelta

    antrag, entwurf, _er, _gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    beschluss.frist = timezone.now() - timedelta(minutes=1)
    beschluss.save(update_fields=['frist'])
    entwurf.fortschreiben(antrag)
    antrag.refresh_from_db()
    (pruefung,) = archivkern.entwurf_bloecke(antrag)[0]['pruefungen']
    assert pruefung['begruendung'].startswith('Die Prüfung der Gruppe 2 blieb ohne Ergebnis')
