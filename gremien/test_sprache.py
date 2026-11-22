"""GP-039: Englische Seiten der Räte zeigten deutsche Optionen, Anlässe, Prüfpunkte und Bereichstexte.

Die Texte waren nicht zur Übersetzung markiert oder kamen aus gespeichertem JSON (Optionsnamen), deshalb
bemerkte der Katalogwächter nichts. Geprüft wird hier mit einer Pseudo-Übersetzung: Jeder Text, der durch
gettext läuft, erscheint als „EN[…]“. Was danach noch deutsch dasteht, ist nicht übersetzbar — ganz gleich,
ob der Katalog den Text schon kennt (der Katalog wird bei der Zusammenführung gepflegt)."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import translation

from gremien.models import Anlass, Fachliste, GremienBeschluss, Gremium, standard_ende
from gremien.test_pruefung import pruef_lage
from gremien.test_werkstatt import mitglied_anlegen, ordnung, rolle_geben  # noqa: F401

pytestmark = pytest.mark.django_db

MARKE = re.compile(r'EN\[[^\]]*\]')


@pytest.fixture
def pseudo(monkeypatch):
    """Jede Übersetzung wird sichtbar: gettext liefert „EN[msgid]“."""
    echt = {name: getattr(translation._trans, name) for name in ('gettext', 'ngettext', 'pgettext', 'npgettext')}
    monkeypatch.setattr(translation._trans, 'gettext', lambda m: f'EN[{m}]', raising=False)
    monkeypatch.setattr(
        translation._trans, 'ngettext', lambda s, p, n: f'EN[{echt["ngettext"](s, p, n)}]', raising=False
    )
    monkeypatch.setattr(translation._trans, 'pgettext', lambda c, m: f'EN[{m}]', raising=False)
    monkeypatch.setattr(
        translation._trans, 'npgettext', lambda c, s, p, n: f'EN[{echt["ngettext"](s, p, n)}]', raising=False
    )


def _unuebersetzt(html: str) -> str:
    return MARKE.sub('', html)


def _ir(n=3):
    leute = [mitglied_anlegen(f'ir{i}') for i in range(n)]
    for m in leute:
        rolle_geben(m, Gremium.INTEGRITAETSRAT)
    return leute


def _seite(adresse, als=None) -> str:
    c = Client()
    if als is not None:
        c.force_login(als)
    antwort = c.get(adresse)
    assert antwort.status_code == 200, adresse
    return _unuebersetzt(antwort.content.decode())


def test_die_seiten_der_raete_enthalten_keinen_unuebersetzbaren_text(client, ordnung, pseudo):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    ir = _ir()
    bw = mitglied_anlegen('bw0')
    rolle_geben(bw, Gremium.BERICHTSWESENRAT)
    Fachliste.objects.create(mitglied=mitglied_anlegen('fachfrau'))
    Fachliste.objects.create(mitglied=ir[0])  # unvereinbar: Mitglied des Integritätsrats

    pruefseite = _seite(reverse('gremien:pruefung'), gruppe2[0])
    for text in (
        'validieren', 'mit Begründung zurückgeben', 'Austausch bei Gruppe 1 beantragen',
        'Interessenbindungen der Gruppe 1', 'Bieterkreis nachvollziehbar', 'Schwellenwerte des Vergaberechts',
        'Vergleichsangebote',
    ):
        assert text not in pruefseite, text

    irseite = _seite(reverse('gremien:integritaet'), ir[0])
    for text in ('Antrag hervorheben', 'Hervorhebung aufheben', 'Antrag zurückweisen', 'Aussetzen', 'Aussetzung aufheben'):
        assert '>' + text not in irseite, text

    client.force_login(ir[0])
    client.post(reverse('gremien:integritaet_beschluss'), {'anlass': Anlass.HERVORHEBUNG, 'antrag': antrag.pk, 'beschreibung': 'Grund.'})
    assert GremienBeschluss.objects.filter(anlass=Anlass.HERVORHEBUNG).exists()
    irseite = _seite(reverse('gremien:integritaet'), ir[0])
    assert '>dafür' not in irseite and '>dagegen' not in irseite

    client.post(reverse('gremien:integritaet_regelpruefung'))
    regelpruefung = GremienBeschluss.objects.get(anlass=Anlass.REGELPRUEFUNG)
    einzel = _seite(reverse('gremien:beschluss', args=[regelpruefung.nummer]))
    assert 'geprüft, keine Beanstandung' not in einzel and 'beanstandet' not in einzel

    ratseite = _seite(reverse('gremien:rat', args=['berichtswesenrat']), bw)
    for text in ('führt das öffentliche Umsetzungsregister', 'Das Umsetzungsregister', 'Stand der Umsetzung zu jedem'):
        assert text not in ratseite, text

    fachliste = _seite(reverse('gremien:fachliste'))
    for text in ('keine angegeben', 'Mitglied des Integritätsrats'):
        assert text not in fachliste, text

    admin = mitglied_anlegen('verwaltung')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    antwort = client.post(
        reverse('gremien:rollen_aktion'),
        {'aktion': 'berufen', 'mitglied': ir[0].pk, 'gremium': 'koordinationsrat', 'endet_am': standard_ende().isoformat()},
        follow=True,
    )
    meldungen = [_unuebersetzt(str(m)) for m in antwort.context['messages']]
    assert meldungen and not any('Integritätsrats' in m for m in meldungen), meldungen


def test_gespeicherte_optionen_und_gruende_bleiben_deutsch(client, ordnung):  # noqa: F811
    """Die Übersetzung geschieht beim Anzeigen: Gespeichert, auditiert und exportiert wird die deutsche
    Quelle wie bisher — sonst hinge der Inhalt eines Beschlusses von der Sprache des Anlegenden ab."""
    from gremien.models import JA_NEIN, PRUEFOPTIONEN, PRUEFPUNKTE, unvereinbar_fuer

    assert JA_NEIN == [{'wert': 'dafuer', 'name': 'dafür'}, {'wert': 'dagegen', 'name': 'dagegen'}]
    assert PRUEFOPTIONEN[0] == {'wert': 'validiert', 'name': 'validieren'}
    assert PRUEFPUNKTE[1][1].startswith('Bieterkreis')
    with translation.override('en'):
        assert unvereinbar_fuer(1, {1}, set()) == 'Mitglied des Integritätsrats (§ 6 Abs 3 lit a)'
