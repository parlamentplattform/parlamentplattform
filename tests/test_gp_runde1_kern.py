"""Gesamtprüfung 18.11.2026, erste Behebungsrunde: Zählkern, Prüfskript, Regelverzeichnis.

Jeder Test stellt einen Befund (GP-Kennung) nach und hält die Behebung fest."""

from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Policy
from plattform_core.tally import auszaehlen, personenwahl_auszaehlen
from verify.nachrechnen import nachrechnen

ZEIT = '2026-11-18T12:58:55.763580+00:00'


def _policy(prozent=5, mehrheitsbasis='ja_nein'):
    return Policy(
        id='test',
        version=1,
        unterstuetzung_schwelle=5,
        unterstuetzung_frist_tage=14,
        beratung_tage=21,
        abstimmung_tage=7,
        mindestbeteiligung=prozent / 100,
        mehrheitsbasis=mehrheitsbasis,
    )


def _kandidatur_export(bewerbungen, zustimmungen, berechtigte, prozent=5):
    """Ein Kandidatur-Export, wie `export_json` ihn schreibt. `bewerbungen`: (nummer, zurueckgezogen);
    `zustimmungen`: (pseudonym, nummer, ruecknahme) mit ruecknahme None (gilt), 'wert' (neue
    Schreibweise `zurueckgenommen: true`) oder 'zeit' (alte Schreibweise mit Zeitangabe)."""
    zeilen = []
    for pseudonym, nummer, ruecknahme in zustimmungen:
        zeile = {'pseudonym': pseudonym, 'bewerbung': nummer}
        if ruecknahme == 'wert':
            zeile['zurueckgenommen'] = True
        elif ruecknahme == 'zeit':
            zeile['zurueckgenommen_am'] = ZEIT
        elif ruecknahme == 'offen':
            zeile['zurueckgenommen'] = False
            zeile['zurueckgenommen_am'] = None
        zeilen.append(zeile)
    return {
        'art': 'mandat',
        'policy': {'mindestbeteiligung': prozent / 100},
        'stimmberechtigte': berechtigte,
        'stimmen': [],
        'bewerbungen': [
            {'bewerbung': nummer, 'name': f'B{nummer}', 'eingereicht_am': '2026-11-01', 'zurueckgezogen': weg}
            for nummer, weg in bewerbungen
        ],
        'zustimmungen': zeilen,
    }


def _kern(bewerbungen, zustimmungen, berechtigte, prozent=5):
    """Dieselbe Wahl, wie `Antrag.kandidatur_auszaehlen` sie dem Kern übergibt: nur wählbare
    Bewerbungen, nur gültige Zustimmungen zu ihnen."""
    waehlbar = [nummer for nummer, weg in bewerbungen if not weg]
    gueltig = [(p, nummer) for p, nummer, ruecknahme in zustimmungen if ruecknahme in (None, 'offen') and nummer in waehlbar]
    return personenwahl_auszaehlen(gueltig, waehlbar, berechtigte, _policy(prozent))


def _gleich(skript, kern):
    assert skript['gewaehlt'] == kern.gewonnen_id
    assert skript['beteiligung'] == kern.beteiligung
    assert skript['beteiligung_erreicht'] is kern.beteiligung_erreicht
    assert skript['angenommen'] is kern.angenommen
    assert [(p['platz'], p['bewerbung'], p['zustimmungen']) for p in skript['plaetze']] == [
        (p.platz, p.bewerbung_id, p.stimmen) for p in kern.plaetze
    ]


# --- GP-022: zurückgenommene Zustimmungen zählen im Prüfskript nicht -------------------------------


def test_pruefskript_ueberspringt_zurueckgenommene_zustimmungen():
    """ASR-01: Zwei Mitglieder stimmen B zu und nehmen zurück, eines stimmt A zu. Die Plattform wählt
    A mit Beteiligung 1; das Skript nannte B mit Beteiligung 3. Beide Schreibweisen der Rücknahme
    (Wahrheitswert und alte Zeitangabe) müssen übersprungen werden."""
    bewerbungen = [(1, False), (2, False)]
    for schreibweise in ('wert', 'zeit'):
        zustimmungen = [('p1', 2, schreibweise), ('p2', 2, schreibweise), ('p3', 1, 'offen')]
        skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, 10))
        kern = _kern(bewerbungen, zustimmungen, 10)
        _gleich(skript, kern)
        assert skript['gewaehlt'] == 1 and skript['beteiligung'] == 1
        assert skript['zurueckgenommen'] == 2


def test_pruefskript_nur_zurueckgenommene_zustimmungen_tragen_keine_beteiligung():
    """ASR-01, zweiter Fall: Eine gültige Zustimmung bei 40 Stimmberechtigten verfehlt die
    Mindestbeteiligung; drei zurückgenommene dürfen sie nicht über die Schwelle heben."""
    bewerbungen = [(1, False)]
    zustimmungen = [('p1', 1, None), ('p2', 1, 'wert'), ('p3', 1, 'zeit'), ('p4', 1, 'wert')]
    skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, 40))
    kern = _kern(bewerbungen, zustimmungen, 40)
    _gleich(skript, kern)
    assert skript['beteiligung_erreicht'] is False and skript['gewaehlt'] is None
    assert skript['zurueckgenommen'] == 3


def test_pruefskript_weist_doppelte_zeilen_auch_bei_ruecknahme_ab():
    """Die Plattform führt je Pseudonym und Bewerbung genau eine Zeile; eine zweite ist ein Fehler
    im Export, gleich ob eine der beiden zurückgenommen ist."""
    import pytest

    export = _kandidatur_export([(1, False)], [('p1', 1, 'wert'), ('p1', 1, None)], 10)
    with pytest.raises(SystemExit, match='doppelt'):
        nachrechnen(export)


def test_pruefskript_rechnet_den_echten_export_mit_ruecknahmen_wie_die_plattform(client, db):
    """Abnahme GP-022 am echten Export: Zwei Mitglieder stimmen B zu und nehmen zurück, eines stimmt
    A zu. `export_json` führt die zurückgenommenen Zeilen weiter; das Skript muss denselben Gewinner
    und dieselbe Beteiligung nennen wie `kandidatur_auszaehlen` (vorher: B mit Beteiligung 3)."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    from verfahren.models import Verfahrensordnung, bewerbung_einreichen, bewerbung_zustimmen
    from verfahren.test_kandidatur import _in_abstimmung, _kandidatur
    from verfahren.test_views_aktionen import REGELN, mitglied_anlegen

    ordnung = Verfahrensordnung.objects.create(policy_id='test-ordnung', version=1, regeln=REGELN, aktiv=True)
    autor = mitglied_anlegen('autor')
    leute = [mitglied_anlegen(f'm{i}') for i in range(3)]
    antrag = _kandidatur(ordnung, autor)
    a = bewerbung_einreichen(antrag, leute[0], 'A')
    b = bewerbung_einreichen(antrag, leute[1], 'B')
    _in_abstimmung(antrag, leute)
    for wer in leute[:2]:
        assert bewerbung_zustimmen(antrag, wer, b) is True
        assert bewerbung_zustimmen(antrag, wer, b) is False  # zurückgenommen
    assert bewerbung_zustimmen(antrag, leute[2], a) is True
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=['phase_beginn'])

    daten = client.get(reverse('verfahren:export', args=[antrag.pk])).json()
    assert len(daten['zustimmungen']) == 3  # die zurückgenommenen Zeilen stehen im Export
    skript = nachrechnen(daten)
    kern = antrag.kandidatur_auszaehlen()
    assert skript['gewaehlt'] == kern.gewonnen_id == a.pk
    assert skript['beteiligung'] == kern.beteiligung == 1
    assert skript['zurueckgenommen'] == 2


@given(
    zurueckgezogen=st.lists(st.booleans(), min_size=1, max_size=6),
    zeilen=st.dictionaries(
        st.tuples(st.integers(0, 11), st.integers(1, 6)),
        st.sampled_from([None, 'offen', 'wert', 'zeit']),
        max_size=25,
    ),
    berechtigte=st.integers(1, 300),
    prozent=st.integers(5, 100),
)
def test_eigenschaft_pruefskript_und_kern_zaehlen_jede_kandidatur_gleich(zurueckgezogen, zeilen, berechtigte, prozent):
    """§ 5 Abs 8: Für jede Wahl mit zurückgezogenen Bewerbungen und zurückgenommenen Zustimmungen
    nennt das unabhängige Skript dieselben Plätze, dieselbe Beteiligung und denselben Gewinner
    wie der Kern (Schwellen in ganzen Prozent, wie das Register sie führt)."""
    bewerbungen = [(nummer, weg) for nummer, weg in enumerate(zurueckgezogen, start=1)]
    zustimmungen = [
        (f'p{p}', nummer, ruecknahme) for (p, nummer), ruecknahme in zeilen.items() if nummer <= len(bewerbungen)
    ]
    skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, berechtigte, prozent))
    _gleich(skript, _kern(bewerbungen, zustimmungen, berechtigte, prozent))
    assert skript['zurueckgenommen'] == sum(1 for z in zustimmungen if z[2] in ('wert', 'zeit'))


@given(
    ja=st.integers(0, 120),
    nein=st.integers(0, 120),
    enthaltung=st.integers(0, 120),
    berechtigte=st.integers(1, 3000),
    prozent=st.integers(5, 100),
    basis=st.sampled_from(['ja_nein', 'abgegeben']),
)
def test_eigenschaft_pruefskript_und_kern_zaehlen_jede_sachfrage_gleich(ja, nein, enthaltung, berechtigte, prozent, basis):
    """Dieselbe Gegenprobe für Sachfragen, beide Mehrheitsbasen."""
    werte = ['ja'] * ja + ['nein'] * nein + ['enthaltung'] * enthaltung
    stimmen = [(f'p{i}', wert) for i, wert in enumerate(werte)]
    kern = auszaehlen(stimmen, berechtigte, _policy(prozent, basis))
    skript = nachrechnen(
        {
            'art': 'sache',
            'policy': {'mindestbeteiligung': prozent / 100, 'mehrheitsbasis': basis},
            'stimmberechtigte': berechtigte,
            'stimmen': [{'pseudonym': p, 'stimme': wert} for p, wert in stimmen],
        }
    )
    assert (skript['ja'], skript['nein'], skript['enthaltung']) == (kern.ja, kern.nein, kern.enthaltung)
    assert skript['beteiligung_erreicht'] is kern.beteiligung_erreicht
    assert skript['angenommen'] is kern.angenommen


# --- GP-204: Regelverzeichnis ohne Programmtext, jeder Regeltext ein Katalogeintrag ---------------


def test_jeder_registerschluessel_im_regelverzeichnis_ist_ein_text():
    """GAST-10/RVA-16: Ein Tupel im Feld erschien auf /regeln/ als Programmtext `('…',)`."""
    from plattform_core.regelwerk import REGELN

    falsch = [(r.modul, r.registerschluessel) for r in REGELN if not isinstance(r.registerschluessel, str)]
    assert falsch == []


def test_jeder_regeltext_ist_genau_ein_katalogeintrag():
    """GAST-10: Sieben Texte waren aus mehreren markierten Teilen zusammengesetzt. Die Vorlage schlägt
    den ganzen Text im Katalog nach, den es dort nur in Teilen gab; englisch blieben sie deutsch.
    Jedes Textfeld einer Regel ist deshalb genau ein markierter Text."""
    import ast
    import pathlib

    quelle = pathlib.Path(__file__).resolve().parent.parent / 'plattform_core' / 'regelwerk.py'
    zusammengesetzt = []
    for knoten in ast.walk(ast.parse(quelle.read_text(encoding='utf-8'))):
        if not (isinstance(knoten, ast.Call) and getattr(knoten.func, 'id', '') == 'Regel'):
            continue
        modul = next(ast.literal_eval(s.value) for s in knoten.keywords if s.arg == 'modul')
        for s in knoten.keywords:
            if s.arg in ('titel', 'zweck', 'grund', 'nachrechenbar', 'luecke') and not (
                isinstance(s.value, ast.Call) and getattr(s.value.func, 'id', '') == '_'
            ):
                zusammengesetzt.append((modul, s.arg))
    assert zusammengesetzt == []


def test_regelseite_zeigt_keinen_programmtext(client, db):
    """Abnahme GP-204: /regeln/ zeigt den Schlüssel als Text, nicht als maskiertes Tupel `('…',)`."""
    seite = client.get('/regeln/').content.decode()
    assert '>suche-treffer-hoechstzahl</a>' in seite
    assert '(&#x27;' not in seite and '&#x27;,)' not in seite


# --- GP-022 und GP-203: Das Regelverzeichnis sagt, was beim Nachrechnen von Hand nicht zählt -------


def test_regelverzeichnis_nennt_ruecknahmen_und_den_gleichstand_an_der_spitze():
    """Wer die Kandidatur nach dem Verzeichnis von Hand nachrechnet, zählte zurückgenommene
    Zustimmungen mit (derselbe Fehler wie im Prüfskript, GP-022). Die geltende Gleichstandsregel
    stand nur als „steht vorn“ da; dass sie auch den ersten Platz entscheidet, steht jetzt dabei
    (GP-203, nur die Benennung; die Regel selbst ist unverändert)."""
    from plattform_core.regelwerk import REGELN

    (regel,) = [r for r in REGELN if r.titel == 'Auszählung der Zustimmungswahl bei Kandidaturen']
    assert 'ohne zurückgenommene Zustimmungen' in regel.nachrechenbar
    assert 'verify/nachrechnen.py' in regel.nachrechenbar
    assert 'ist die früher eingereichte gewählt' in regel.zweck


def test_gleichstand_an_der_spitze_waehlt_die_frueher_eingereichte_bewerbung():
    """Die im Verzeichnis benannte Regel, an Kern und Prüfskript nachgestellt."""
    bewerbungen = [(7, False), (3, False)]  # 7 wurde früher eingereicht als 3
    zustimmungen = [('p1', 3, None), ('p2', 7, None)]
    kern = _kern(bewerbungen, zustimmungen, 10)
    skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, 10))
    assert kern.gewonnen_id == skript['gewaehlt'] == 7


# --- Z-3 (Fahrtenbuch D-C7): „Meistgelesene Anträge“ steht als Regel im Verzeichnis -----------------


def test_meistgelesene_antraege_stehen_als_versionierte_regel_im_verzeichnis():
    """Gründer 28.9.2026: Die Liste bleibt und wird als offengelegte, versionierte Regel geführt.
    Der Eintrag beschreibt das heutige Verhalten und benennt, was daran offen ist."""
    from plattform_core import meistgelesen
    from plattform_core.regelwerk import REGELN, Wirkung

    (regel,) = [r for r in REGELN if r.modul == 'meistgelesen.py']
    assert regel.wirkung is Wirkung.REIHT and regel.fassung == meistgelesen.VERSION == 1
    assert regel.seit and regel.grund and regel.nachrechenbar
    assert 'fünf' in regel.zweck and 'absteigend' in regel.nachrechenbar
    assert 'gleicher Summe' in regel.luecke


def test_die_uebersicht_reiht_die_meistgelesenen_wie_die_regel(client, db):
    """Die Regel beschreibt, was die Seite tut: Summe der Aufrufe aller Tage je Antrag, absteigend,
    höchstens fünf. Verglichen wird die Seite mit der Nachrechnung aus den Tageszahlen."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    from plattform_core.meistgelesen import HOECHSTZAHL, meistgelesene
    from uebersicht.models import AntragAufruf
    from verfahren.models import Verfahrensordnung, antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG, REGELN, mitglied_anlegen

    ordnung = Verfahrensordnung.objects.create(policy_id='test-ordnung', version=1, regeln=REGELN, aktiv=True)
    autor = mitglied_anlegen('autor')
    heute = timezone.localdate()
    tageszahlen = []
    for nummer, je_tag in enumerate([(3, 4), (20,), (1, 1, 1), (9, 2), (6,), (5, 7), (2,)]):
        antrag = antrag_einbringen(autor, **{**ANTRAG, 'titel': f'Antrag {nummer}'}, ordnung=ordnung)
        for tage, aufrufe in enumerate(je_tag):
            AntragAufruf.objects.create(antrag=antrag, datum=heute - timedelta(days=tage), aufrufe=aufrufe)
            tageszahlen.append((antrag.pk, aufrufe))

    seite = client.get(reverse('uebersicht:index'))
    gezeigt = [(zeile['antrag'].pk, zeile['aufrufe']) for zeile in seite.context['meistgelesen']]
    assert len(gezeigt) == HOECHSTZAHL
    assert gezeigt == meistgelesene(tageszahlen)
