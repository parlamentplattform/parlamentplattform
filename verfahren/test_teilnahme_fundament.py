"""Noch nicht aktivierter Gebiets-/Kreisspeicher: Historie, Rechte und Datenschutz."""

from copy import deepcopy
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from mitglieder.models import (
    Gemeinde,
    Identitaetsstufe,
    Mitgliedsstatus,
    Wohnsitzart,
    stimmberechtigte_zaehlen,
)
from plattform_core import Gegenstand
from plattform_core.teilnehmerkreis import GebietsFehler
from verfahren.models import Antrag, AuditEintrag, OertlicheTeilnahme, antrag_einbringen
from verfahren.teilnahme import berechtigte_zaehlen, hauptgebiet, kreis_festhalten, oertlich_zulaessig
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def orte():
    a = Gemeinde.objects.create(kennziffer="40510", name="St. Marienkirchen an der Polsenz",
                                bezirk="Eferding", bundesland="oberoesterreich")
    b = Gemeinde.objects.create(kennziffer="41227", name="St. Marienkirchen am Hausruck",
                                bezirk="Ried", bundesland="oberoesterreich")
    return a, b


def mit_ort(name, ort, **kwargs):
    m = mitglied_anlegen(name, **kwargs)
    m.wohnsitz = ort
    m.wohnsitz_art = Wohnsitzart.OESTERREICH
    m.save(update_fields=["wohnsitz", "wohnsitz_art"])
    return m


def vorbereiten(vo, autor, ebene="gemeinde"):
    gebiet = hauptgebiet(autor, ebene)
    return Antrag.objects.create(titel="Kreisprüfung", eingebracht_von=autor,
                                 policy_snapshot=vo.als_policy().als_dict(), ebene=ebene,
                                 gebiet=gebiet.name, teilnahmegebiet=gebiet.als_dict())


def test_alte_verfahren_werden_nicht_nachbefuellt_oder_umgerechnet(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    fremd = mit_ort("fremd", orte[1])
    alt = antrag_einbringen(autor, "Altverfahren", "Wortlaut", "", ordnung, ebene="gemeinde", gebiet=orte[0].name)
    vorher = deepcopy(alt.policy_snapshot)
    audit = list(AuditEintrag.objects.values())
    assert alt.teilnahmegebiet is None and alt.teilnehmerkreis_am is None
    assert oertlich_zulaessig(alt, fremd)
    assert berechtigte_zaehlen(alt, Gegenstand.SACHFRAGE, timezone.localdate()) == stimmberechtigte_zaehlen(
        Gegenstand.SACHFRAGE, timezone.localdate(),
    )
    with pytest.raises(GebietsFehler, match="Altverfahren"):
        kreis_festhalten(alt)
    alt.refresh_from_db()
    assert alt.policy_snapshot == vorher and alt.teilnahmegebiet is None
    assert list(AuditEintrag.objects.values()) == audit
    assert not OertlicheTeilnahme.objects.exists()


def test_hauptwohnsitzkreis_bleibt_nach_beiden_umzugsrichtungen_erhalten(ordnung, orte):  # noqa: F811
    innen = mit_ort("innen", orte[0])
    aussen = mit_ort("aussen", orte[1])
    aussen.nebenwohnsitz = orte[0]
    aussen.save(update_fields=["nebenwohnsitz"])
    antrag = vorbereiten(ordnung, innen)
    kreis_festhalten(antrag)
    assert oertlich_zulaessig(antrag, innen) and not oertlich_zulaessig(antrag, aussen)
    innen.wohnsitz, aussen.wohnsitz = orte[1], orte[0]
    innen.save(update_fields=["wohnsitz"])
    aussen.save(update_fields=["wohnsitz"])
    innen.wohnsitz_art = Wohnsitzart.OHNE_FESTEN_WOHNSITZ
    innen.save(update_fields=["wohnsitz_art"])
    antrag.refresh_from_db()
    assert oertlich_zulaessig(antrag, innen) and not oertlich_zulaessig(antrag, aussen)
    assert antrag.teilnehmerkreis_am == antrag.eingebracht_am
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, timezone.localdate()) == 1


def test_spaeteres_konto_kommt_nicht_rueckwirkend_in_den_regionalen_kreis(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    neu = mit_ort("neu", orte[0])
    assert not oertlich_zulaessig(antrag, neu)
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, timezone.localdate()) == 1


def test_territoriale_aufnahme_ersetzt_nicht_die_allgemeine_stichtagspruefung(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    ungeprueft = mit_ort("ungeprueft", orte[0], stufe=Identitaetsstufe.UNGEPRUEFT)
    test = mit_ort("test", orte[0])
    test.testkonto = True
    test.save(update_fields=["testkonto"])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    assert oertlich_zulaessig(antrag, ungeprueft) and not oertlich_zulaessig(antrag, test)
    tag = timezone.localdate()
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, tag) == 1
    ungeprueft.identitaetsstufe = Identitaetsstufe.GEPRUEFT
    ungeprueft.geprueft_seit = tag + timedelta(days=1)
    ungeprueft.save(update_fields=["identitaetsstufe", "geprueft_seit"])
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, tag) == 1
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, tag + timedelta(days=1)) == 2
    autor.status = Mitgliedsstatus.PAUSIERT
    autor.save(update_fields=["status"])
    assert oertlich_zulaessig(antrag, autor)
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, tag) == 0


@pytest.mark.parametrize("art", [Wohnsitzart.AUSLAND, Wohnsitzart.OHNE_FESTEN_WOHNSITZ])
def test_explizite_wohnart_gewinnt_gegen_veraltete_haupt_fk(ordnung, orte, art):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    fremd = mit_ort("fremd", orte[0])
    fremd.wohnsitz_art = art
    fremd.save(update_fields=["wohnsitz_art"])
    with pytest.raises(GebietsFehler, match="Hauptwohnsitz"):
        hauptgebiet(fremd, "gemeinde")
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    assert not oertlich_zulaessig(antrag, fremd)


def test_bundesverfahren_bleibt_auch_fuer_neue_konten_ohne_hauptwohnsitz_offen(ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor")
    antrag = vorbereiten(ordnung, autor, "bund")
    kreis_festhalten(antrag)
    neu = mitglied_anlegen("neu")
    neu.wohnsitz_art = Wohnsitzart.OHNE_FESTEN_WOHNSITZ
    neu.save(update_fields=["wohnsitz_art"])
    assert oertlich_zulaessig(antrag, neu)
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, timezone.localdate()) == 2
    assert not antrag.oertlicher_kreis.exists()


def test_unvollstaendiger_neuer_kreis_verleiht_keine_territorialen_rechte(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)
    assert not oertlich_zulaessig(antrag, autor)
    assert not oertlich_zulaessig(antrag, AnonymousUser())
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, timezone.localdate()) == 0


def test_festgehaltener_kreis_ist_keine_neuberechnung_bei_erneutem_aufruf(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    before = (antrag.teilnahmegebiet, antrag.teilnehmerkreis_am, list(antrag.oertlicher_kreis.values_list("pk", flat=True)))
    mit_ort("neu", orte[0])
    with pytest.raises(GebietsFehler, match="bereits festgehalten"):
        kreis_festhalten(antrag)
    antrag.refresh_from_db()
    assert (antrag.teilnahmegebiet, antrag.teilnehmerkreis_am,
            list(antrag.oertlicher_kreis.values_list("pk", flat=True))) == before


def test_fehler_beim_audit_rollt_den_ganzen_neuen_kreis_zurueck(ordnung, orte, monkeypatch):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)

    def fehler(_ereignis):
        raise RuntimeError("Abbruch der gesamten Transaktion")

    monkeypatch.setattr(AuditEintrag, "anhaengen", fehler)
    with pytest.raises(RuntimeError):
        kreis_festhalten(antrag)
    antrag.refresh_from_db()
    assert antrag.teilnehmerkreis_am is None and not antrag.oertlicher_kreis.exists()


def test_oeffentliches_audit_enthaelt_keine_privaten_kreiszuordnungen(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    event = AuditEintrag.objects.get(ereignis__typ="teilnehmerkreis_festgehalten").ereignis
    assert set(event) == {"typ", "antrag", "fassung", "gebiet", "festgehalten_am", "zeit"}
    with pytest.raises(ProtectedError):
        autor.delete()


def test_frische_datenbankangabe_statt_manipuliertem_aufrufobjekt(orte):
    autor = mit_ort("autor", orte[0])
    autor.wohnsitz = orte[1]  # nicht gespeichert, nicht als Selbstdeklaration akzeptieren
    assert hauptgebiet(autor, "gemeinde").gemeinden == (orte[0].kennziffer,)


@pytest.mark.parametrize("weg", ["save", "update", "bulk_update", "delete", "query_delete", "neu", "bulk_neu"])
def test_kreiszuordnung_kann_nach_festhaltung_nicht_geaendert_werden(ordnung, orte, weg):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    fremd = mit_ort("fremd", orte[1])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    eintrag = antrag.oertlicher_kreis.get()
    with pytest.raises(ValidationError):
        if weg == "save":
            eintrag.mitglied = fremd
            eintrag.save()
        elif weg == "update":
            antrag.oertlicher_kreis.update(mitglied=fremd)
        elif weg == "bulk_update":
            eintrag.mitglied = fremd
            OertlicheTeilnahme.objects.bulk_update([eintrag], ["mitglied"])
        elif weg == "delete":
            eintrag.delete()
        elif weg == "query_delete":
            antrag.oertlicher_kreis.all().delete()
        elif weg == "neu":
            antrag.oertlicher_kreis.create(mitglied=fremd)
        else:
            OertlicheTeilnahme.objects.bulk_create([OertlicheTeilnahme(antrag=antrag, mitglied=fremd)])
    assert list(antrag.oertlicher_kreis.values_list("mitglied_id", flat=True)) == [autor.pk]


def test_abweichende_gebietsebene_kann_nicht_als_bund_festgehalten_werden(ordnung, orte):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    gebiet = hauptgebiet(autor, "bund")
    antrag = Antrag.objects.create(titel="Widerspruch", eingebracht_von=autor, ebene="gemeinde",
                                   policy_snapshot=ordnung.als_policy().als_dict(), teilnahmegebiet=gebiet.als_dict())
    with pytest.raises(GebietsFehler, match="widersprechen"):
        kreis_festhalten(antrag)


@pytest.mark.parametrize("feld,wert", [
    ("teilnahmegebiet", None), ("teilnahmegebiet", {"fassung": 42}),
    ("teilnehmerkreis_am", None), ("ebene", "bund"), ("gebiet", "Falscher Ort"),
])
@pytest.mark.parametrize("weg", ["save", "update", "bulk_update"])
def test_auch_gebietsstand_und_stichtag_bleiben_fest(ordnung, orte, feld, wert, weg):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    vorher = (deepcopy(antrag.teilnahmegebiet), antrag.teilnehmerkreis_am, antrag.ebene, antrag.gebiet)
    with pytest.raises(ValidationError):
        if weg == "update":
            Antrag.objects.filter(pk=antrag.pk).update(**{feld: wert})
        else:
            setattr(antrag, feld, wert)
            if weg == "save":
                antrag.save(update_fields=[feld])
            else:
                Antrag.objects.bulk_update([antrag], [feld])
    antrag.refresh_from_db()
    assert (antrag.teilnahmegebiet, antrag.teilnehmerkreis_am, antrag.ebene, antrag.gebiet) == vorher


@pytest.mark.parametrize("weg", ["save", "update", "bulk_update"])
def test_altverfahren_erhaelt_auch_nicht_durch_generischen_schreibweg_einen_kreis(ordnung, orte, weg):  # noqa: F811
    autor = mit_ort("autor", orte[0])
    alt = antrag_einbringen(autor, "Historisch", "Wortlaut", "", ordnung)
    wert = hauptgebiet(autor, "gemeinde").als_dict()
    with pytest.raises(ValidationError):
        if weg == "update":
            Antrag.objects.filter(pk=alt.pk).update(teilnahmegebiet=wert)
        else:
            alt.teilnahmegebiet = wert
            if weg == "save":
                alt.save()
            else:
                Antrag.objects.bulk_update([alt], ["teilnahmegebiet"])
    alt.refresh_from_db()
    assert alt.teilnahmegebiet is None and alt.teilnehmerkreis_am is None
