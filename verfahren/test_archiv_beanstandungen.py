'''Öffentliche Beanstandungen im Archiv eines Antrags (Gesamtprüfung GP-085, § 6 Abs 11 lit b).

Wer das Archiv sichert, bekam nur Beanstandungen mit Korrekturauftrag — und im Markdown gar keine.
Beide Exportformen nennen jetzt jede Beanstandung mit Text, Zeitpunkt, beanstandetem Lauf und dem Stand
der Nachrechnung: keine, angefordert, erledigt (oder gescheitert). Ohne Namen.'''

import json

import pytest
from django.urls import reverse

from ki.korrekturen import anfordern
from ki.models import Auftragsstatus, KIAuftrag
from ki.test_korrekturen import fall  # noqa: F401
from verfahren import archiv as archivkern
from verfahren.models import Beanstandung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

EINWAND_A = 'EINWAND-A ohne Nachrechnung: Zuständigkeit falsch.'
EINWAND_B = 'EINWAND-B mit Nachrechnung: Norm fehlt.'


def _zwei_beanstandungen(fall):  # noqa: F811
    a, m, _rolle, alt, erste = fall
    andere = mitglied_anlegen('einwenderin')
    andere.first_name, andere.last_name, andere.klarname_oeffentlich = 'Erna', 'Einwand', True
    andere.save()
    ohne = Beanstandung.objects.create(antrag=a, lauf=alt.lauf, mitglied=andere, text=EINWAND_A)
    mit = Beanstandung.objects.create(antrag=a, lauf=alt.lauf, mitglied=m, text=EINWAND_B)
    auftrag = anfordern(mit, m)
    return a, alt, erste, ohne, mit, auftrag


def test_beide_exportformen_nennen_jede_beanstandung_mit_ihrem_stand(client, fall):  # noqa: F811
    a, alt, erste, ohne, mit, auftrag = _zwei_beanstandungen(fall)
    daten = json.loads(client.get(reverse('verfahren:archiv_export', kwargs={'pk': a.pk, 'art': 'json'})).content)
    je_id = {b['id']: b for b in daten['beanstandungen']}
    assert set(je_id) == {erste.pk, ohne.pk, mit.pk}
    assert je_id[ohne.pk]['text'] == EINWAND_A and je_id[ohne.pk]['nachrechnung'] == 'keine'
    assert je_id[ohne.pk]['lauf'] == alt.lauf_id and je_id[ohne.pk]['erstellt_am'] == ohne.erstellt_am.isoformat()
    assert je_id[ohne.pk]['nachrechnung_auftrag'] is None
    assert je_id[mit.pk]['text'] == EINWAND_B and je_id[mit.pk]['nachrechnung'] == 'angefordert'
    assert je_id[mit.pk]['nachrechnung_auftrag'] == auftrag.pk
    assert [b['id'] for b in daten['beanstandungen']] == [erste.pk, ohne.pk, mit.pk]  # in der Reihenfolge des Eingangs
    markdown = client.get(reverse('verfahren:archiv_export', kwargs={'pk': a.pk, 'art': 'md'})).content.decode()
    assert EINWAND_A in markdown and EINWAND_B in markdown
    zeile_a = next(z for z in markdown.split('\n') if f'**Beanstandung #{ohne.pk}**' in z)
    zeile_b = next(z for z in markdown.split('\n') if f'**Beanstandung #{mit.pk}**' in z)
    assert 'keine Nachrechnung' in zeile_a and f'#{alt.lauf_id}' in zeile_a
    assert 'Nachrechnung angefordert' in zeile_b


def test_der_stand_folgt_dem_auftrag_erledigt_und_gescheitert(fall):  # noqa: F811
    a, _alt, _erste, _ohne, mit, auftrag = _zwei_beanstandungen(fall)
    for status, stand, wort in (
        (Auftragsstatus.LAEUFT, 'angefordert', 'Nachrechnung angefordert'),
        (Auftragsstatus.ERLEDIGT, 'erledigt', 'Nachrechnung erledigt'),
        (Auftragsstatus.GESCHEITERT, 'gescheitert', 'Nachrechnung gescheitert'),
    ):
        KIAuftrag.objects.filter(pk=auftrag.pk).update(status=status)
        eintrag = next(b for b in archivkern.beanstandungen(a) if b['id'] == mit.pk)
        assert eintrag['nachrechnung'] == stand
        zeile = next(z for z in archivkern.als_markdown(a).split('\n') if f'**Beanstandung #{mit.pk}**' in z)
        assert wort in zeile


def test_die_exporte_nennen_keinen_namen_der_beanstandenden(fall):  # noqa: F811
    a, _alt, _erste, _ohne, _mit, _auftrag = _zwei_beanstandungen(fall)
    for eintrag in archivkern.beanstandungen(a):
        assert 'Einwand' not in json.dumps(eintrag, ensure_ascii=False) and 'mitglied' not in eintrag
    abschnitt = archivkern.als_markdown(a).split('## Beanstandungen', 1)[1].split('\n## ', 1)[0]
    assert 'Erna' not in abschnitt and 'einwenderin' not in abschnitt


def test_ein_alter_erledigungsvermerk_ohne_auftrag_steht_als_erledigt_im_export(ordnung):  # noqa: F811
    '''Altbestand: Vor den Nachrechnungen trug die Beanstandung selbst Erledigungstag und Vermerk, ohne
    Lauf und ohne Auftrag. Der Export nennt sie mit ihrem Vermerk.'''
    from django.utils import timezone

    m = mitglied_anlegen('altfall')
    a = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    jetzt = timezone.now()
    alt = Beanstandung.objects.create(
        antrag=a, lauf=None, mitglied=m, text='Die Kosten sind zu niedrig angesetzt.',
        erledigt_am=jetzt, erledigt_vermerk='Neu gerechnet, die Zahl wurde berichtigt.',
    )
    (eintrag,) = archivkern.beanstandungen(a)
    assert eintrag['id'] == alt.pk and eintrag['lauf'] is None and eintrag['nachrechnung'] == 'erledigt'
    assert eintrag['erledigt_am'] == jetzt.isoformat()
    assert eintrag['erledigt_vermerk'] == 'Neu gerechnet, die Zahl wurde berichtigt.'
    markdown = archivkern.als_markdown(a)
    assert 'Die Kosten sind zu niedrig angesetzt.' in markdown and 'Neu gerechnet, die Zahl wurde berichtigt.' in markdown


def test_ohne_beanstandung_bleibt_die_liste_leer_und_der_abschnitt_weg(ordnung):  # noqa: F811
    a = antrag_einbringen(mitglied_anlegen('ruhig'), **ANTRAG, ordnung=ordnung)
    assert json.loads(archivkern.als_json(a))['beanstandungen'] == []
    assert 'Beanstandung' not in archivkern.als_markdown(a)
