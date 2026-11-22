'''Die Historie des Registers unter Riegel (Gesamtprüfung GP-130, Grundregel 7, § 6 Abs 11 lit c).

Die Historie eines Registerwerts hing mit CASCADE am Parameter: Eine Zeile entfernte sie, und der Wert
entstand beim nächsten Aufruf ohne Geschichte neu. Jetzt schützt PROTECT Historie und Tests vor dem
Löschen ihres Parameters, und eine geschriebene Änderung lässt sich weder ändern noch löschen.'''

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from django.utils import timezone

from parameter.models import Aenderung, Parameter, ParameterTest
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def _parameter(schluessel='siegel-probe', wert='14'):
    return Parameter.objects.create(schluessel=schluessel, wert=wert, einheit='Tage', beschreibung='Probe', quelle='§ 5 Abs 12')


def _aenderung(parameter, neu='21'):
    return Aenderung.objects.create(
        parameter=parameter, alter_wert=parameter.wert, neuer_wert=neu, grund='Erprobung.', durch='Verwaltung',
    )


def _test(parameter):
    return ParameterTest.objects.create(
        parameter=parameter, testwert='9', alter_wert=parameter.wert, hypothese='Probe', messgroesse='motions.total',
        ende=timezone.localdate() + timedelta(days=30), rueckweg='Von selbst.', angeordnet_von=mitglied_anlegen('korat'),
    )


# --- PROTECT statt CASCADE ----------------------------------------------------------------------------------


@pytest.mark.parametrize('weg', ['delete', 'query_delete'])
def test_ein_parameter_mit_historie_laesst_sich_nicht_loeschen(weg):
    parameter = _parameter()
    _aenderung(parameter)
    with pytest.raises(ProtectedError):
        if weg == 'delete':
            parameter.delete()
        else:
            Parameter.objects.filter(pk=parameter.pk).delete()
    assert Parameter.objects.filter(pk=parameter.pk).exists() and parameter.historie.count() == 1


def test_ein_parameter_mit_test_laesst_sich_nicht_loeschen():
    parameter = _parameter()
    _test(parameter)
    with pytest.raises(ProtectedError):
        parameter.delete()
    assert parameter.tests.count() == 1


def test_ein_parameter_ohne_historie_bleibt_loeschbar():
    '''Der bestehende Löschweg (ein eben angelegter Eintrag ohne Geschichte, etwa in Tests) geht weiter.'''
    parameter = _parameter()
    parameter.delete()
    assert not Parameter.objects.filter(schluessel='siegel-probe').exists()


# --- Schreibriegel an der Änderung ----------------------------------------------------------------------------


@pytest.mark.parametrize('weg', ['save', 'save_felder', 'update', 'bulk_update', 'delete', 'query_delete', 'umschreiben'])
def test_eine_geschriebene_aenderung_laesst_sich_nicht_aendern_oder_loeschen(weg):
    parameter = _parameter()
    aenderung = _aenderung(parameter)
    with pytest.raises(ValidationError):
        if weg == 'save':
            aenderung.grund = 'Ein anderer Grund.'
            aenderung.save()
        elif weg == 'save_felder':
            aenderung.neuer_wert = '99'
            aenderung.save(update_fields=['neuer_wert'])
        elif weg == 'update':
            parameter.historie.update(grund='Ein anderer Grund.')
        elif weg == 'bulk_update':
            aenderung.grund = 'Ein anderer Grund.'
            Aenderung.objects.bulk_update([aenderung], ['grund'])
        elif weg == 'delete':
            aenderung.delete()
        elif weg == 'query_delete':
            Aenderung.objects.filter(parameter=parameter).delete()
        else:
            Aenderung.objects.update_or_create(pk=aenderung.pk, defaults={'grund': 'Ein anderer Grund.'})
    assert list(parameter.historie.values_list('alter_wert', 'neuer_wert', 'grund')) == [('14', '21', 'Erprobung.')]


def test_die_verwaltung_schreibt_die_historie_weiter(client):
    '''Der reguläre Weg: Die Verwaltung ändert einen Wert mit Grund — Historie und Audit-Kette wachsen,
    und eine zweite Änderung hängt sich an die erste.'''
    admin = mitglied_anlegen('admin')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    client.get(reverse('parameter:verwaltung'))  # legt den Erstbestand an
    eintrag = Parameter.objects.get(schluessel='gremien-review-tage')
    for wert in ('7', '10'):
        client.post(reverse('parameter:verwaltung_aktion'), {'parameter': eintrag.pk, 'wert': wert, 'grund': 'Erprobung.'})
    assert [(a.alter_wert, a.neuer_wert) for a in eintrag.historie.order_by('geaendert_am', 'pk')] == [('14', '7'), ('7', '10')]
    assert AuditEintrag.objects.filter(ereignis__typ='parameter_geaendert').count() == 2
    with pytest.raises(ProtectedError):
        eintrag.delete()


# --- Die Migration mit Altbestand ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_die_migration_behaelt_historie_und_tests_des_altbestands():
    '''Altbestand von vor dieser Fassung: Parameter mit Historie und Test, angelegt mit CASCADE. Die
    Migration ändert nur die Löschregel — jede Zeile bleibt, wie sie war, und ein zweiter Lauf tut nichts.'''
    ziel = [('parameter', '0007_historie_geschuetzt')]
    davor = [('parameter', '0006_gruppe_mandatare')]
    executor = MigrationExecutor(connection)
    blaetter = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(davor)
        alt = executor.loader.project_state(davor).apps
        parameter = alt.get_model('parameter', 'Parameter').objects.create(
            schluessel='altbestand-probe', wert='14', beschreibung='Probe', quelle='§ 5',
        )
        aenderung = alt.get_model('parameter', 'Aenderung').objects.create(
            parameter_id=parameter.pk, alter_wert='10', neuer_wert='14', grund='Damals.', durch='Verwaltung',
        )
        vorher = list(alt.get_model('parameter', 'Aenderung').objects.values())

        executor = MigrationExecutor(connection)
        executor.migrate(ziel)
        neu = executor.loader.project_state(ziel).apps
        assert list(neu.get_model('parameter', 'Aenderung').objects.values()) == vorher
        assert neu.get_model('parameter', 'Parameter').objects.filter(pk=parameter.pk).exists()
        MigrationExecutor(connection).migrate(ziel)  # wiederholtes Deploy-Migrate
        assert list(neu.get_model('parameter', 'Aenderung').objects.values()) == vorher
    finally:
        MigrationExecutor(connection).migrate(blaetter)
    # Mit den heutigen Modellen: Der Altbestand ist geschützt wie jede neue Zeile.
    with pytest.raises(ProtectedError):
        Parameter.objects.get(pk=parameter.pk).delete()
    with pytest.raises(ValidationError):
        Aenderung.objects.filter(pk=aenderung.pk).update(grund='Umgeschrieben.')
    assert Aenderung.objects.get(pk=aenderung.pk).grund == 'Damals.'
