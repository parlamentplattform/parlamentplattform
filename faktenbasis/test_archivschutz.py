"""Neue Python-Objekte und Stapel sind kein Weg zum Ersetzen amtlicher Fakten."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from faktenbasis import volltext
from faktenbasis.models import Norm, NormText, NormTextAbruf, RisImport, SchnappschussQuerySet
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture(params=[Norm, RisImport, NormText, NormTextAbruf])
def stand(request, norm, xml):  # noqa: F811
    abruf = volltext.importieren(norm)
    return {Norm: norm, RisImport: norm.importlauf, NormText: abruf.inhalt, NormTextAbruf: abruf}[request.param]


def kopie(stand):
    return type(stand)(**{f.attname: getattr(stand, f.attname) for f in stand._meta.concrete_fields})


def aenderung(stand):
    return {Norm: ("kurztitel", "Nachträglich ersetzt"), RisImport: ("treffer", 999),
            NormText: ("text", "Fremder Wortlaut"), NormTextAbruf: ("neu", False)}[type(stand)]


@pytest.mark.parametrize("weg", ["neues_objekt", "upsert", "bulk_update"])
def test_neuanlage_und_stapel_ersetzen_keinen_gespeicherten_faktenstand(stand, weg):
    modell = type(stand)
    vorher = modell.objects.filter(pk=stand.pk).values().get()
    neu = kopie(stand)
    feld, wert = aenderung(stand)
    setattr(neu, feld, wert)
    with transaction.atomic():
        with pytest.raises(ValidationError):
            if weg == "neues_objekt":
                assert neu._state.adding
                neu.save()
            elif weg == "upsert":
                modell.objects.bulk_create([neu], update_conflicts=True, update_fields=[feld], unique_fields=["pk"])
            else:
                modell.objects.bulk_update([neu], [feld])
        # Ein abgefangener Schreibschutzfehler darf keine äußere Transaktion vergiften.
        assert modell.objects.filter(pk=stand.pk).values().get() == vorher


def test_gleichzeitige_pk_kollision_faellt_nicht_auf_update_zurueck(stand, monkeypatch):
    modell = type(stand)
    vorher = modell.objects.filter(pk=stand.pk).values().get()
    neu = kopie(stand)
    feld, wert = aenderung(stand)
    setattr(neu, feld, wert)
    monkeypatch.setattr(SchnappschussQuerySet, "exists", lambda self: False)
    with pytest.raises(IntegrityError), transaction.atomic():
        neu.save()
    assert modell.objects.filter(pk=stand.pk).values().get() == vorher


def test_neue_importe_und_idempotente_dokumentuebernahme_bleiben_moeglich(norm, xml):  # noqa: F811
    erster = volltext.importieren(norm)
    zweiter = volltext.importieren(norm)
    assert erster.inhalt_id == zweiter.inhalt_id
    assert NormTextAbruf.objects.count() == 2 and NormText.objects.count() == 1
    # Auch ein neuer Stapel von Abrufbelegen wird nur angehängt.
    neu = kopie(zweiter)
    neu.pk = None
    eingefuegt, = NormTextAbruf.objects.bulk_create([neu])
    assert eingefuegt.pk not in {erster.pk, zweiter.pk} and NormTextAbruf.objects.count() == 3
