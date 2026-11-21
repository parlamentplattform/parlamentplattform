"""GP-109 (MG-08, GAST-05): Zahlenparameter aus Adresse und Formular — hochgestellte, vollbreite und eingekreiste
Ziffern sowie 26 Stellen führen nie zu einem Serverfehler, sondern zu 200, 302, 403 oder 404."""

import pytest
from django.urls import reverse

from mandatare.eingabe import kennung
from mandatare.models import Mandat
from mandatare.sitzung import sitzung_beginnen
from mandatare.test_mandatare import admin_anlegen, mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren.chat import sitzung_beitrag_schreiben
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

#: Hochgestellt, vollbreit, eingekreist, arabisch-indisch, übergroß — `str.isdigit` ließ die ersten drei durch.
VERFORMT = ('²', '１２', '①', '٣', '9' * 26, '-1', ' 1 2', '')
ERLAUBT = {200, 302, 403, 404}


def test_kennung_nimmt_nur_ascii_ziffern_in_der_laenge_einer_datenbankkennung():
    assert kennung('42') == 42 and kennung(' 7 ') == 7 and kennung(9) == 9
    for roh in (*VERFORMT, None, '1.0', '0x1', '9' * 19):
        assert kennung(roh) is None, roh
    assert kennung('9' * 18) == int('9' * 18)


@pytest.fixture
def lage(client):
    mitglied = mitglied_anlegen('gp109anna')
    mandat = mandat_anlegen(mitglied)
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat))
    sitzung_beitrag_schreiben(sitzung, mitglied_anlegen('gp109bert'), 'Frage an die Mandatarin')
    return mitglied, mandat, sitzung


def test_oeffentliche_zahlenparameter_antworten_ohne_serverfehler(client, lage):
    _mitglied, mandat, sitzung = lage
    live = reverse('mandatare:live', args=[mandat.pk])
    for wert in VERFORMT:
        for url in (
            f'{live}?sitzung={wert}',
            f'{live}?sitzung={sitzung.pk}&antwort_auf={wert}',
            f'{reverse("mandatare:liste")}?seite={wert}',
            f'{reverse("mandatare:rechenschaft")}?ebene={wert}',
            f'{reverse("mandatare:rechenschaft_json")}?ebene={wert}',
            f'{reverse("mandatare:vertrauensfragen")}?ebene={wert}',
        ):
            assert client.get(url).status_code in ERLAUBT, url
    for url in (
        f'/mandatare/{"9" * 26}/', f'/mandatare/{"9" * 26}/live/', f'/mandatare/{"9" * 26}/rechenschaft/',
        f'/mandatare/{"9" * 26}/berichte/', f'/mandatare/{"9" * 26}/foto',
    ):
        assert client.get(url).status_code == 404, url


def test_angemeldete_zahlenparameter_antworten_ohne_serverfehler(client, lage):
    mitglied, mandat, sitzung = lage
    client.force_login(mitglied)
    aktion = reverse('mandatare:mein_aktion')
    mein = reverse('mandatare:mein_mandat', args=[mandat.pk])
    for wert in VERFORMT:
        for daten in (
            {'aktion': 'aufgabe_status', 'mandat': wert},
            {'aktion': 'aufgabe_status', 'mandat': mandat.pk, 'aufgabe': wert, 'status': 'erledigt'},
            {'aktion': 'sammelbericht', 'mandat': mandat.pk, 'aufgabe': wert, 'text': 'Bericht'},
            {'aktion': 'rechenschaft', 'mandat': mandat.pk, 'aufgabe': wert, 'gegenstand': 'Budget'},
            {'aktion': 'rechenschaft', 'mandat': mandat.pk, 'punkt': wert, 'gegenstand': 'Budget'},
            {'aktion': 'freiwillige_begruendung', 'mandat': mandat.pk, 'rechenschaft': wert, 'text': 'Darum'},
            {'aktion': 'sitzung_meldung', 'mandat': mandat.pk, 'punkt': wert, 'text': 'Meldung'},
            {'aktion': 'sitzung_meldung', 'mandat': mandat.pk, 'berichtigt': wert, 'text': 'Meldung'},
            {'aktion': 'sitzung_punkt', 'mandat': mandat.pk, 'antrag': wert, 'titel': 'Punkt'},
        ):
            assert client.post(aktion, daten).status_code in ERLAUBT, daten
        for url in (f'{mein}?punkt={wert}', f'{mein}?aufgabe={wert}&vorlage=1'):
            assert client.get(url).status_code in ERLAUBT, url
        antwort = client.post(
            reverse('mandatare:live_beitrag', args=[mandat.pk, sitzung.pk]), {'text': 'Danke', 'antwort_auf': wert}
        )
        assert antwort.status_code in ERLAUBT, wert
        antwort = client.post(
            reverse('mandatare:vertrauensfrage_stellen', args=[mandat.pk]), {'anlass': wert, 'begruendung': 'x'}
        )
        assert antwort.status_code in ERLAUBT, wert


def test_zahlenparameter_der_verwaltung_antworten_ohne_serverfehler(client, lage):
    _mitglied, mandat, _sitzung = lage
    client.force_login(admin_anlegen())
    aktion = reverse('mandatare:verwaltung_aktion')
    for wert in VERFORMT:
        for daten in (
            {'aktion': 'beenden', 'mandat': wert},
            {'aktion': 'aufgabe_status', 'aufgabe': wert, 'status': 'erledigt'},
            {'aktion': 'aufgabe', 'mandat': mandat.pk, 'titel': 'Neu', 'antrag': wert},
            {'aktion': 'anfechtung', 'vertrauensfrage': wert},
            {'aktion': 'rechenschaft_nachtragen', 'mandat': mandat.pk, 'antrag': wert},
        ):
            assert client.post(aktion, daten).status_code in ERLAUBT, daten
    assert Mandat.objects.get(pk=mandat.pk).beendet is None


def test_uebrige_handlungen_der_verwaltung_antworten_ohne_serverfehler(client, lage):
    """Folgewelle GP-109: die Vermerke zur Vertrauensfrage, Berichtigung, Zuordnung und das Anlegen —
    jede Kennung aus dem Formular geht über `kennung` oder ein Formularfeld, keine über `isdigit`."""
    _mitglied, mandat, _sitzung = lage
    client.force_login(admin_anlegen())
    aktion = reverse('mandatare:verwaltung_aktion')
    for wert in VERFORMT:
        for daten in (
            {'aktion': 'rueckgabezusage', 'mandat': wert, 'wert': 'abgegeben'},
            {'aktion': 'lit_h', 'mandat': wert, 'datum': '2026-09-20'},
            {'aktion': 'entscheidung', 'vertrauensfrage': wert, 'entscheidung': 'bestaetigt'},
            {'aktion': 'bestaetigung_durch_wahl', 'mandat': wert},
            {'aktion': 'berichtigen', 'mandat': wert, 'bezeichnung': 'Neu'},
            {'aktion': 'gemeinde_zuordnen', 'mandat': wert, 'gemeindekennziffer': wert},
            {'aktion': 'gemeinde_zuordnen', 'mandat': mandat.pk, 'gemeindekennziffer': wert},
            {'aktion': 'foto', 'mandat': wert},
            {'aktion': 'anlegen', 'mitglied': wert, 'kandidatur': wert, 'bezeichnung': 'Rat', 'angetreten': '2026-01-01'},
        ):
            assert client.post(aktion, daten).status_code in ERLAUBT, daten
    assert Mandat.objects.count() == 1


def test_keine_isdigit_pruefung_mehr_in_den_ansichten_der_mandatare():
    """Die Eigenschaft, die bleibt: Keine Ansicht der App prüft Eingaben mit `str.isdigit`."""
    from pathlib import Path

    for datei in sorted(Path(__file__).parent.glob('*.py')):
        if datei.name.startswith('test_'):
            continue
        assert '.isdigit(' not in datei.read_text(encoding='utf-8'), datei.name
