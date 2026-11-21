"""Ausrollfenster: Der alte Code schreibt weiter, während die neue Fassung die Datenbank schon migriert hat.

Beim Ausrollen migriert die neue Instanz, während die alte (Code der Live-Fassung) noch Anfragen bedient.
Eine neue NOT-NULL-Spalte an einer bestehenden Tabelle, deren Vorgabe nur in Python steht, ließe in diesem
Fenster jedes INSERT des alten Codes scheitern (Gesamtprüfung 0.115.0, Fund „Alter Code kann nach der
Migration keine Anmeldelinks mehr anlegen“). Mit `db_default` behält die Datenbank die Vorgabe.
"""

import pytest
from django.db import connection
from django.db.migrations import operations
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from verfahren.test_views_aktionen import mitglied_anlegen

#: Die jeweils letzte Migration der Live-Fassung 0.114.0 (f1209d0) je App.
LIVE_STAND = {
    'anstoss': '0001',
    'faktenbasis': '0012',
    'gremien': '0021',
    'ki': '0011',
    'mandatare': '0013',
    'mitglieder': '0025',
    'parameter': '0006',
    'uebersicht': '0001',
    'verfahren': '0030',
}


def _neue_migrationen():
    loader = MigrationLoader(None, ignore_no_migrations=True)
    for (app, name), migration in sorted(loader.disk_migrations.items()):
        stand = LIVE_STAND.get(app)
        if stand is not None and name[:4] > stand:
            yield app, name, migration


def test_neue_pflichtspalten_an_bestehenden_tabellen_tragen_ihre_vorgabe_in_der_datenbank():
    neu_angelegt = set()
    for app, _name, migration in _neue_migrationen():
        for op in migration.operations:
            if isinstance(op, operations.CreateModel):
                neu_angelegt.add((app, op.name_lower))
    fehlend = []
    for app, name, migration in _neue_migrationen():
        for op in migration.operations:
            if not isinstance(op, operations.AddField) or (app, op.model_name_lower) in neu_angelegt:
                continue
            feld = op.field
            if not feld.null and feld.has_default() and not feld.has_db_default():
                fehlend.append(f'{app}.{name}: {op.model_name}.{op.name}')
    assert fehlend == []


@pytest.mark.django_db
def test_alter_code_legt_einen_anmeldelink_ohne_ziel_an():
    """Der Code der Live-Fassung kennt `ziel` nicht und lässt die Spalte im INSERT weg."""
    mitglied = mitglied_anlegen('alt')
    jetzt = timezone.now()
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO mitglieder_einmaltoken (mitglied_id, zweck, token_hash, erstellt_am, gueltig_bis) '
            'VALUES (%s, %s, %s, %s, %s)',
            [mitglied.pk, 'login', 'a' * 64, jetzt, jetzt],
        )
        cursor.execute('SELECT ziel FROM mitglieder_einmaltoken WHERE token_hash = %s', ['a' * 64])
        assert cursor.fetchone()[0] == ''



@pytest.mark.django_db
def test_rueckweg_der_umsetzungsvermerke_wird_verweigert_sobald_ein_vermerk_besteht():
    """gremien 0024 leert das Feld am Beschluss; ein Rückweg löschte mit der Tabelle die Vermerke des Rates.
    Solange keiner besteht (leere Datenbank, Testläufe), verliert der Rückweg nichts und bleibt möglich."""
    import importlib
    from types import SimpleNamespace

    from django.apps import apps
    from django.db.migrations.exceptions import IrreversibleError

    from gremien.models import Umsetzungsvermerk
    from gremien.test_gp_runde2 import _entschiedener_beschluss, _rat

    migration = importlib.import_module('gremien.migrations.0024_umsetzungsvermerke_anfuegen')
    editor = SimpleNamespace(connection=connection)
    assert migration.rueckweg_pruefen(apps, editor) is None
    leute, _rollen = _rat(1, praefix='rueckweg')
    Umsetzungsvermerk.objects.create(beschluss=_entschiedener_beschluss(leute), nummer=1, text='Erledigt.')
    with pytest.raises(IrreversibleError):
        migration.rueckweg_pruefen(apps, editor)
    assert Umsetzungsvermerk.objects.count() == 1
