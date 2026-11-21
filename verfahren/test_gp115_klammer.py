'''Speichern und Audit-Eintrag gelingen gemeinsam oder gar nicht (Gesamtprüfung GP-129).

Drei Stellen in verfahren/models.py schrieben erst die Zeile und hängten danach den Eintrag an, ohne
gemeinsame Transaktion: Scheiterte das Anhängen, blieb eine Handlung ohne Spur in der Kette zurück.'''

import pytest
from django.core.management import call_command

from verfahren.models import (
    Antrag,
    AuditEintrag,
    Bewerbung,
    Vollzugseintrag,
    antrag_einbringen,
    bewerbung_einreichen,
    kategorien_zuordnen,
    vollzug_fortschreiben,
)
from verfahren.test_kandidatur import _kandidatur
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401
from verfahren.test_vollzug import admin_anlegen, angenommenen_antrag

pytestmark = pytest.mark.django_db


class KetteFaelltAus(RuntimeError):
    pass


@pytest.fixture
def kette_faellt_aus(monkeypatch):
    '''Schaltet auf Zuruf das Anhängen an die Kette ab — wie ein Fehler der Datenbank an dieser Stelle.'''

    def ausschalten():
        def scheitern(*args, **kwargs):
            raise KetteFaelltAus

        monkeypatch.setattr(AuditEintrag, 'anhaengen', scheitern)

    return ausschalten


def test_vollzug_ohne_audit_eintrag_laesst_keinen_registereintrag_zurueck(ordnung, kette_faellt_aus):  # noqa: F811
    antrag, _leute = angenommenen_antrag(ordnung)
    chefin = admin_anlegen()
    kette_faellt_aus()
    with pytest.raises(KetteFaelltAus):
        vollzug_fortschreiben(antrag, chefin, 'in_umsetzung', 'Los geht es.')
    assert not Vollzugseintrag.objects.filter(antrag=antrag).exists()


def test_bewerbung_ohne_audit_eintrag_wird_nicht_gespeichert(ordnung, kette_faellt_aus):  # noqa: F811
    autor, anna = mitglied_anlegen('autor'), mitglied_anlegen('anna')
    antrag = _kandidatur(ordnung, autor)
    kette_faellt_aus()
    with pytest.raises(KetteFaelltAus):
        bewerbung_einreichen(antrag, anna, 'Ich stehe für offene Sitzungen.')
    assert not Bewerbung.objects.filter(antrag=antrag).exists()


def test_erneuerte_bewerbung_ohne_audit_eintrag_bleibt_wie_sie_war(ordnung, kette_faellt_aus):  # noqa: F811
    autor, anna = mitglied_anlegen('autor'), mitglied_anlegen('anna')
    antrag = _kandidatur(ordnung, autor)
    bewerbung = bewerbung_einreichen(antrag, anna, 'Erste Vorstellung.')
    Bewerbung.objects.filter(pk=bewerbung.pk).update(zurueckgezogen=True)
    kette_faellt_aus()
    with pytest.raises(KetteFaelltAus):
        bewerbung_einreichen(antrag, anna, 'Zweite Vorstellung.')
    bewerbung.refresh_from_db()
    assert bewerbung.vorstellung == 'Erste Vorstellung.' and bewerbung.zurueckgezogen is True


def test_zuordnung_ohne_audit_eintrag_aendert_die_kategorien_nicht(ordnung, kette_faellt_aus):  # noqa: F811
    call_command('kategorien_laden')
    antrag = antrag_einbringen(
        mitglied_anlegen(),
        'Aussetzung der Norm für Rohrmaße',
        'Die Norm über zulässige Rohrmaße wird ausgesetzt; Installateure dürfen bewährte Maße verwenden.',
        '',
        ordnung,
    )
    antrag.kategorien.clear()
    kette_faellt_aus()
    with pytest.raises(KetteFaelltAus):
        kategorien_zuordnen(antrag)
    assert not Antrag.objects.get(pk=antrag.pk).kategorien.exists()


def test_verfristete_pruefung_ohne_audit_eintrag_laesst_den_entwurf_wie_er_war(client, ordnung, monkeypatch):  # noqa: F811
    '''Schlusspflege: Antrag._schritt schreibt die Schleife des Entwurfs in eigener Klammer fort. Scheitert
    der Eintrag „pruefung_frist_verstrichen“, bleibt weder der Vermerk noch der neue Status zurück.'''
    from datetime import timedelta

    from gremien.models import Entwurf, EntwurfsStatus, Pruefung
    from gremien.test_werkstatt import einreichen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    tage = antrag.policy().pruefung_tage
    Entwurf.objects.filter(pk=entwurf.pk).update(eingereicht_am=entwurf.eingereicht_am - timedelta(days=tage, hours=1))
    original = AuditEintrag.anhaengen

    def anhaengen(ereignis, *args, **kwargs):
        if ereignis.get('typ') == 'pruefung_frist_verstrichen':
            raise KetteFaelltAus
        return original(ereignis, *args, **kwargs)

    monkeypatch.setattr(AuditEintrag, 'anhaengen', anhaengen)
    antrag.refresh_from_db()
    with pytest.raises(KetteFaelltAus):
        antrag.fortschreiben()
    assert Entwurf.objects.get(pk=entwurf.pk).status == EntwurfsStatus.PRUEFUNG
    assert not Pruefung.objects.filter(entwurf=entwurf).exists()
    monkeypatch.setattr(AuditEintrag, 'anhaengen', original)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert Entwurf.objects.get(pk=entwurf.pk).status == EntwurfsStatus.UNTERSTUETZER
    assert Pruefung.objects.filter(entwurf=entwurf, ergebnis=Pruefung.Ergebnis.UNGEPRUEFT).count() == 1


def test_die_schleife_des_entwurfs_steht_nicht_mehr_als_gemeldet_im_bestand():
    '''Entwurf.fortschreiben und zurueck_an_gruppe_1 gelten als gefasst; nichts ist mehr „gemeldet“, und
    keine Zeile der Listen des Werkzeugs ist veraltet.'''
    from tools import audit_klammer

    gefunden = audit_klammer.stellen()
    einstufung = {s.schluessel: s.einstufung for s in gefunden}
    for funktion in ('Entwurf.fortschreiben', 'Entwurf.zurueck_an_gruppe_1'):
        assert einstufung[f'gremien/models.py:{funktion}'] == 'aufrufer', funktion
    assert [s.schluessel for s in gefunden if s.einstufung == 'gemeldet'] == []
    assert audit_klammer.veraltete_eintraege(gefunden) == []


def test_die_drei_stellen_stehen_nicht_mehr_als_ungefasst_im_bestand():
    '''Das Werkzeug zu GP-129 stuft die drei Aufrufe als gefasst ein (nicht mehr „gemeldet“).'''
    from tools import audit_klammer

    einstufung = {s.schluessel: s.einstufung for s in audit_klammer.stellen()}
    for funktion in ('vollzug_fortschreiben', 'bewerbung_einreichen', 'kategorien_zuordnen'):
        assert einstufung[f'verfahren/models.py:{funktion}'] == 'atomic', funktion
