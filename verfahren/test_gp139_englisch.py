'''GP-139 (ASR-21, OCR-20): Die englische Oberfläche zeigte Ergebnisbegründung, Lebensbereiche, Suche und
Chat-Sperre deutsch.

Geprüft wird mit einer Pseudo-Übersetzung wie in gremien/test_sprache.py: Jeder Text, der durch gettext
läuft, erscheint als „EN[…]“. Was danach noch an Buchstaben dasteht, ist nicht übersetzbar. Der deutsche
Ergebnissatz bleibt Urtext in Audit und Export; die Anzeige baut ihn aus den Zahlen und einem übersetzbaren
Muster und ist auf Deutsch Zeichen für Zeichen derselbe Satz.'''

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.conf import settings
from django.urls import reverse
from django.utils import translation

from plattform_core import tally
from plattform_core.policy import Policy
from verfahren.models import Antrag, Kategorie, antrag_einbringen
from verfahren.templatetags.lebensbereiche import ERSTBESTAND_NAMEN, anzeigename
from verfahren.templatetags.phasen import ergebnis_satz
from verfahren.test_siegel_nenner import _entschieden
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

INNEN = re.compile(r'EN\[[^\[\]]*\]')
#: Die Zustimmungswahl liest nur die Mindestbeteiligung; ohne Schwelle ist auch „keine Zustimmung“ erreichbar.
OHNE_SCHWELLE = SimpleNamespace(mindestbeteiligung=0.0)


@pytest.fixture
def pseudo(monkeypatch):
    '''Jede Übersetzung wird sichtbar: gettext liefert „EN[msgid]“.'''
    echt = translation._trans.ngettext
    monkeypatch.setattr(translation._trans, 'gettext', lambda m: f'EN[{m}]', raising=False)
    monkeypatch.setattr(translation._trans, 'ngettext', lambda s, p, n: f'EN[{echt(s, p, n)}]', raising=False)


def _rest(text: str) -> str:
    '''Entfernt alle (auch verschachtelten) EN[…]-Marken — was bleibt, lief nicht durch gettext.'''
    vorher = None
    while vorher != text:
        vorher, text = text, INNEN.sub('', text)
    return text


def _policy(mindest=0.05, basis='ja_nein'):
    return Policy(
        id='t', version=1, unterstuetzung_schwelle=1, unterstuetzung_frist_tage=14, beratung_tage=21,
        abstimmung_tage=7, mindestbeteiligung=mindest, mehrheitsbasis=basis,
    )


def _stimmen(ja, nein, enthaltung):
    werte = ['ja'] * ja + ['nein'] * nein + ['enthaltung'] * enthaltung
    return [(f'p{i}', w) for i, w in enumerate(werte)]


SACHFAELLE = [
    # (ja, nein, enthaltung, berechtigte, mindest, basis, leer, fall)
    (0, 0, 0, 0, 0.05, 'ja_nein', True, tally.FALL_LEERER_KREIS),
    (1, 0, 0, 100, 0.05, 'ja_nein', False, tally.FALL_BETEILIGUNG_VERFEHLT),
    (0, 0, 0, 21, 0.05, 'ja_nein', False, tally.FALL_BETEILIGUNG_VERFEHLT),
    (0, 0, 0, 20, 0.05, 'abgegeben', False, tally.FALL_BETEILIGUNG_VERFEHLT),
    (1, 0, 0, 200, 0.125, 'ja_nein', False, tally.FALL_BETEILIGUNG_VERFEHLT),
    (3, 1, 1, 5, 0.05, 'ja_nein', False, tally.FALL_ANGENOMMEN),
    (3, 1, 1, 5, 0.05, 'abgegeben', False, tally.FALL_ANGENOMMEN),
    (1, 1, 3, 5, 0.05, 'ja_nein', False, tally.FALL_KEINE_MEHRHEIT),
    (2, 1, 2, 5, 0.05, 'abgegeben', False, tally.FALL_KEINE_MEHRHEIT),
]


def _sach(ja, nein, enthaltung, berechtigte, mindest, basis, leer):
    return tally.auszaehlen(
        _stimmen(ja, nein, enthaltung), berechtigte, _policy(mindest, basis), leerer_oertlicher_kreis=leer
    )


def _wahlen():
    '''Alle fünf Ausgänge der Zustimmungswahl.'''
    p = _policy()
    return [
        (tally.personenwahl_auszaehlen([], [], 10, p), tally.FALL_KEINE_BEWERBUNG),
        (tally.personenwahl_auszaehlen([], [7], 0, p, leerer_oertlicher_kreis=True), tally.FALL_LEERER_KREIS),
        (tally.personenwahl_auszaehlen([('a', 7), ('b', 7), ('b', 8)], [7, 8], 10, p), tally.FALL_GEWAEHLT),
        (tally.personenwahl_auszaehlen([('a', 7)], [7], 21, p), tally.FALL_BETEILIGUNG_VERFEHLT),
        (tally.personenwahl_auszaehlen([('a', 7)], [7], 8, _policy(0.125)), tally.FALL_GEWAEHLT),
        (tally.personenwahl_auszaehlen([], [7], 2, OHNE_SCHWELLE), tally.FALL_KEINE_ZUSTIMMUNG),
    ]


# --- Kern: der Fall neben dem Satz, Rechnung unverändert -------------------------------------------------


@pytest.mark.parametrize('fall', SACHFAELLE)
def test_die_sachauszaehlung_nennt_ihren_fall(fall):
    *eingabe, erwartet = fall
    assert _sach(*eingabe).fall == erwartet


def test_die_zustimmungswahl_nennt_ihren_fall():
    for wahl, erwartet in _wahlen():
        assert wahl.fall == erwartet
    assert tally.personenwahl_auszaehlen([('a', 7)], [7], 3, _policy(0.5)).fall == tally.FALL_BETEILIGUNG_VERFEHLT


def test_die_fassung_der_auszaehlregel_bleibt():
    assert tally.VERSION == 3


# --- Anzeige: deutsch Zeichen für Zeichen gleich, englisch ohne deutschen Rest ----------------------------


@pytest.mark.parametrize('fall', SACHFAELLE)
def test_der_deutsche_ergebnissatz_bleibt_zeichengleich(fall):
    *eingabe, _erwartet = fall
    a = _sach(*eingabe)
    with translation.override('de'):
        assert ergebnis_satz(a) == a.begruendung


def test_der_deutsche_wahlsatz_bleibt_zeichengleich():
    wahlen = [w for w, _f in _wahlen()]
    with translation.override('de'):
        for wahl in wahlen:
            assert ergebnis_satz(wahl) == wahl.begruendung


@pytest.mark.parametrize('fall', SACHFAELLE)
def test_der_englische_ergebnissatz_hat_keinen_deutschen_rest(fall, pseudo):
    *eingabe, _erwartet = fall
    a = _sach(*eingabe)
    with translation.override('en'):
        satz = ergebnis_satz(a)
    assert satz != a.begruendung
    assert not re.search(r'[A-Za-zÄÖÜäöüß]', _rest(satz)), satz


def test_der_englische_wahlsatz_hat_keinen_deutschen_rest(pseudo):
    wahlen = [w for w, _f in _wahlen()]
    with translation.override('en'):
        for wahl in wahlen:
            satz = ergebnis_satz(wahl)
            assert not re.search(r'[A-Za-zÄÖÜäöüß]', _rest(satz)), satz


def test_der_anteil_steht_englisch_mit_punkt():
    a = _sach(1, 0, 0, 200, 0.125, 'ja_nein', False)
    with translation.override('en'):
        assert '12.5 %' in ergebnis_satz(a)
    with translation.override('de'):
        assert '12,5 %' in ergebnis_satz(a)


def test_ohne_fall_bleibt_der_gespeicherte_satz():
    '''Ein Objekt ohne Fall (fremde Quelle) zeigt seinen Satz unverändert, statt zu raten.'''

    class Alt:
        begruendung = 'Alter Satz.'

    assert ergebnis_satz(Alt()) == 'Alter Satz.'


# --- Antragsseite: Ergebniskarte und Lebensbereich-Chip ----------------------------------------------------


def _baum():
    wurzel = Kategorie.objects.create(slug='gesellschaftliches-zusammenleben', name='Das gesellschaftliche Zusammenleben')
    saeule = Kategorie.objects.create(slug='saeule-sicherheit-soziales', name='Sicherheit & Soziales Fundament', eltern=wurzel)
    bereich = Kategorie.objects.create(slug='bereich-gesundheitswesen-praevention', name='Gesundheitswesen & Prävention', eltern=saeule)
    return Kategorie.objects.create(slug='gesundheit-pflege', name='Gesundheit & Pflege', eltern=bereich)


def test_die_englische_antragsseite_zeigt_ergebnis_und_chip_uebersetzt(client, ordnung, pseudo):  # noqa: F811
    leute = [mitglied_anlegen(f'e{i}') for i in range(4)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.kategorien.add(_baum())
    _entschieden(client, antrag, leute)
    urtext = Antrag.objects.get(pk=antrag.pk).auszaehlen().begruendung
    assert urtext.startswith('Angenommen:')

    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk]), HTTP_ACCEPT_LANGUAGE='en').content.decode()
    # Die Ergebniskarte; die Audit-Spur im Archiv zeigt den Urtext der Kette und bleibt, wie sie ist
    karte = seite.split('<h3>EN[Ergebnis]</h3>')[1].split('</div>')[0]
    assert urtext not in karte
    assert '<strong>EN[Angenommen: EN[Ja 4 : Nein 0], Enthaltungen 0; Beteiligung 4/4 (§ 5 Abs 4).]</strong>' in karte
    assert '>Gesundheit &amp; Pflege<' not in seite
    assert '>EN[Gesundheit &amp; Pflege]</a>' in seite
    assert 'title="EN[Sicherheit &amp; Soziales Fundament] › EN[Gesundheitswesen &amp; Prävention] › EN[Gesundheit &amp; Pflege]"' in seite


def test_audit_und_export_behalten_den_deutschen_urtext(client, ordnung, pseudo):  # noqa: F811
    from verfahren.models import AuditEintrag

    leute = [mitglied_anlegen(f'u{i}') for i in range(4)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    with translation.override('en'):
        daten = _entschieden(client, antrag, leute)
    urtext = 'Angenommen: Ja 4 : Nein 0, Enthaltungen 0; Beteiligung 4/4 (§ 5 Abs 4).'
    gruende = [
        e.ereignis.get('grund')
        for e in AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel')
    ]
    assert urtext in gruende
    assert urtext in str(daten)


# --- Lebensbereiche: Verzeichnis, Anzeige, Suche ------------------------------------------------------------


def _yaml_namen() -> set[str]:
    namen: set[str] = set()

    def geh(eintrag):
        namen.add(eintrag['name'])
        for kind in eintrag.get('unterkategorien', []):
            geh(kind)

    for datei in sorted((Path(settings.BASE_DIR) / 'policies').glob('kategorien-v*.yaml')):
        for eintrag in yaml.safe_load(datei.read_text(encoding='utf-8'))['lebensbereiche']:
            geh(eintrag)
    return namen


def test_das_verzeichnis_fuehrt_genau_die_namen_des_erstbestands():
    assert set(ERSTBESTAND_NAMEN) == _yaml_namen()


def test_frei_gepflegte_namen_bleiben_unveraendert(pseudo):
    with translation.override('en'):
        assert anzeigename('Energie') == 'EN[Energie]'
        assert anzeigename('Energiewende in unserer Gemeinde') == 'Energiewende in unserer Gemeinde'


@pytest.fixture
def englisch(monkeypatch):
    '''Eine kleine englische Fassung der Lebensbereiche — die übrigen Texte wie die Pseudo-Übersetzung.'''
    woerter = {
        'Energie': 'Energy',
        'Erneuerbare Energie': 'Renewable energy',
        'Das gesellschaftliche Zusammenleben': 'Living together in society',
    }
    echt = translation._trans.ngettext
    monkeypatch.setattr(translation._trans, 'gettext', lambda m: woerter.get(m, f'EN[{m}]'), raising=False)
    monkeypatch.setattr(translation._trans, 'ngettext', lambda s, p, n: f'EN[{echt(s, p, n)}]', raising=False)


def _energiebaum():
    wurzel = Kategorie.objects.create(slug='gesellschaftliches-zusammenleben', name='Das gesellschaftliche Zusammenleben')
    energie = Kategorie.objects.create(slug='energie', name='Energie', eltern=wurzel)
    Kategorie.objects.create(slug='erneuerbare-energie', name='Erneuerbare Energie', eltern=energie)
    Kategorie.objects.create(slug='energiewende-ort', name='Energiewende in unserer Gemeinde', eltern=energie)


def _treffer(seite: str) -> list[str]:
    return re.findall(r'class="treffer-link" href="\?fach=([a-z-]+)#', seite)


def test_energy_findet_energie(client, englisch):
    _energiebaum()
    seite = client.get('/parlament/?suche=energy', HTTP_ACCEPT_LANGUAGE='en').content.decode()
    assert _treffer(seite) == ['energie', 'erneuerbare-energie']
    assert '<strong>Energy</strong>' in seite
    assert '<strong>Renewable energy</strong>' in seite
    assert '<strong>Energie</strong>' not in seite


def test_die_suche_findet_auch_den_deutschen_namen(client, englisch):
    _energiebaum()
    seite = client.get('/parlament/?suche=Energie', HTTP_ACCEPT_LANGUAGE='en').content.decode()
    assert set(_treffer(seite)) == {'energie', 'erneuerbare-energie', 'energiewende-ort'}
    assert '<strong>Energiewende in unserer Gemeinde</strong>' in seite


def test_die_deutsche_suche_bleibt_wie_bisher(client):
    _energiebaum()
    with translation.override('de'):
        seite = client.get('/parlament/?suche=energie').content.decode()
    assert set(_treffer(seite)) == {'energie', 'erneuerbare-energie', 'energiewende-ort'}
    assert '<strong>Energie</strong>' in seite
    assert client.get('/parlament/?suche=energy').content.decode().count('class="treffer-link"') == 0


def test_der_faecher_zeigt_die_lebensbereiche_englisch(client, pseudo):
    _energiebaum()
    seite = client.get('/parlament/?fach=energie', HTTP_ACCEPT_LANGUAGE='en').content.decode()
    feld = seite.split('id="feld-favoriten"')[1].split('</section>')[0]
    assert 'EN[Erneuerbare Energie]' in feld
    assert '>Erneuerbare Energie<' not in feld
    assert '>Energie<' not in feld


# --- Chat-Sperre ---------------------------------------------------------------------------------------------


def test_die_chat_sperre_ist_uebersetzbar(ordnung, pseudo):  # noqa: F811
    from verfahren.chat import ChatGesperrt, beitrag_schreiben

    anna = mitglied_anlegen('anna')
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(phase='verfallen')
    antrag.refresh_from_db()
    with translation.override('en'), pytest.raises(ChatGesperrt) as fehler:
        beitrag_schreiben(antrag, anna, 'Ein Beitrag.')
    assert str(fehler.value).startswith('EN[') and not _rest(str(fehler.value)).strip()
