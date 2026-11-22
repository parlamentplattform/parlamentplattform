"""GP-118: Schreiben und Audit-Eintrag in einer Transaktion — scheitert der Eintrag in die Protokollkette,
bleibt auch die Handlung nicht bestehen (Sonde F, Zeilen F5)."""

from datetime import date, timedelta
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from mandatare import models as mm
from mandatare.models import Aufgabe, Bericht, Mandat
from mandatare.sitzung import sitzung_beginnen
from mandatare.test_mandatare import PNG_MINI, admin_anlegen, mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren.models import AuditEintrag, Kommentar
from verfahren.models import Meldung as BeitragsMeldung
from verfahren.test_vertrauensfrage import altmandat, einbringen  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

AKTION = reverse('mandatare:mein_aktion')
VERWALTUNG = reverse('mandatare:verwaltung_aktion')


def _scheiternd(tu):
    with mock.patch.object(AuditEintrag, 'anhaengen', side_effect=IntegrityError('Audit scheitert')):
        return tu()


@pytest.fixture
def welt(client):
    heute = timezone.localdate()
    anna = mitglied_anlegen('gp118anna')
    mandat = mandat_anlegen(anna, angetreten=heute - timedelta(days=120))
    alt = sitzungstag(mandat, heute - timedelta(days=2), titel='Alte Sitzung')
    admin = admin_anlegen('gp118admin')
    client.raise_request_exception = False
    return {'anna': anna, 'mandat': mandat, 'alt': alt, 'admin': admin, 'heute': heute, 'client': client}


def _vormonat(heute: date) -> date:
    return (heute.replace(day=1) - timedelta(days=1)).replace(day=1)


FAELLE = {
    'Instant-Report': (
        'anna',
        lambda w: (AKTION, {'aktion': 'report', 'mandat': w['mandat'].pk, 'titel': 'Report X',
                            'frist_datum': (w['heute'] + timedelta(days=3)).isoformat()}),
        lambda w: Aufgabe.objects.count(),
    ),
    'Aufgabenstatus': (
        'anna',
        lambda w: (AKTION, {'aktion': 'aufgabe_status', 'mandat': w['mandat'].pk, 'aufgabe': w['alt'].pk, 'status': 'erledigt'}),
        lambda w: Aufgabe.objects.get(pk=w['alt'].pk).status,
    ),
    'Vorstellung': (
        'anna',
        lambda w: (AKTION, {'aktion': 'vorstellung', 'mandat': w['mandat'].pk, 'vorstellung': 'Neu'}),
        lambda w: Mandat.objects.get(pk=w['mandat'].pk).vorstellung,
    ),
    'Foto': (
        'anna',
        lambda w: (AKTION, {'aktion': 'foto', 'mandat': w['mandat'].pk, 'foto': SimpleUploadedFile('f.png', PNG_MINI, 'image/png')}),
        lambda w: Mandat.objects.get(pk=w['mandat'].pk).foto_typ,
    ),
    'Sammelbericht': (
        'anna',
        lambda w: (AKTION, {'aktion': 'sammelbericht', 'mandat': w['mandat'].pk, 'aufgabe': w['alt'].pk, 'text': 'Bericht'}),
        lambda w: Bericht.objects.count(),
    ),
    'Monatsbericht': (
        'anna',
        lambda w: (AKTION, {'aktion': 'monatsbericht', 'mandat': w['mandat'].pk, 'monat': _vormonat(w['heute']).isoformat(), 'text': 'Bericht'}),
        lambda w: Bericht.objects.count(),
    ),
    'Verwaltung: Aufgabe': (
        'admin',
        lambda w: (VERWALTUNG, {'aktion': 'aufgabe', 'mandat': w['mandat'].pk, 'titel': 'V-Aufgabe'}),
        lambda w: Aufgabe.objects.count(),
    ),
    'Verwaltung: Rueckgabezusage': (
        'admin',
        lambda w: (VERWALTUNG, {'aktion': 'rueckgabezusage', 'mandat': w['mandat'].pk, 'wert': 'abgegeben'}),
        lambda w: Mandat.objects.get(pk=w['mandat'].pk).rueckgabezusage,
    ),
    'Verwaltung: lit h': (
        'admin',
        lambda w: (VERWALTUNG, {'aktion': 'lit_h', 'mandat': w['mandat'].pk, 'datum': w['heute'].isoformat()}),
        lambda w: Mandat.objects.get(pk=w['mandat'].pk).mandatsvereinbarung_lit_h_am,
    ),
    'Verwaltung: Mandat anlegen': (
        'admin',
        lambda w: (VERWALTUNG, {'aktion': 'anlegen', 'mitglied': w['admin'].pk, 'bezeichnung': 'Gemeinderat', 'ebene': 'gemeinde',
                                'gebiet': 'X', 'angetreten': w['heute'].isoformat()}),
        lambda w: Mandat.objects.count(),
    ),
    'Verwaltung: Mandat beenden': (
        'admin',
        lambda w: (VERWALTUNG, {'aktion': 'beenden', 'mandat': w['mandat'].pk}),
        lambda w: Mandat.objects.get(pk=w['mandat'].pk).beendet,
    ),
}


@pytest.mark.parametrize('name', list(FAELLE))
def test_gescheiterter_audit_eintrag_laesst_keine_handlung_stehen(welt, name):
    wer, anfrage, zaehlen = FAELLE[name]
    client = welt['client']
    client.force_login(welt[wer])
    url, daten = anfrage(welt)
    # Gegenprobe ohne Störung wäre eine andere Welt — hier zählt nur: vorher gleich nachher
    vorher = zaehlen(welt)
    antwort = _scheiternd(lambda: client.post(url, daten))
    assert antwort.status_code == 500
    assert zaehlen(welt) == vorher, name


def test_gescheiterter_audit_eintrag_laesst_keine_meldung_im_sitzungschat_stehen(welt):
    mandat = welt['mandat']
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat), punkte=['Budget'])
    beitrag = Kommentar.objects.create(sitzung=sitzung, mitglied=welt['admin'], text='Beitrag', phase='sitzung',
                                       erstellt_am=timezone.now())
    melder = mitglied_anlegen('gp118carl')
    client = welt['client']
    client.force_login(melder)
    url = reverse('mandatare:live_beitrag_aktion', args=[mandat.pk, sitzung.pk, beitrag.pk])
    antwort = _scheiternd(lambda: client.post(url, {'aktion': 'melden', 'grund': 'sonst'}))
    assert antwort.status_code == 500
    assert BeitragsMeldung.objects.count() == 0


def test_gescheiterter_audit_eintrag_laesst_keine_stellungnahme_stehen(ordnung, altmandat):  # noqa: F811
    vf = einbringen(mitglied_anlegen('gp118bea'), altmandat, ordnung).vertrauensfrage
    with pytest.raises(IntegrityError):
        _scheiternd(lambda: mm.stellungnahme_abgeben(vf, altmandat.mitglied, 'Meine Sicht.'))
    assert mm.Stellungnahme.objects.count() == 0


def test_ohne_stoerung_steht_die_handlung_samt_audit(welt):
    client = welt['client']
    client.force_login(welt['admin'])
    url, daten = FAELLE['Verwaltung: Mandat beenden'][1](welt)
    assert client.post(url, daten).status_code == 302
    assert Mandat.objects.get(pk=welt['mandat'].pk).beendet == welt['heute']
    assert AuditEintrag.objects.filter(ereignis__typ='mandat_beendet').count() == 1


# ── GP-129 (Folgewelle): jede Stelle der App steht mit ihrem Audit-Eintrag in einer Transaktion ──


def test_gescheiterter_audit_eintrag_laesst_keine_bestaetigung_stehen(welt):
    """`Mandat.bestaetigen` wird auch von außerhalb der App gerufen (Wahl in einen Rat): Die Methode fasst
    sich selbst. Scheitert der Eintrag, bleibt die Kandidatursperre — in der Datenbank und am Objekt."""
    mandat = welt['mandat']
    with pytest.raises(IntegrityError):
        _scheiternd(lambda: mandat.bestaetigen('wahl'))
    assert Mandat.objects.get(pk=mandat.pk).bestaetigt_am is None
    assert mandat.bestaetigt_am is None
    assert mandat.bestaetigen('wahl') is True  # ohne Störung gelingt es danach — einmal
    assert Mandat.objects.get(pk=mandat.pk).bestaetigt_am is not None and mandat.bestaetigen('wahl') is False


def test_gescheiterter_audit_eintrag_laesst_keine_rueckgabezusage_stehen(welt):
    mandat = welt['mandat']
    vorher = Mandat.objects.get(pk=mandat.pk).rueckgabezusage
    with pytest.raises(IntegrityError):
        _scheiternd(lambda: mm.rueckgabezusage_vermerken(mandat, 'abgegeben'))
    assert Mandat.objects.get(pk=mandat.pk).rueckgabezusage == vorher


def test_gescheiterter_audit_eintrag_laesst_keine_bestaetigung_durch_wahl_stehen(welt):
    """Die Verwaltungshandlung zur Bestätigung (lit f Z 3) über die Ansicht."""
    mandat = welt['mandat']
    Mandat.objects.filter(pk=mandat.pk).update(vertrauen_entzogen_am=timezone.now() - timedelta(days=40))
    assert Mandat.objects.get(pk=mandat.pk).kandidatursperre
    client = welt['client']
    client.force_login(welt['admin'])
    antwort = _scheiternd(lambda: client.post(VERWALTUNG, {'aktion': 'bestaetigung_durch_wahl', 'mandat': mandat.pk}))
    assert antwort.status_code == 500
    assert Mandat.objects.get(pk=mandat.pk).bestaetigt_am is None


def test_gescheiterter_audit_eintrag_laesst_keine_frage_als_beantwortet_stehen(welt):
    """Die dritte Handlung von `live_beitrag_aktion`: „beantwortet“ durch den Mandatar der Sitzung."""
    mandat = welt['mandat']
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat), punkte=['Budget'])
    frage = Kommentar.objects.create(sitzung=sitzung, mitglied=welt['admin'], text='Frage', phase='sitzung',
                                     erstellt_am=timezone.now())
    client = welt['client']
    client.force_login(welt['anna'])
    url = reverse('mandatare:live_beitrag_aktion', args=[mandat.pk, sitzung.pk, frage.pk])
    antwort = _scheiternd(lambda: client.post(url, {'aktion': 'beantwortet'}))
    assert antwort.status_code == 500
    assert Kommentar.objects.get(pk=frage.pk).beantwortet_am is None


def test_keine_audit_stelle_der_app_wartet_noch_auf_ihre_fassung():
    """Die Eigenschaft, die bleibt: Jeder Aufruf von `AuditEintrag.anhaengen` in mandatare/ ist lexikalisch
    gefasst oder wird nur aus gefassten Stellen gerufen — keiner ist bloß „gemeldet“ oder „offen“."""
    from tools import audit_klammer

    eigene = [s for s in audit_klammer.stellen() if s.datei.split('/')[0] == 'mandatare']
    assert eigene
    ungefasst = [f'{s.datei}:{s.zeile} {s.funktion}' for s in eigene if s.einstufung not in ('atomic', 'aufrufer')]
    assert ungefasst == []
