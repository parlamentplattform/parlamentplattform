"""Archiveingaben und -antworten über dieselben ORM-Wege unveränderlich halten."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ki.models import KIAuftrag, KILauf, Zweck
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def lauf(a):  # noqa: F811
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    return job.lauf


@pytest.mark.parametrize("feld,wert", [("antwort", "Nachträglich ersetzt"), ("erfolgreich", False),
                                      ("modell", "anderes-modell"), ("tokens_ein", 999)])
@pytest.mark.parametrize("weg", ["save", "update", "bulk_update", "bulk_create"])
def test_fertiger_lauf_ist_auch_ausserhalb_der_eingabe_unveraenderlich(lauf, feld, wert, weg):
    vorher = KILauf.objects.filter(pk=lauf.pk).values().get()
    with transaction.atomic():
        with pytest.raises(ValidationError):
            setattr(lauf, feld, wert)
            if weg == "save":
                lauf.save(update_fields=[feld])
            elif weg == "update":
                KILauf.objects.filter(pk=lauf.pk).update(**{feld: wert})
            elif weg == "bulk_update":
                KILauf.objects.bulk_update([lauf], [feld])
            else:
                KILauf.objects.bulk_create([lauf], update_conflicts=True, update_fields=[feld], unique_fields=["pk"])
        assert KILauf.objects.filter(pk=lauf.pk).values().get() == vorher


@pytest.mark.parametrize("modell", [KIAuftrag, KILauf])
@pytest.mark.parametrize("weg", ["delete", "queryset_delete"])
def test_lauf_und_auftrag_bleiben_bei_loeschversuchen_erhalten(lauf, modell, weg):
    obj = lauf if modell is KILauf else KIAuftrag.objects.get(lauf=lauf)
    with pytest.raises(ValidationError):
        obj.delete() if weg == "delete" else modell.objects.filter(pk=obj.pk).delete()
    assert modell.objects.filter(pk=obj.pk).exists()


def test_neues_python_objekt_mit_bestehender_pk_ist_keine_neue_archivzeile(lauf):
    kopie = KILauf(**{f.attname: getattr(lauf, f.attname) for f in KILauf._meta.concrete_fields})
    assert kopie._state.adding
    kopie.antwort = "Falsche Neuanlage"
    with pytest.raises(ValidationError):
        kopie.save()
    assert KILauf.objects.get(pk=lauf.pk).antwort == lauf.antwort


def test_bestehende_auftrag_pk_umgeht_quellenschutz_nicht(lauf):
    job = KIAuftrag.objects.get(lauf=lauf)
    kopie = KIAuftrag(**{f.attname: getattr(job, f.attname) for f in KIAuftrag._meta.concrete_fields})
    assert kopie._state.adding
    kopie.kontext = {}
    with pytest.raises(ValidationError):
        kopie.save()
    assert KIAuftrag.objects.get(pk=job.pk).kontext == job.kontext


@pytest.mark.parametrize("feld", ["angefordert_von", "erstellt_am"])
def test_auftrag_haelt_auch_urheber_und_einreihzeitpunkt_fest(lauf, feld):
    job = KIAuftrag.objects.get(lauf=lauf)
    neu = mitglied_anlegen("anderer-urheber") if feld == "angefordert_von" else job.erstellt_am + timedelta(days=1)
    setattr(job, feld, neu)
    with pytest.raises(ValidationError):
        job.save(update_fields=[feld])
    with pytest.raises(ValidationError):
        KIAuftrag.objects.filter(pk=job.pk).update(**{feld: neu})
    # Betrieblich veränderliche Zustände bleiben unabhängig vom Identitätsschutz.
    KIAuftrag.objects.filter(pk=job.pk).update(versuche=5)
    assert KIAuftrag.objects.get(pk=job.pk).versuche == 5


@pytest.mark.parametrize("modell", [KIAuftrag, KILauf])
def test_neuanlage_faellt_bei_nebenlaeufiger_pk_kollision_nie_auf_update_zurueck(lauf, modell, monkeypatch):
    original = lauf if modell is KILauf else KIAuftrag.objects.get(lauf=lauf)
    vorher = modell.objects.filter(pk=original.pk).values().get()
    kopie = modell(**{f.attname: getattr(original, f.attname) for f in modell._meta.concrete_fields})
    if modell is KILauf:
        kopie.antwort = "Kollision"
    else:
        kopie.status = "gescheitert"
    # Die vorangehende Existenzabfrage kann eine noch nicht bestätigte parallele
    # Anlage übersehen. Die eigentliche SQL-Operation muss trotzdem INSERT bleiben.
    monkeypatch.setattr(type(modell.objects.all()), "exists", lambda self: False)
    with pytest.raises(IntegrityError), transaction.atomic():
        kopie.save()
    assert modell.objects.filter(pk=original.pk).values().get() == vorher


def test_neue_laeufe_duerfen_weiter_angehaengt_werden_auch_als_stapel(lauf):
    felder = {f.attname: getattr(lauf, f.attname) for f in KILauf._meta.concrete_fields if not f.primary_key}
    neu = KILauf(**felder)
    neu.save()
    stapel, = KILauf.objects.bulk_create([KILauf(**felder)])
    assert neu.pk != lauf.pk and stapel.pk not in {neu.pk, lauf.pk} and KILauf.objects.count() == 3
