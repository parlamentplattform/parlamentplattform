'''Folgewelle 0.115.0, Paket Oberfläche: Zuarbeit und Auflagen der ersten Welle an der Antragsseite,
an Kacheln und Ansichten des Pakets verfahren (GP-138, GP-049, GP-050, GP-003, GP-100, GP-078, GP-129,
GP-199 und Registerwerte).'''

from datetime import timedelta

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from verfahren.models import Antrag, antrag_einbringen, stimme_abgeben
from verfahren.test_oertliche_teilnahme import menschen  # noqa: F401
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


# --- GP-049: „kein Beschluss“ statt „abgelehnt“ an Badge und Listen ----------------------------------


def test_leerer_ortskreis_heisst_an_badge_und_listen_kein_beschluss(client, menschen, ordnung):  # noqa: F811
    from verfahren.templatetags.phasen import antrag_phase
    from verfahren.test_ergebnisfeld import _leerer_kreis

    a = _leerer_kreis(client, menschen)
    inhalt = _seite(client, a)
    a.refresh_from_db()
    assert a.phase == 'abgelehnt' and a.ergebnis == 'kein_beschluss'
    assert '<span class="badge b-abgelehnt">kein Beschluss</span>' in inhalt
    assert antrag_phase(a) == 'kein Beschluss'
    zeile = render_to_string('verfahren/_ast_liste.html', {'ast': {'zeilen': [a], 'seite': {'gesamt': 1, 'seiten': 1}}})
    assert 'kein Beschluss' in zeile and 'abgelehnt' not in zeile


def test_abgelehnt_und_laufend_heissen_weiter_wie_ihre_phase(ordnung):  # noqa: F811
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from verfahren.templatetags.phasen import antrag_phase

    a = antrag_einbringen(mitglied_anlegen('alt'), **ANTRAG, ordnung=ordnung)
    with CaptureQueriesContext(connection) as abfragen:
        assert antrag_phase(a) == 'Unterstützung'
    assert len(abfragen) == 0  # vor dem Ergebnis keine Abfrage
    Antrag.objects.filter(pk=a.pk).update(phase='abgelehnt')
    a.refresh_from_db()
    assert antrag_phase(a) == 'abgelehnt'


# --- GP-050: Mindestbeteiligung als Kopfzahl in der Abstimmen-Karte -----------------------------------


def test_die_abstimmen_karte_nennt_die_mindestbeteiligung_als_kopfzahl(client, ordnung):  # noqa: F811
    from plattform_core.tally import mindeststimmen

    antrag, leute = _abstimmung(ordnung)
    client.force_login(leute[5])
    inhalt = _seite(client, antrag)
    karte = inhalt.split('id="abstimmen"', 1)[1].split('</div>', 1)[0]
    policy = antrag.policy()
    n = mindeststimmen(antrag.stimmberechtigte_anzahl, policy.mindestbeteiligung)
    prozent = f'{policy.mindestbeteiligung * 100:g}'
    wort = 'Stimme' if n == 1 else 'Stimmen'
    assert f'Mindestbeteiligung: {n} {wort} ({prozent} % von {antrag.stimmberechtigte_anzahl})' in karte


def test_ohne_festgestellten_nenner_nennt_die_karte_keine_kopfzahl(client, ordnung):  # noqa: F811
    antrag, leute = _abstimmung(ordnung)
    Antrag._base_manager.filter(pk=antrag.pk).update(stimmberechtigte_anzahl=None)  # Altbestand
    client.force_login(leute[5])
    inhalt = _seite(client, antrag)
    karte = inhalt.split('id="abstimmen"', 1)[1].split('</div>', 1)[0]
    assert 'Mindestbeteiligung' not in karte


# --- GP-003 (Auflage): Zone 3 in der Wartezeit vor der Endabstimmung --------------------------------


def _zone3_kopf(client, antrag):
    inhalt = _seite(client, antrag)
    return inhalt.split('class="vorschlagskopf"', 1)[1].split('</article>', 1)[0]


def test_in_der_wartezeit_nennt_zone_3_den_beginn_der_endabstimmung_und_den_festgestellten_stand(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import _nur_die_unterstuetzerfrist_verstreicht, einreichen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    client.logout()
    vorher = _zone3_kopf(client, antrag)
    assert 'Beratung bis' in vorher and 'Endabstimmung ab' not in vorher
    frist = _nur_die_unterstuetzerfrist_verstreicht(entwurf)
    kopf = _zone3_kopf(client, antrag)
    entwurf.refresh_from_db()
    warte = entwurf.endabstimmung_wartet()
    assert warte is not None and warte['ab'] > timezone.now() > frist
    assert f'Endabstimmung ab {timezone.localtime(warte["ab"]):%d.%m.%Y %H:%M}' in kopf
    assert 'Beratung bis' not in kopf and f'{timezone.localtime(frist):%d.%m.%Y %H:%M}' not in kopf
    stand = warte['stand']
    assert f'„Passt alles": {stand["ja"]} 👍 / {stand["nein"]} 👎' in kopf



# --- GP-100: Umleitung zur Anmeldung mit Ziel ---------------------------------------------------------


@pytest.mark.parametrize('name,args', [('verfahren:meldungen', []), ('verfahren:eigene_stimme', [1])])
def test_der_gast_kommt_mit_ziel_zur_anmeldung(client, ordnung, name, args):  # noqa: F811
    from urllib.parse import quote

    if args:
        antrag_einbringen(mitglied_anlegen('ziel'), **ANTRAG, ordnung=ordnung)
        args = [Antrag.objects.get().pk]
    pfad = reverse(name, args=args)
    antwort = client.get(pfad)
    assert antwort.status_code == 302
    assert antwort['Location'] == f"{reverse('mitglieder:login')}?next={quote(pfad, safe='')}"


def test_in_verfahren_bleibt_keine_umleitung_ohne_ziel():
    from pathlib import Path

    for datei in ('views.py', 'views_aktionen.py'):
        text = (Path(__file__).parent / datei).read_text(encoding='utf-8')
        assert 'redirect("mitglieder:login")' not in text and "redirect('mitglieder:login')" not in text


# --- GP-129: Speichern und Audit-Eintrag in einer Transaktion ----------------------------------------


def _eintrag_scheitert(monkeypatch):
    from verfahren.models import AuditEintrag

    def scheitern(*_a, **_k):
        raise RuntimeError('Kette nicht erreichbar')

    monkeypatch.setattr(AuditEintrag, 'anhaengen', scheitern)


def test_scheitert_der_eintrag_bleibt_keine_meldung_stehen(client, ordnung, monkeypatch):  # noqa: F811
    from verfahren import chat as chatkern
    from verfahren.models import Meldung

    anna, bernd = mitglied_anlegen('anna'), mitglied_anlegen('bernd')
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    beitrag = chatkern.beitrag_schreiben(antrag, anna, 'Ein Beitrag.')
    client.force_login(bernd)
    _eintrag_scheitert(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(reverse('verfahren:melden', args=[antrag.pk, beitrag.pk]), {'grund': 'thema'})
    assert Meldung.objects.count() == 0


def test_scheitert_der_eintrag_bleibt_die_bewerbung_stehen(client, ordnung, monkeypatch):  # noqa: F811
    from verfahren.models import bewerbung_einreichen
    from verfahren.test_kandidatur import _kandidatur

    autor, anna = mitglied_anlegen('autor'), mitglied_anlegen('anna')
    antrag = _kandidatur(ordnung, autor)
    bewerbung = bewerbung_einreichen(antrag, anna, 'Vorstellung')
    client.force_login(anna)
    _eintrag_scheitert(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(reverse('verfahren:bewerbung_zurueckziehen', args=[antrag.pk]))
    bewerbung.refresh_from_db()
    assert bewerbung.zurueckgezogen is False


# --- GP-199: offene Formate mit der Kopfzeile der Hülle ------------------------------------------------


def test_umsetzung_und_stimmen_export_tragen_die_kopfzeile_der_offenen_formate(client, ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    assert antrag.fortschreiben(antrag.phase_beginn + timedelta(days=8)) is True
    for adresse in (reverse('verfahren:umsetzung_json'), reverse('verfahren:export', args=[antrag.pk])):
        for antwort in (client.get(adresse), client.head(adresse)):
            assert antwort.status_code == 200, adresse
            assert antwort['Access-Control-Allow-Origin'] == '*', adresse
