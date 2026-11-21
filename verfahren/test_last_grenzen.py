'''Größen- und Zeitgrenzen bei 2.000 offenen Verfahren (GP-153, Q-04).

Geprüft werden Abfragezahl, Speicherspitze (tracemalloc) und Antwortgröße — das hängt nicht von
der Rechnergeschwindigkeit ab. Die Zeitgrenzen stehen in einem eigenen Lasttest, der nur mit
DDOE_LASTTEST=1 läuft. Gemessen am Stand 0.114.0 (Prüfrechner, Python 3.12, SQLite):
Vorschau 11 Abfragen, Spitze 14,0 MiB, rund 540 ms; Absenden mit 2.000 Vektoren zu 1.024
Dimensionen Spitze 99,5 MiB, rund 1,4 s; Antragsseite mit 21 Läufen 41 Abfragen, 827.868 Bytes.
'''

import os
import random
import time
import tracemalloc

import pytest
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ki.anbieter import AttrappenAnbieter, Einbettung, anbieter_waehlen
from parameter.models import Parameter, zahl
from plattform_core import Phase
from plattform_core.similarity import aehnlichkeit, kosinus, vereinigen
from verfahren.aehnlichkeit import OFFENE_PHASEN, PERSONENARTEN, aehnliche_antraege
from verfahren.models import Antrag, Antragsart, AntragsEinbettung, AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

lasttest = pytest.mark.skipif(not os.environ.get('DDOE_LASTTEST'), reason='Lasttest nur mit DDOE_LASTTEST=1')

NEU = {'titel': 'Öffentliche Trinkbrunnen in jeder Gemeinde', 'begruendung': 'Last.',
       'wortlaut': 'Jede Gemeinde richtet mindestens einen öffentlich zugänglichen Trinkbrunnen ein.'}
WORTE = ('Radweg Schule Gemeinde Verkehr Wasser Energie Pflege Wohnen Steuer Wald Bahn Markt Jugend Kultur Sport '
         'Abfall Lärm Licht Brücke Platz Garten Bücherei Spital Feuerwehr Kanal').split()
MIB = 1048576
#: Dreifacher Abstand zu den am Prüfrechner nach GP-153 gemessenen Werten.
VORSCHAU_SEKUNDEN = 1.5
ABSENDEN_SEKUNDEN = 4.5


def _register(schluessel, wert):
    Parameter.objects.update_or_create(schluessel=schluessel, defaults={'wert': str(wert), 'beschreibung': 'x', 'quelle': 'Test'})


def _bestand(anzahl, ordnung, *, dimension=0):  # noqa: F811
    autorin = mitglied_anlegen('autorin')
    erster = antrag_einbringen(autorin, 'Erster Antrag der Lastprobe', 'Wortlaut des ersten Antrags.', '', ordnung)
    felder = [f.attname for f in Antrag._meta.concrete_fields if not f.primary_key]
    werte = {f: getattr(erster, f) for f in felder}
    zufall = random.Random(7)
    Antrag.objects.bulk_create([
        Antrag(**{**werte, 'titel': f'{zufall.choice(WORTE)} {zufall.choice(WORTE)} verbessern ({i})'})
        for i in range(anzahl - 1)], batch_size=500)
    alle = list(Antrag.objects.exclude(pk=erster.pk).values_list('pk', flat=True))
    AntragsFassung.objects.bulk_create([
        AntragsFassung(antrag_id=pk, nummer=1, wortlaut=' '.join(zufall.choice(WORTE) for _ in range(120)))
        for pk in alle], batch_size=500)
    if dimension:
        AntragsEinbettung.objects.bulk_create([
            AntragsEinbettung(antrag_id=pk, fassung_nummer=1, modell=AttrappenAnbieter.einbettungsmodell,
                              vektor=[round(zufall.uniform(-1, 1), 6) for _ in range(dimension)])
            for pk in [erster.pk, *alle]], batch_size=200)
    return erster


def _zufallsvektoren(monkeypatch, dimension):
    zufall = random.Random(3)
    monkeypatch.setattr(AttrappenAnbieter, 'einbetten', lambda self, texte, zeitgrenze=None: Einbettung(
        vektoren=[[zufall.uniform(-1, 1) for _ in range(dimension)] for _ in texte],
        modell=self.einbettungsmodell, tokens=5))


def _gemessen(aufruf):
    '''Ergebnis, Abfragezahl und Speicherspitze eines Aufrufs.'''
    reset_queries()
    tracemalloc.start()
    try:
        with CaptureQueriesContext(connection) as q:
            ergebnis = aufruf()
        _, spitze = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return ergebnis, len(q.captured_queries), spitze


# --- Dieselben Treffer wie die Rechnung über alle offenen Anträge ----------------------------------


def _bisherige_rechnung(titel, wortlaut, ergebnis):
    '''Die Rechnung von 0.114.0 nachgebaut: Wortvergleich über alle offenen Anträge mit ihrer jüngsten
    Fassung, Bedeutung über alle gespeicherten Vektoren der Sachanträge zu dieser Fassung.'''
    offene = list(Antrag.objects.filter(phase__in=OFFENE_PHASEN).prefetch_related('fassungen').order_by('pk'))

    def juengste(a):
        return max(a.fassungen.all(), key=lambda f: f.nummer, default=None)

    wortwerte = {a.pk: aehnlichkeit((titel, wortlaut), (a.titel, juengste(a).wortlaut if juengste(a) else ''))
                 for a in offene}
    bedeutung = {}
    if ergebnis.neuer_vektor is not None:
        for a in offene:
            if a.art in PERSONENARTEN:
                continue
            nummer = juengste(a).nummer if juengste(a) else 1
            zeile = AntragsEinbettung.objects.filter(antrag=a, fassung_nummer=nummer, modell=ergebnis.bedeutungsmodell).first()
            if zeile is not None:
                bedeutung[a.pk] = kosinus(ergebnis.neuer_vektor, zeile.vektor)
    zeilen = vereinigen(wortwerte, bedeutung,
                        wort_schwelle=zahl('aehnlichkeit-schwelle-prozent', 30) / 100,
                        bedeutung_schwelle=zahl('aehnlichkeit-bedeutung-schwelle-prozent', 78) / 100,
                        limit=zahl('aehnlichkeit-treffer', 3))
    return [(kid, round(w * 100), round(b * 100) if b is not None else None) for kid, w, b in zeilen]


@pytest.fixture
def gemischter_bestand(ordnung, settings):  # noqa: F811
    '''Offene und abgeschlossene Anträge, Personenanträge, mehrere Fassungen, Vektoren zu früheren
    Fassungen und zu einem anderen Modell, ein Antrag ohne Fassung.'''
    from ki.anbieter import attrappen_vektor

    settings.DDOE_KI_ANBIETER = 'attrappe'
    zufall = random.Random(11)
    leute = [mitglied_anlegen(f'person{i}') for i in range(4)]
    antraege = []
    for i in range(60):
        titel = ' '.join(zufall.sample(WORTE, 3)) + f' Vorschlag {i}'
        wortlaut = ' '.join(zufall.choice([*WORTE, 'Trinkbrunnen', 'öffentlich', 'zugänglich'])
                            for _ in range(zufall.randint(4, 40)))
        antraege.append(antrag_einbringen(leute[i % 4], titel, wortlaut + '.', '', ordnung))
    for a in antraege[::7]:
        AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut='Trinkbrunnen Gemeinde öffentlich zugänglich Wasser.')
    Antrag.objects.filter(pk__in=[a.pk for a in antraege[1::9]]).update(phase=Phase.ANGENOMMEN.value)
    Antrag.objects.filter(pk__in=[a.pk for a in antraege[2::11]]).update(art=Antragsart.MANDAT)
    # Altbestand ohne Fassung: am Schreibriegel der Fassungen vorbei hergestellt (GP-067).
    AntragsFassung._base_manager.filter(antrag=antraege[5]).delete()
    modell = AttrappenAnbieter.einbettungsmodell
    for a in antraege[::3]:
        AntragsEinbettung.objects.get_or_create(antrag=a, fassung_nummer=1, modell=modell,
                                                defaults={'vektor': attrappen_vektor(f'{a.titel}\nalt')})
    for a in antraege[::5]:
        AntragsEinbettung.objects.get_or_create(antrag=a, fassung_nummer=1, modell='anderes-modell',
                                                defaults={'vektor': [1.0, 0.0]})
    return leute


@pytest.mark.parametrize('treffer,wort,bedeutung', [(3, 30, 78), (50, 0, 0), (10, 15, 40)])
@pytest.mark.parametrize('mit_bedeutung', [False, True])
def test_dieselben_treffer_wie_die_rechnung_ueber_alle(gemischter_bestand, treffer, wort, bedeutung, mit_bedeutung):
    _register('aehnlichkeit-treffer', treffer)
    _register('aehnlichkeit-schwelle-prozent', wort)
    _register('aehnlichkeit-bedeutung-schwelle-prozent', bedeutung)
    assert anbieter_waehlen() is not None
    gefunden = 0
    for nr, (titel, wortlaut) in enumerate([
        (NEU['titel'], NEU['wortlaut']),
        ('Wasser Energie Wald', 'Wasser und Energie für den Wald, Pflege der Gärten.'),
        ('Ganz anderes Thema', 'Steuer Markt Jugend'),
        ('Trinkbrunnen öffentlich zugänglich', 'Trinkbrunnen Gemeinde öffentlich zugänglich Wasser.'),
    ]):
        ergebnis = aehnliche_antraege(titel, wortlaut, gemischter_bestand[nr], bedeutung=mit_bedeutung)
        assert ergebnis.bedeutung_aktiv is mit_bedeutung
        erhalten = [(t['antrag'].pk, t['prozent'], t['bedeutung_prozent']) for t in ergebnis.treffer]
        assert erhalten == _bisherige_rechnung(titel, wortlaut, ergebnis)
        gefunden += len(erhalten)
    assert gefunden, 'die Testfälle sollen Treffer haben'


# --- Vorschau und Absenden --------------------------------------------------------------------------


def test_vorschau_bei_2000_offenen_antraegen_bleibt_unter_der_speichergrenze(client, ordnung, settings):  # noqa: F811
    settings.DDOE_KI_ANBIETER = ''
    _bestand(2000, ordnung)
    client.force_login(mitglied_anlegen('bernd'))
    client.post(reverse('verfahren:einbringen_vorschau'), NEU)  # Registerwerte und Sitzung einmal laden
    antwort, abfragen, spitze = _gemessen(lambda: client.post(reverse('verfahren:einbringen_vorschau'), NEU))
    print(f'VORSCHAU 2000: abfragen={abfragen} spitze_mib={spitze / MIB:.1f} bytes={len(antwort.content)}')
    assert antwort.status_code == 200
    assert abfragen <= 11
    assert spitze < 3 * MIB  # 0.114.0: 14,2 MiB; jetzt rund 0,7 MiB


def test_absenden_bei_2000_vektoren_bleibt_unter_der_speichergrenze(ordnung, settings, monkeypatch):  # noqa: F811
    '''Die gespeicherten Vektoren werden seitenweise verglichen, nicht alle zugleich gehalten.'''
    settings.DDOE_KI_ANBIETER = 'attrappe'
    _bestand(2000, ordnung, dimension=256)
    _zufallsvektoren(monkeypatch, 256)
    bernd = mitglied_anlegen('bernd')
    ergebnis, abfragen, spitze = _gemessen(lambda: aehnliche_antraege(NEU['titel'], NEU['wortlaut'], bernd))
    print(f'ABSENDEN 2000x256: abfragen={abfragen} spitze_mib={spitze / MIB:.1f}')
    assert ergebnis.bedeutung_aktiv
    assert spitze < 6 * MIB  # 0.114.0: 36,5 MiB; jetzt rund 1,9 MiB


@lasttest
def test_lasttest_vorschau_und_absenden_mit_zeitgrenze(client, ordnung, settings, monkeypatch):  # noqa: F811
    '''Lasttest mit 1.024 Dimensionen wie ein übliches Einbettungsmodell.'''
    settings.DDOE_KI_ANBIETER = 'attrappe'
    _bestand(2000, ordnung, dimension=1024)
    _zufallsvektoren(monkeypatch, 1024)
    client.force_login(mitglied_anlegen('bernd'))
    settings.DDOE_KI_ANBIETER = ''
    zeiten = []
    for _ in range(3):
        t = time.perf_counter()
        assert client.post(reverse('verfahren:einbringen_vorschau'), NEU).status_code == 200
        zeiten.append(time.perf_counter() - t)
    settings.DDOE_KI_ANBIETER = 'attrappe'
    t = time.perf_counter()
    antwort = client.post(reverse('verfahren:einbringen'), NEU)
    absenden = time.perf_counter() - t
    tracemalloc.start()
    try:
        client.post(reverse('verfahren:einbringen'), NEU)
        _, spitze = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    print(f'LASTTEST vorschau_ms={[round(z * 1000) for z in zeiten]} absenden_ms={round(absenden * 1000)} '
          f'absenden_spitze_mib={spitze / MIB:.1f}')
    assert antwort.status_code == 302
    assert min(zeiten) < VORSCHAU_SEKUNDEN
    assert absenden < ABSENDEN_SEKUNDEN
    assert spitze < 25 * MIB  # 0.114.0: 99,5 MiB; jetzt rund 5 MiB


# --- Antragsseite -----------------------------------------------------------------------------------


def _antrag_mit_laeufen(ordnung, monkeypatch, settings, laeufe=21):  # noqa: F811
    from faktenbasis.test_personalrahmen import daten as personaldaten
    from ki.anbieter import Antwort
    from ki.test_folgenauftraege import ANTWORT
    from ki.warteschlange import abarbeiten, rechtspruefung_einreihen

    settings.DDOE_KI_ANBIETER = 'attrappe'
    monkeypatch.setattr(AttrappenAnbieter, 'frage', lambda self, a, e, zeitgrenze=None: Antwort(ANTWORT, 'last', 10, 20))
    _register('ki-tageslaeufe', 100)
    personaldaten()
    m = mitglied_anlegen('viel')
    antrag = antrag_einbringen(m, 'Antrag mit vielen Fassungen', 'Wortlaut eins. ' + 'Langer Absatz der Lastprobe. ' * 400, 'Grund.', ordnung)
    rechtspruefung_einreihen(antrag, m)
    for n in range(2, laeufe + 1):
        AntragsFassung.objects.create(antrag=antrag, nummer=n, wortlaut=f'Wortlaut {n}. ' + 'Langer Absatz der Lastprobe. ' * 400)
        rechtspruefung_einreihen(antrag, m)
    abarbeiten()
    return antrag


def test_antragsseite_mit_21_laeufen_bleibt_unter_der_groessengrenze(client, ordnung, settings, monkeypatch):  # noqa: F811
    '''Die Eingaben früherer Läufe stehen im Archiv des Antrags, nicht eingebettet in der Seite.'''
    from ki.models import KILauf

    antrag = _antrag_mit_laeufen(ordnung, monkeypatch, settings)
    laeufe = list(KILauf.objects.filter(antrag=antrag).order_by('-erstellt_am', '-pk'))
    assert len(laeufe) == 21
    gast = client.__class__()
    gast.get(reverse('verfahren:antrag', args=[antrag.pk]))
    reset_queries()
    with CaptureQueriesContext(connection) as q:
        antwort = gast.get(reverse('verfahren:antrag', args=[antrag.pk]))
    html = antwort.content.decode()
    anfang = html.index('id="zone-einschaetzung"')
    zone = html[anfang:html.index('</aside>', anfang)].encode()
    print(f'ANTRAGSSEITE 21 Läufe: abfragen={len(q.captured_queries)} bytes={len(antwort.content)} zone={len(zone)}')
    assert antwort.status_code == 200
    # 0.114.0: rund 470.000 Bytes in der Zone, je früherem Lauf die volle Eingabe. Jetzt hat ein Eintrag der
    # Historie eine feste Größe, und die Historie ist seitenweise (ki-einschaetzungen-je-seite).
    assert len(zone) < 200_000
    # 41 bis 0.115.0; dazu je eine feste Abfrage der Seite, unabhängig von Zahl der Läufe und Fassungen
    # (mit 3 und 21 Läufen gleich viele): die nicht gezählten Unterstützungen von Testkonten (GP-126)
    # und die verknüpfte Rechenschaft des Antrags (GP-065).
    assert len(q.captured_queries) <= 43
    # Der aktuelle Lauf zeigt seine Eingabe weiter, die Historie verweist auf das Archiv
    assert html.count('class="auftragstext"') == 1
    assert reverse('verfahren:archiv_export', args=[antrag.pk, 'md']) in html
    archiv = gast.get(reverse('verfahren:archiv_export', args=[antrag.pk, 'md'])).content.decode()
    assert all(lauf.eingabe[:200] in archiv for lauf in laeufe[1:3])
