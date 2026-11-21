'''Größe der Normseite bei mehreren gespeicherten Dokumenttexten (GP-153, Q-04).'''

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

import pytest
from django.urls import reverse

from faktenbasis.models import Norm, NormText, RisImport

pytestmark = pytest.mark.django_db

ERFASST = datetime(2026, 11, 2, 15, tzinfo=UTC)
ZEICHEN = 'Wortlaut der Lastprobe. ' * 20000  # rund 480.000 Zeichen je Text


def _norm_mit_texten(anzahl=5, ris_id='NOR40000001'):
    lauf = RisImport.objects.create(gesetzesnummer='10000001', stand=date(2026, 11, 1), erfolgreich=True,
                                    treffer=1, gelesen=1, neu=1)
    norm = Norm.objects.create(ris_id=ris_id, gesetzesnummer='10000001', kurztitel='Synthetisch',
                               abschnitt='§ 1', stand=date(2026, 11, 1), quelle='https://ris.bka.gv.at/x',
                               rohdaten={'s': 'r' * 20000}, inhalt_hash=sha256(ris_id.encode()).hexdigest(), importlauf=lauf)
    texte = []
    for i in range(anzahl):
        inhalt = f'<x>{ris_id} {i}</x>'.encode()
        texte.append(NormText.objects.create(
            norm=norm, quelle=norm.quelle, xml=inhalt, text=f'Fassung {i} ' + ZEICHEN,
            xml_hash=sha256(inhalt).hexdigest(), parser_fassung=3, erfasst_am=ERFASST + timedelta(days=i)))
    return norm, texte


def test_normseite_bettet_nur_einen_dokumenttext_ein(client):
    '''0.114.0: alle fünf Texte im HTML, 2.515.882 Bytes. Jetzt steht nur der jüngste Text in der Seite;
    jeder weitere ist über seine eigene Adresse (?text=) erreichbar.'''
    norm, texte = _norm_mit_texten()
    adresse = reverse('faktenbasis:norm', args=[norm.pk])
    antwort = client.get(adresse)
    html = antwort.content.decode()
    print(f'NORMSEITE 5 Texte: status={antwort.status_code} bytes={len(antwort.content)}')
    assert antwort.status_code == 200
    assert len(antwort.content) < 700_000
    juengster = texte[-1]
    assert [i for i in range(len(texte)) if f'Fassung {i} Wortlaut' in html] == [len(texte) - 1]
    for t in texte:
        assert f'id="dokumenttext-{t.pk}"' in html
        assert reverse('faktenbasis:textxml', args=[t.pk]) in html
    for t in texte[:-1]:
        assert f'href="{adresse}?text={t.pk}#dokumenttext-{t.pk}"' in html
    assert f'?text={juengster.pk}#' not in html

    gewaehlt = client.get(adresse, {'text': texte[0].pk}).content.decode()
    assert 'Fassung 0 ' in gewaehlt and f'Fassung {len(texte) - 1} ' not in gewaehlt
    assert len(gewaehlt.encode()) < 700_000


@pytest.mark.parametrize('wert', ['x', '0', '-1', 'fremd'])
def test_unbekannter_dokumenttext_zeigt_den_juengsten(client, wert):
    norm, _texte = _norm_mit_texten(2)
    if wert == 'fremd':
        _andere, (fremder_text,) = _norm_mit_texten(1, ris_id='NOR40000002')
        wert = str(fremder_text.pk)
    html = client.get(reverse('faktenbasis:norm', args=[norm.pk]), {'text': wert}).content.decode()
    assert 'Fassung 1 ' in html and 'Fassung 0 ' not in html
