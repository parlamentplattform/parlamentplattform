"""Was der Steckplatz aus der Antwort des Anbieters liest: Abbruchgrund (GP-143) und fehlende
Verbrauchsangabe (GP-145). Kein Netz: Der Versand ist durch eine Attrappe ersetzt."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import pytest
from django.urls import reverse

from ki.anbieter import Antwort, AttrappenAnbieter, MistralAnbieter
from ki.models import Auftragsstatus, KILauf, Zweck
from ki.test_folgenauftraege import attrappe, neu  # noqa: F401
from ki.test_kontext import antrag  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, warteschlange_stand
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _mistral(monkeypatch, daten):
    gesendet = []

    def senden(self, endpunkt, rumpf, zeitgrenze=None):
        gesendet.append(rumpf)
        return daten

    monkeypatch.setattr(MistralAnbieter, '_senden', senden)
    return MistralAnbieter('attrappen-wert', 'test-modell'), gesendet


def test_der_adapter_liest_den_abbruchgrund(monkeypatch):
    anbieter, _ = _mistral(monkeypatch, {
        'model': 'test-modell', 'usage': {'prompt_tokens': 5, 'completion_tokens': 900},
        'choices': [{'message': {'content': '{"normen": [{"titel": "Abgebro'}, 'finish_reason': 'length'}],
    })
    antwort = anbieter.frage('Auftrag', 'Eingabe')
    assert antwort.abbruchgrund == 'length' and antwort.tokens_aus == 900
    anbieter, _ = _mistral(monkeypatch, {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]})
    assert anbieter.frage('Auftrag', 'Eingabe').abbruchgrund == 'stop'


def test_abgeschnittene_antwort_zaehlt_nicht_als_erledigt(antrag, attrappe, monkeypatch, client):
    aufrufe = []

    def abgeschnitten(self, auftrag, eingabe):
        aufrufe.append(1)
        return Antwort('{"normen": [{"titel": "Abgebro', 'test-modell', 10, 900, abbruchgrund='length')

    monkeypatch.setattr(AttrappenAnbieter, 'frage', abgeschnitten)
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == 'gescheitert'
    job.refresh_from_db()
    assert len(aufrufe) == 1 and job.versuche == 1  # keine sechsfache Wiederholung derselben Grenze
    assert job.status == Auftragsstatus.GESCHEITERT and job.lauf is not None
    lauf = job.lauf
    assert not lauf.erfolgreich and lauf.fehlercode == 'abgeschnitten' and 'length' in lauf.fehler
    assert lauf.antwort.startswith('{"normen"') and lauf.tokens_aus == 900  # Wortlaut und Verbrauch im Archiv
    zeile = next(z for z in warteschlange_stand()['zwecke'] if z['zweck'] == Zweck.RECHTSFOLGEN)
    assert zeile['erledigt'] == 0 and zeile['gescheitert'] == 1
    html = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'an der Längengrenze abgeschnitten' in html
    assert 'alle Versuche aufgebraucht' not in html


def test_vollstaendige_antwort_bleibt_erledigt(antrag, attrappe, monkeypatch):
    from ki.test_folgenauftraege import ANTWORT

    monkeypatch.setattr(AttrappenAnbieter, 'frage',
                        lambda self, a, e: Antwort(ANTWORT, 'test-modell', 1, 2, abbruchgrund='stop'))
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == 'erledigt'
    assert KILauf.objects.get(pk=job.__class__.objects.get(pk=job.pk).lauf_id).erfolgreich

