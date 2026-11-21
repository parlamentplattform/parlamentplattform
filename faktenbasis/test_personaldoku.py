"""Die Dokumentation der Personaldaten sagt dasselbe wie die Quellenseiten (GP-152): Neue
Rechtsfolgenaufträge erhalten Aggregat und Ressorttabelle als Bestandsrahmen."""

from pathlib import Path

from django.conf import settings

from ki.folgenkontext import _eingabe


def _doku(name):
    return ' '.join(Path(settings.BASE_DIR, 'docs', name).read_text(encoding='utf-8').split())


def test_folgeneingabe_enthaelt_die_personalgrundlage():
    import inspect

    assert 'personal_bestandsgrundlage' in inspect.getsource(_eingabe)


def test_personalressorts_doku_bestreitet_die_uebernahme_nicht():
    text = _doku('PERSONALRESSORTS.md')
    assert 'nicht automatisch in Modellaufträge' not in text
    assert 'Neue Rechtsfolgenaufträge der Zukunftswerkstatt erhalten' in text and 'Bestandsrahmen' in text


def test_faktenbasis_doku_nennt_den_bestandsrahmen():
    assert 'Personal-Bestandsrahmen' in _doku('FAKTENBASIS.md')
