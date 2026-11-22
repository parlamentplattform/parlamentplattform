'''Der Markdown-Export des Archivs nennt dieselben Tage wie die Antragsseite (Gesamtprüfung GP-126).

Die Seite zeigt Ortszeit, das Markdown schnitt den UTC-Zeitstempel ab: Ein Antrag, eingebracht um
23:30 UTC, stand auf der Seite am 20.10. und im Markdown am 19.10. Jetzt rechnet auch das Markdown in
Ortszeit und sagt das dazu. Alle Zeitpunkte der Tests sind fest gewählt — kein Bezug auf heute.'''

from datetime import UTC, datetime

import pytest
from django.urls import reverse

from verfahren import archiv as archivkern
from verfahren import chat as chatkern
from verfahren.models import Antrag, AntragsFassung, AuditEintrag, Kommentar, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

#: 19.10.2026 23:30 UTC ist in Wien (Sommerzeit, UTC+2) der 20.10.2026, 01:30.
SOMMER = datetime(2026, 10, 19, 23, 30, tzinfo=UTC)
#: 31.12.2026 23:30 UTC ist in Wien (Winterzeit, UTC+1) der 1.1.2027, 00:30.
WINTER = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)


def _antrag_am(ordnung, wann):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen('nachtmensch'), **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(eingebracht_am=wann, phase_beginn=wann)
    AntragsFassung._base_manager.filter(antrag=antrag).update(erstellt_am=wann)
    antrag.refresh_from_db()
    return antrag


@pytest.mark.parametrize(('wann', 'tag_seite', 'tag_markdown'), [
    (SOMMER, '20.10.2026', '2026-10-20'),
    (WINTER, '01.01.2027', '2027-01-01'),
])
def test_html_und_markdown_nennen_denselben_einbringungstag(client, ordnung, wann, tag_seite, tag_markdown):  # noqa: F811
    antrag = _antrag_am(ordnung, wann)
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert f'eingebracht {tag_seite}' in seite
    markdown = client.get(reverse('verfahren:archiv_export', kwargs={'pk': antrag.pk, 'art': 'md'})).content.decode()
    kopf = next(z for z in markdown.split('\n') if z.startswith('Eingebracht'))
    assert f'Eingebracht: {tag_markdown}' in kopf
    assert f'Fassung 1 ({tag_markdown})' in markdown
    assert 'Zeitangaben in Ortszeit (Europe/Vienna)' in markdown


def test_beitraege_und_audit_spur_stehen_im_markdown_in_ortszeit(ordnung, monkeypatch):  # noqa: F811
    antrag = _antrag_am(ordnung, SOMMER)
    beitrag = chatkern.beitrag_schreiben(antrag, antrag.eingebracht_von, 'Geschrieben kurz vor Mitternacht UTC.')
    Kommentar.objects.filter(pk=beitrag.pk).update(erstellt_am=SOMMER)
    with monkeypatch.context() as uhr:  # die Kette versiegelt ihren Zeitpunkt selbst — die Uhr wird gestellt
        uhr.setattr('django.utils.timezone.now', lambda: SOMMER)
        eintrag = AuditEintrag.anhaengen({'typ': 'probe_ortszeit', 'antrag': antrag.pk})
    markdown = archivkern.als_markdown(antrag)
    zeile = next(z for z in markdown.split('\n') if z.startswith('- **') and '(2026-10-' in z)
    assert '(2026-10-20 01:30)' in zeile
    spur = next(z for z in markdown.split('\n') if 'probe_ortszeit' in z)
    assert spur.startswith('- 2026-10-20 01:30 ·') and eintrag.hash in spur


def test_das_json_des_archivs_bleibt_bei_iso_mit_zeitzone(ordnung):  # noqa: F811
    '''Das JSON ist unverändert: ISO-Zeitstempel mit Versatz — eindeutig, für Maschinen.'''
    import json

    antrag = _antrag_am(ordnung, SOMMER)
    daten = json.loads(archivkern.als_json(antrag))
    assert datetime.fromisoformat(daten['antrag']['eingebracht_am']) == SOMMER


def test_ein_nur_auf_den_tag_gekuerzter_audit_eintrag_bleibt_ein_tag():
    '''Stimm-Ereignisse einer laufenden Abstimmung tragen öffentlich nur den Tag (schon in Ortszeit,
    ohne Versatz): Das Markdown rechnet daran nichts um und erfindet keine Uhrzeit.'''
    assert archivkern._ortszeit('2026-11-18T00:00:00', nur_tag=True) == '2026-11-18'
    assert archivkern._ortszeit('2026-11-18T00:00:00') == '2026-11-18 00:00'
    assert archivkern._ortszeit('2026-10-19T23:30:00+00:00') == '2026-10-20 01:30'
    assert archivkern._ortszeit('2026-10-19T23:30:00+00:00', nur_tag=True) == '2026-10-20'
    assert archivkern._ortszeit('kein Zeitstempel') == 'kein Zeitstempel'
