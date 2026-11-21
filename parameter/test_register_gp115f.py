'''Registerwerte der Folgewelle 0.115.0: zehn bisherige Modulkonstanten stehen im Register, mit
Startwert, Wertbereich und Schema-Kennung; die beiden Drosseln werden ausgeschaltet ausgeliefert.'''

import pytest
from django.urls import reverse

from parameter import models as register_modul
from parameter.models import ERSTBESTAND, Parameter, erstbestand_sicherstellen, wertbereich
from plattform_core.schema import schema_key
from verfahren.models import Antrag, AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

NEU = {
    # Schlüssel: (Startwert, Wertbereich)
    'gremien-ki-je-stunde': ('0', (0, 100)),
    'beanstandung-je-stunde': ('0', (0, 1000)),
    'parlament-gruppe-hoechstzahl': ('60', (0, 500)),
    'umsetzung-seite-hoechstzahl': ('50', (0, 500)),
    'verwaltung-liste-seitengroesse': ('200', (10, 1000)),
    'mandatare-liste-seite': ('50', (10, 500)),
    'uebersicht-laufende-je-seite': ('50', (1, 500)),
    'faktenbasis-bestandsnachweis-warnanteil': ('100', (1, 100)),
    'aehnlichkeit-seite-zeilen': ('200', (50, 2000)),
    'audit-pruefstand-ueberfaellig-takte': ('2', (2, 31)),
}


def _register(schluessel, wert):
    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel=schluessel).update(wert=str(wert))


def test_die_zehn_werte_stehen_mit_startwert_bereich_und_kennung_im_register():
    werte = {e['schluessel']: e for e in ERSTBESTAND}
    for schluessel, (start, bereich) in NEU.items():
        eintrag = werte[schluessel]
        assert eintrag['wert'] == start, schluessel
        assert wertbereich(schluessel, eintrag['einheit']) == bereich, schluessel
        assert schema_key(schluessel), schluessel
        assert eintrag['beschreibung'] and eintrag['quelle'] and eintrag['gruppe'], schluessel
    for drossel in ('gremien-ki-je-stunde', 'beanstandung-je-stunde'):
        assert '0 = keine Grenze' in werte[drossel]['beschreibung'], drossel


def test_beschreibungen_nennen_alle_sammlungen_und_die_titelsuche():
    from faktenbasis.bestandsnachweis import SAMMLUNGEN

    werte = {e['schluessel']: e['beschreibung'] for e in ERSTBESTAND}
    nachweis = werte['faktenbasis-bestandsnachweis-hoechstzahl']
    assert len(SAMMLUNGEN) == 7
    for wort in ('Normstände', 'Dokumenttexte', 'Kundmachungsbelege', 'Personalstände', 'Ressorttabellen',
                 'VfGH', 'RIS-Änderungsseiten', 'sieben'):
        assert wort in nachweis, wort
    assert 'Titelsuche im Parlament' in werte['suche-treffer-hoechstzahl']


def test_altbestand_bekommt_die_neuen_eintraege_ohne_dass_ein_wert_sich_aendert(monkeypatch):
    '''Eine Datenbank im Stand 0.114.0: alle bisherigen Einträge, teils mit eigenen Werten, die beiden
    berichtigten Beschreibungen im alten Systemtext, eine von Hand geschriebene Beschreibung.'''
    alt = [e for e in ERSTBESTAND if e['schluessel'] not in NEU]
    monkeypatch.setattr(register_modul, 'ERSTBESTAND', alt)
    erstbestand_sicherstellen()
    monkeypatch.undo()
    assert not Parameter.objects.filter(schluessel__in=NEU).exists()
    alte_nachweis = register_modul.ALTE_SYSTEMBESCHREIBUNGEN['faktenbasis-bestandsnachweis-hoechstzahl'][0]
    alte_suche = register_modul.ALTE_SYSTEMBESCHREIBUNGEN['suche-treffer-hoechstzahl'][0]
    Parameter.objects.filter(schluessel='faktenbasis-bestandsnachweis-hoechstzahl').update(
        wert='1500', beschreibung=alte_nachweis[-1])
    Parameter.objects.filter(schluessel='suche-treffer-hoechstzahl').update(wert='12', beschreibung=alte_suche[-1])
    Parameter.objects.filter(schluessel='kacheln-abgeschlossen').update(wert='7', beschreibung='Eigener Text.')
    vorher = dict(Parameter.objects.values_list('schluessel', 'wert'))
    audit_vorher = AuditEintrag.objects.count()

    assert erstbestand_sicherstellen() == len(NEU)
    nachher = dict(Parameter.objects.values_list('schluessel', 'wert'))
    assert {k: nachher[k] for k in vorher} == vorher
    assert {k: nachher[k] for k in NEU} == {k: start for k, (start, _b) in NEU.items()}
    beschreibung = dict(Parameter.objects.values_list('schluessel', 'beschreibung'))
    werte = {e['schluessel']: e['beschreibung'] for e in ERSTBESTAND}
    assert beschreibung['faktenbasis-bestandsnachweis-hoechstzahl'] == werte['faktenbasis-bestandsnachweis-hoechstzahl']
    assert beschreibung['suche-treffer-hoechstzahl'] == werte['suche-treffer-hoechstzahl']
    assert beschreibung['kacheln-abgeschlossen'] == 'Eigener Text.'
    belege = [e.ereignis for e in AuditEintrag.objects.order_by('lfd')[audit_vorher:]]
    assert sorted(b['parameter'] for b in belege) == ['faktenbasis-bestandsnachweis-hoechstzahl',
                                                     'suche-treffer-hoechstzahl']
    assert all(b['typ'] == 'parameterbeschreibung_berichtigt' for b in belege)
    assert erstbestand_sicherstellen() == 0 and AuditEintrag.objects.count() == audit_vorher + 2


def test_die_ganz_alte_suchbeschreibung_wird_weiter_berichtigt():
    erstbestand_sicherstellen()
    alte = register_modul.ALTE_SYSTEMBESCHREIBUNGEN['suche-treffer-hoechstzahl'][0]
    Parameter.objects.filter(schluessel='suche-treffer-hoechstzahl').update(beschreibung=alte[0])
    erstbestand_sicherstellen()
    neu = next(e['beschreibung'] for e in ERSTBESTAND if e['schluessel'] == 'suche-treffer-hoechstzahl')
    assert Parameter.objects.get(schluessel='suche-treffer-hoechstzahl').beschreibung == neu


def test_uebersicht_liest_die_laufenden_je_seite_aus_dem_register(client, ordnung):  # noqa: F811
    autor = mitglied_anlegen('autor')
    for i in range(3):
        a = antrag_einbringen(autor, **{**ANTRAG, 'titel': f'Abstimmung {i}'}, ordnung=ordnung)
        Antrag.objects.filter(pk=a.pk).update(phase='abstimmung', stimmberechtigte_anzahl=5)
    _register('uebersicht-laufende-je-seite', 2)
    antwort = client.get(reverse('uebersicht:index'))
    assert len(antwort.context['abstimmungen']) == 2
    _register('uebersicht-laufende-je-seite', 0)  # außerhalb des Bereichs: wirkt wie 1, kein Serverfehler
    assert len(client.get(reverse('uebersicht:index')).context['abstimmungen']) == 1


@pytest.mark.parametrize('anteil, bestand, warnung', [(100, 9, False), (100, 10, True), (50, 5, True), (50, 4, False)])
def test_bestandsnachweis_warnt_ab_dem_registeranteil(monkeypatch, anteil, bestand, warnung):
    from faktenbasis import bestandsnachweis

    _register('faktenbasis-bestandsnachweis-hoechstzahl', 10)
    _register('faktenbasis-bestandsnachweis-warnanteil', anteil)
    monkeypatch.setattr(bestandsnachweis, 'bestandszahl', lambda: bestand)
    assert bestandsnachweis.grenzstand()['warnung'] is warnung


def test_aehnlichkeit_liest_die_zeilen_je_abruf_aus_dem_register(monkeypatch, ordnung):  # noqa: F811
    from django.db.models.query import QuerySet

    from verfahren import aehnlichkeit

    antrag_einbringen(mitglied_anlegen('autor'), **ANTRAG, ordnung=ordnung)
    gesehen = []
    original = QuerySet.iterator

    def iterator(self, chunk_size=None):
        gesehen.append(chunk_size)
        return original(self, chunk_size=chunk_size)

    monkeypatch.setattr(QuerySet, 'iterator', iterator)
    _register('aehnlichkeit-seite-zeilen', 75)
    assert list(aehnlichkeit._offene_zeilen())
    assert gesehen == [75]


def test_keine_der_drei_eigenen_konstanten_bleibt_stehen():
    import pathlib

    wurzel = pathlib.Path(__file__).resolve().parent.parent
    for datei, konstante in (
        ('uebersicht/views.py', 'LAUFENDE_JE_SEITE'),
        ('faktenbasis/bestandsnachweis.py', 'WARNANTEIL_PROZENT'),
        ('verfahren/aehnlichkeit.py', 'VERGLEICH_SEITE_ZEILEN'),
    ):
        assert konstante not in (wurzel / datei).read_text(encoding='utf-8'), datei
