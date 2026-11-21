'''GP-149: Das Lauf-Archiv der Zukunftswerkstatt ist eine seitenweise Liste aller öffentlich
gelisteten Läufe mit Nummer und Anker. Die Laufnummer der Antragsseite führt auf die Seite mit
diesem Lauf; die Liste zeigt dieselben Angaben wie bisher die letzten Läufe der Werkstattseite.'''

import re

import pytest
from django.urls import reverse

from ki.models import KILauf, Zweck
from parameter.models import Parameter
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _lauf(mitglied, antrag=None, zweck=Zweck.EINSCHAETZUNG, eingabe='Eingabe', **mehr):
    return KILauf.objects.create(zweck=zweck, antrag=antrag, angefordert_von=mitglied, eingabe=eingabe,
                                 antwort=eingabe + '-ANTWORT', anbieter='attrappe', modell='probe-1', **mehr)


def _register(wert):
    Parameter.objects.update_or_create(schluessel='ki-laeufe-je-seite', defaults={'wert': str(wert)})


def _folgen(client, url):
    antwort = client.get(url, follow=True)
    assert antwort.status_code == 200, url
    return antwort


def test_nach_zwanzig_laeufen_fuehrt_lauf_eins_der_antragsseite_auf_seine_seite(client, ordnung):  # noqa: F811
    _register(5)
    m = mitglied_anlegen('anna')
    antrag = antrag_einbringen(m, ANTRAG['titel'], ANTRAG['wortlaut'], '', ordnung)
    erster = _lauf(m, antrag)
    for _i in range(19):
        _lauf(m)
    assert KILauf.objects.count() == 20

    inhalt = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    ziel = re.search(rf'<a href="([^"]+)">#{erster.pk}</a>', inhalt)
    assert ziel, 'Die Laufnummer der Kopfkarte ist kein Link'
    antwort = _folgen(client, ziel.group(1))
    seite = antwort.content.decode()
    assert f'id="lauf-{erster.pk}"' in seite
    # Die Weiterleitung nennt den Anker, damit der Browser auch ohne JavaScript dorthin springt
    assert antwort.redirect_chain[-1][0].endswith(f'#lauf-{erster.pk}')
    assert '?seite=4' in antwort.redirect_chain[-1][0]

    archiv = re.search(r'<a href="([^"]+)">Lauf-Archiv</a>', inhalt)
    assert archiv and archiv.group(1) == reverse('verfahren:laeufe')


def test_die_liste_blaettert_nach_dem_registerwert_neueste_zuerst(client, ordnung):  # noqa: F811
    _register(3)
    m = mitglied_anlegen('anna')
    laeufe = [_lauf(m) for _i in range(7)]
    erste = client.get(reverse('verfahren:laeufe')).content.decode()
    assert re.findall(r'id="lauf-(\d+)"', erste) == [str(lauf.pk) for lauf in laeufe[:-4:-1]]
    assert 'Seite 1 von 3' in erste
    letzte = client.get(reverse('verfahren:laeufe'), {'seite': 3}).content.decode()
    assert re.findall(r'id="lauf-(\d+)"', letzte) == [str(laeufe[0].pk)]


def test_ohne_registereintrag_gilt_der_startwert(client, ordnung):  # noqa: F811
    Parameter.objects.filter(schluessel='ki-laeufe-je-seite').delete()
    m = mitglied_anlegen('anna')
    for _i in range(51):
        _lauf(m)
    inhalt = client.get(reverse('verfahren:laeufe')).content.decode()
    assert len(re.findall(r'id="lauf-\d+"', inhalt)) == 50


def test_vorabvergleiche_stehen_nicht_im_archiv(client, ordnung):  # noqa: F811
    m = mitglied_anlegen('anna')
    privat = _lauf(m, zweck=Zweck.GEGENUEBERSTELLUNG, eingabe='GEHEIMER-ENTWURF')
    oeffentlich = _lauf(m, zweck=Zweck.RECHTSBEZUG)
    inhalt = client.get(reverse('verfahren:laeufe')).content.decode()
    assert f'id="lauf-{oeffentlich.pk}"' in inhalt and f'id="lauf-{privat.pk}"' not in inhalt
    assert client.get(reverse('verfahren:lauf', args=[privat.pk])).status_code == 404
    assert client.get(reverse('verfahren:lauf', args=[oeffentlich.pk + 1000])).status_code == 404


def test_das_archiv_zeigt_keine_eingaben_antworten_oder_konten(client, ordnung):  # noqa: F811
    '''Wie die Werkstattseite bisher: Zweck, Antrag, Modell, Verbrauch, Zeit, öffentlicher Fehler.'''
    m = mitglied_anlegen('anna')
    for zweck in Zweck:
        if zweck != Zweck.GEGENUEBERSTELLUNG:
            _lauf(m, zweck=zweck, eingabe=f'VERDECKT-{zweck.value}')
    _lauf(m, erfolgreich=False, fehler='Traceback in /srv/geheim.py')
    inhalt = client.get(reverse('verfahren:laeufe')).content.decode()
    assert 'VERDECKT-' not in inhalt
    assert m.anzeigename not in inhalt and m.email not in inhalt
    assert '/srv/geheim.py' not in inhalt


def test_altbestand_ohne_kontext_und_ohne_antrag_wird_gelistet(client, ordnung):  # noqa: F811
    m = mitglied_anlegen('anna')
    alt = _lauf(m, kontext={}, auftrag_version='')
    inhalt = client.get(reverse('verfahren:laeufe')).content.decode()
    assert f'id="lauf-{alt.pk}"' in inhalt and 'Textquelle nicht eigens festgehalten' in inhalt


def test_ungueltige_seitenzahl_zeigt_eine_gueltige_seite(client, ordnung):  # noqa: F811
    m = mitglied_anlegen('anna')
    _lauf(m)
    for seite in ('abc', '0', '999'):
        assert client.get(reverse('verfahren:laeufe'), {'seite': seite}).status_code == 200


def test_werkstattseite_verlinkt_das_archiv_und_die_nummern(client, ordnung):  # noqa: F811
    m = mitglied_anlegen('anna')
    lauf = _lauf(m)
    inhalt = client.get(reverse('verfahren:zukunftswerkstatt')).content.decode()
    assert reverse('verfahren:laeufe') in inhalt
    assert reverse('verfahren:lauf', args=[lauf.pk]) in inhalt


def test_der_tooltip_im_werkstattfenster_verspricht_kein_oeffentliches_archiv_der_antwort():
    from pathlib import Path

    vorlage = (Path(__file__).resolve().parent.parent / 'gremien/templates/gremien/fenster.html').read_text(encoding='utf-8')
    assert 'jeder Lauf steht im öffentlichen Archiv' not in vorlage
    assert "{% url 'verfahren:lauf' b.ki_lauf.pk %}" in vorlage
