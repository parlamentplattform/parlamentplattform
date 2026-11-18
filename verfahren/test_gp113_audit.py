"""Öffentliches Audit, erste Behebungsrunde nach der Gesamtprüfung (0.113.0).

GP-011: Die Begründung einer Rückgabe durch Gruppe 2 nennt die Prüfenden mit Namen — öffentlich geschwärzt.
GP-210: Während der Abstimmung trägt ein Stimm-Ereignis öffentlich nur das Tagesdatum.
GP-158: Angezeigt wird die versiegelte Zeit; eine Abweichung der Spalte meldet die Prüfung."""

import pytest
from django.urls import reverse

from verfahren.audit_oeffentlich import MASKE, ereignis_oeffentlich
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


# --- GP-011 ---------------------------------------------------------------------------------------


def test_die_rueckgabe_durch_gruppe_2_nennt_oeffentlich_keinen_pruefenden():
    alt = {
        'typ': 'vorschlag_zurueckgegeben',
        'antrag': 7,
        'runde': 2,
        'grund': 'Gruppe 2: Petra Probekind: mit Begründung zurückgeben — Die Kriterien fehlen.',
    }
    oeffentlich, geschwaerzt = ereignis_oeffentlich(alt)
    assert geschwaerzt
    assert oeffentlich['grund'] == MASKE
    assert 'Probekind' not in str(oeffentlich)


def test_die_rueckgabe_aus_dem_abstimmungs_chat_bleibt_lesbar():
    rechnung = {
        'typ': 'vorschlag_zurueckgegeben',
        'antrag': 7,
        'runde': 2,
        'grund': 'Der Abstimmungs-Chat gibt zurück: 3 von 10 (30 %, Schwelle 50 %).',
    }
    oeffentlich, geschwaerzt = ereignis_oeffentlich(rechnung)
    assert not geschwaerzt
    assert oeffentlich['grund'] == rechnung['grund']


# --- GP-210 ---------------------------------------------------------------------------------------


def _laufende_abstimmung(eingefroren):
    from verfahren.models import antrag_einbringen, stimme_abgeben
    from verfahren.test_views_aktionen import ANTRAG, in_abstimmung_bringen, mitglied_anlegen

    leute = [mitglied_anlegen(f'z{i}') for i in range(4)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=eingefroren)
    in_abstimmung_bringen(antrag, leute[1:3])
    antrag.refresh_from_db()
    stimme_abgeben(antrag, leute[3], 'ja')
    stimme_abgeben(antrag, leute[3], 'nein')
    return antrag


def _stimmereignisse(eintraege):
    return [e for e in eintraege if e['typ'] in ('stimme', 'stimme_geaendert')]


def test_waehrend_der_abstimmung_traegt_eine_stimme_oeffentlich_nur_den_tag(client, ordnung):  # noqa: F811
    antrag = _laufende_abstimmung(ordnung)
    assert antrag.phase == 'abstimmung'
    eintraege = client.get(reverse('verfahren:audit_json'), {'antrag': antrag.pk}).json()['eintraege']
    stimmen = _stimmereignisse(eintraege)
    assert len(stimmen) == 2
    for e in stimmen:
        assert e['zeit'].endswith('T00:00:00'), e['zeit']
        assert e['ereignis']['zeit'].endswith('T00:00:00'), e['ereignis']['zeit']
    # andere Ereignisse behalten ihre Uhrzeit
    andere = [e for e in eintraege if e not in stimmen]
    assert andere and not any(e['zeit'].endswith('T00:00:00') for e in andere)


def test_der_export_des_antrags_rundet_ebenso(ordnung):  # noqa: F811
    from verfahren.archiv import audit_spur

    antrag = _laufende_abstimmung(ordnung)
    stimmen = _stimmereignisse(audit_spur(antrag))
    assert stimmen and all(e['zeit'].endswith('T00:00:00') for e in stimmen)


def test_nach_der_abstimmung_steht_die_genaue_zeit_wieder(client, ordnung):  # noqa: F811
    from verfahren.models import Antrag

    antrag = _laufende_abstimmung(ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(phase='angenommen')
    eintraege = client.get(reverse('verfahren:audit_json'), {'antrag': antrag.pk}).json()['eintraege']
    stimmen = _stimmereignisse(eintraege)
    gespeichert = {e.lfd: e.ereignis['zeit'] for e in AuditEintrag.objects.all()}
    assert stimmen and all(e['zeit'] == gespeichert[e['lfd']] for e in stimmen)


def test_die_seite_zeigt_waehrend_der_abstimmung_keine_uhrzeit(client, ordnung):  # noqa: F811
    import re

    antrag = _laufende_abstimmung(ordnung)
    html = client.get(reverse('verfahren:audit'), {'art': 'stimme'}).content.decode()
    kopf = re.findall(r'<span class="meta">#\d+ · ([^<]*)</span>', html)
    assert kopf and all(re.fullmatch(r'\d\d\.\d\d\.\d{4}', k) for k in kopf), kopf
    assert antrag.pk


# --- GP-158 ---------------------------------------------------------------------------------------


def _verschobene_spalte():
    from datetime import timedelta

    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': 3, 'neue_phase': 'beratung'})
    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': 3, 'neue_phase': 'abstimmung'})
    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': 3, 'neue_phase': 'angenommen'})
    zweiter = AuditEintrag.objects.order_by('lfd')[1]
    AuditEintrag.objects.filter(pk=zweiter.pk).update(zeit=zweiter.zeit - timedelta(days=400))
    return zweiter


def test_seite_und_json_zeigen_die_versiegelte_zeit(client):
    from verfahren.templatetags.chat import ortszeit

    zweiter = _verschobene_spalte()
    versiegelt = zweiter.ereignis['zeit']
    eintraege = {e['lfd']: e for e in client.get(reverse('verfahren:audit_json')).json()['eintraege']}
    assert eintraege[zweiter.lfd]['zeit'] == versiegelt
    html = client.get(reverse('verfahren:audit')).content.decode()
    assert f'#{zweiter.lfd} · {ortszeit(versiegelt)}' in html


def test_die_vollpruefung_meldet_eine_verschobene_zeitspalte():
    from verfahren.audit_pruefung import pruefen

    zweiter = _verschobene_spalte()
    ergebnis = pruefen(voll=True)
    assert ergebnis['intakt'] is False
    assert ergebnis['bruch'] == zweiter.lfd and ergebnis['grund'] == 'zeit'
    assert [zweiter.lfd, 'zeit'] in [list(b) for b in ergebnis['brueche']]
    # der nächste Lauf findet die Stelle wieder, auch stückweise
    weiter = pruefen(stand=ergebnis)
    assert weiter['intakt'] is False and weiter['bruch'] == zweiter.lfd


def test_eine_unveraenderte_kette_bleibt_mit_zeitabgleich_intakt():
    from verfahren.audit_pruefung import pruefen

    for i in range(3):
        AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': i, 'neue_phase': 'beratung'})
    assert pruefen(voll=True)['intakt'] is True


def test_die_seite_nennt_den_grund_zeit(client):
    from verfahren.audit_pruefung import LAUF, pruefen
    from verfahren.models import Hintergrundlauf

    _verschobene_spalte()
    Hintergrundlauf.objects.update_or_create(name=LAUF, defaults={'zuletzt_stand': pruefen(voll=True)})
    html = client.get(reverse('verfahren:audit')).content.decode()
    assert 'Zeitspalte weicht von der versiegelten Zeit ab' in html
