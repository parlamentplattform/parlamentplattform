"""Nur gespeicherte Angaben, keine Preise erfinden und keine fremden Texte veröffentlichen."""

import pytest
from django.urls import reverse

from ki.models import KILauf, Zweck
from ki.nachlese import antrag_export
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.verbrauch import fuer_antrag
from verfahren.models import Antrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def lauf(antrag, **felder):
    return KILauf.objects.create(antrag=antrag, zweck=Zweck.RECHTSBEZUG, angefordert_von=antrag.eingebracht_von,
                                eingabe="Interner Text bleibt intern", anbieter="attrappe", modell="Testmodell", **felder)


def test_andere_antraege_und_zuordnungslose_vergleiche_zaehlen_nicht(a, ordnung, django_assert_num_queries):  # noqa: F811
    lauf(a, tokens_ein=10, tokens_aus=5)
    lauf(a, erfolgreich=False)
    b = antrag_einbringen(a.eingebracht_von, **ANTRAG, ordnung=ordnung)
    lauf(b, tokens_ein=999)
    KILauf.objects.create(zweck=Zweck.AEHNLICHKEIT, angefordert_von=a.eingebracht_von,
                          eingabe="Vergleich vor Einbringen", anbieter="attrappe", modell="Testmodell", tokens_ein=777)
    with django_assert_num_queries(1):
        d = fuer_antrag(a)
    assert d["summe"]["laeufe"] == 2 and d["summe"]["fehlversuche"] == 1
    assert d["summe"]["tokens_ein"] == 10 and d["summe"]["tokens_aus"] == 5
    assert d["kosten"]["betrag"] is None


def test_unbekannte_zwecke_bleiben_als_sonstige_vollstaendig_mitgezaehlt(a):  # noqa: F811
    for zweck in ["x", "y", Zweck.EINSCHAETZUNG, Zweck.AEHNLICHKEIT]:
        KILauf.objects.create(zweck=zweck, antrag=a, angefordert_von=a.eingebracht_von, eingabe="Privater Text",
                              anbieter="attrappe", modell="Testmodell", tokens_ein=10)
    d = fuer_antrag(a)
    sonstige, = [z for z in d["zeilen"] if z["zweck"] == "sonstige"]
    assert sonstige["laeufe"] == 2 and sonstige["tokens_ein"] == 20
    assert len(d["zeilen"]) == 3 and d["summe"]["tokens_ein"] == 40
    assert "Privater Text" not in str(d)


def test_oeffentlicher_export_ergaenzt_nur_laufmetadaten(a, client):  # noqa: F811
    oeffentlich = lauf(a, tokens_ein=12, tokens_aus=4, dauer_ms=55)
    KILauf.objects.create(zweck=Zweck.EINSCHAETZUNG, antrag=a, angefordert_von=a.eingebracht_von,
                          eingabe="GEHEIMER_GREMEMENTEXT", antwort="GEHEIME_ANTWORT", anbieter="attrappe", modell="m", tokens_ein=99)
    export = antrag_export(a)
    assert export["verbrauch"]["summe"]["tokens_ein"] == 111
    assert export["laeufe"][0]["tokens_ein"] == oeffentlich.tokens_ein
    assert export["laeufe"][0]["dauer_ms"] == 55 and len(export["laeufe"]) == 1
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Modellverbrauch und Kostenstand" in html and "Kostenbetrag nicht erfasst" in html
    assert "GEHEIMER_GREMEMENTEXT" not in str(export) + html and "GEHEIME_ANTWORT" not in str(export) + html
    from mitglieder.profil import daten_export
    eigene = daten_export(a.eingebracht_von)
    assert sorted(k["tokens_ein"] for k in eigene["ki_laeufe"]) == [12, 99]


def test_leerstand_ist_keine_behauptung_von_kostenfreiheit(a, client):  # noqa: F811
    d = fuer_antrag(a)
    assert not d["zeilen"] and d["summe"]["laeufe"] == 0 and d["kosten"]["betrag"] is None
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Noch keine zugeordneten Läufe im Archiv" in html and "kein Abrechnungsnachweis" in html


def test_ungespeicherter_antrag_wird_nicht_zur_uebersicht_aller_zuordnungslosen_laeufe():
    with pytest.raises(ValueError):
        fuer_antrag(Antrag())
