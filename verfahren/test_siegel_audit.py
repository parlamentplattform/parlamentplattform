'''Die Audit-Kette unter Riegel (Gesamtprüfung GP-130, Grundregel 7).

„Einträge werden nie geändert oder gelöscht — dafür gibt es keinen Code-Pfad“ war eine Zusage ohne
Riegel: `save`, `update` und `delete` gingen durch, und Einträge, die seit der letzten täglichen Prüfung
angehängt wurden, ließen sich spurlos entfernen. Jetzt wirft jeder dieser Wege; `anhaengen` arbeitet
unverändert.'''

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from plattform_core import GENESIS, ereignis_hash
from verfahren.audit_pruefung import pruefen
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def _kette(anzahl=3):
    return [AuditEintrag.anhaengen({'typ': 'probe', 'nr': i}) for i in range(anzahl)]


@pytest.mark.parametrize('weg', ['save', 'save_felder', 'update', 'bulk_update', 'delete', 'query_delete', 'alle_loeschen', 'umschreiben'])
def test_ein_audit_eintrag_laesst_sich_nicht_aendern_oder_loeschen(weg):
    eintraege = _kette()
    ziel = eintraege[1]
    vorher = list(AuditEintrag.objects.values_list('lfd', 'ereignis', 'vorgaenger', 'hash'))
    with pytest.raises(ValidationError):
        if weg == 'save':
            ziel.ereignis = {**ziel.ereignis, 'nr': 99}
            ziel.save()
        elif weg == 'save_felder':
            ziel.zeit = timezone.now()
            ziel.save(update_fields=['zeit'])
        elif weg == 'update':
            AuditEintrag.objects.filter(pk=ziel.pk).update(ereignis={**ziel.ereignis, 'nr': 99})
        elif weg == 'bulk_update':
            ziel.ereignis = {**ziel.ereignis, 'nr': 99}
            AuditEintrag.objects.bulk_update([ziel], ['ereignis'])
        elif weg == 'delete':
            ziel.delete()
        elif weg == 'query_delete':
            AuditEintrag.objects.filter(pk__in=[e.pk for e in eintraege[1:]]).delete()
        elif weg == 'alle_loeschen':
            AuditEintrag.objects.all().delete()
        else:
            AuditEintrag.objects.update_or_create(pk=ziel.pk, defaults={'ereignis': {'typ': 'probe', 'nr': 99}})
    assert list(AuditEintrag.objects.values_list('lfd', 'ereignis', 'vorgaenger', 'hash')) == vorher


def test_anhaengen_arbeitet_unveraendert():
    erster, zweiter, dritter = _kette()
    assert erster.vorgaenger == GENESIS and zweiter.vorgaenger == erster.hash and dritter.vorgaenger == zweiter.hash
    for eintrag in (erster, zweiter, dritter):
        assert eintrag.hash == ereignis_hash(eintrag.vorgaenger, eintrag.ereignis)
        assert eintrag.ereignis['zeit'] == eintrag.zeit.isoformat()  # ein Augenblick für Spalte und Siegel
    stand = pruefen(voll=True)
    assert stand['intakt'] and stand['eintraege'] == 3 and stand['kopf'] == dritter.hash


def test_der_noch_ungepruefte_schwanz_laesst_sich_nicht_mehr_abschneiden():
    '''RVB-06: Nach einer Prüfung drei Einträge anhängen, die letzten zwei löschen, einen neuen anhängen —
    die Vollprüfung fand danach nichts. Das Löschen selbst wirft jetzt.'''
    _kette(2)
    stand = pruefen(voll=True)
    neue = [AuditEintrag.anhaengen({'typ': 'probe', 'nr': 10 + i}) for i in range(3)]
    with pytest.raises(ValidationError):
        AuditEintrag.objects.filter(pk__in=[e.pk for e in neue[1:]]).delete()
    AuditEintrag.anhaengen({'typ': 'probe', 'nr': 20})
    weiter = pruefen(stand=stand)
    assert weiter['intakt'] and AuditEintrag.objects.count() == 6


def test_alte_eintraege_ohne_versiegelte_zeit_bleiben_lesbar_und_die_kette_waechst_weiter():
    '''Altbestand: Einträge von vor 0.45 tragen keine `zeit` im Ereignis. Sie werden angelegt, wie eine
    Migration oder Wiederherstellung es tut (neue Zeilen sind erlaubt), bleiben prüfbar, und `anhaengen`
    hängt an sie an.'''
    kopf = GENESIS
    for nr in range(2):
        ereignis = {'typ': 'alt', 'nr': nr}
        wert = ereignis_hash(kopf, ereignis)
        AuditEintrag.objects.create(zeit=timezone.now(), ereignis=ereignis, vorgaenger=kopf, hash=wert)
        kopf = wert
    neu = AuditEintrag.anhaengen({'typ': 'probe', 'nr': 2})
    assert neu.vorgaenger == kopf
    assert pruefen(voll=True)['intakt'] is True
    assert str(AuditEintrag.objects.order_by('lfd').first()) == f'Audit #{AuditEintrag.objects.order_by("lfd").first().lfd} alt'
