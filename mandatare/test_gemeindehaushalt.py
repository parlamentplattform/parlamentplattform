"""Öffentliche Haushaltsquellen und ihre dauerhafte Ortszuordnung."""

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Gemeindehaushaltsquelle
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401
from mitglieder.models import Gemeinde
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

QUELLE = "https://gemeinde.example.org/haushalt/2026.pdf"
KORREKTUR = "https://gemeinde.example.org/haushalt/2026-neu.pdf"
DATEN = {"aktion": "veroeffentlichen", "art": "voranschlag", "jahr": "2026", "url": QUELLE, "bestaetigt": "on"}


def _verwaltung(mandat):
    return reverse("mandatare:haushaltsquelle_verwalten", args=[mandat.pk])


def _liste(gemeinde):
    return reverse("gemeinde:haushalt", args=[gemeinde.kennziffer])


def test_haushaltsquellen_sind_je_mandat_und_jahr_nachvollziehbar(client, gemeindemandat):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    verwalten, liste = _verwaltung(gemeindemandat), _liste(gemeindemandat.gemeinde)
    assert liste in client.get(reverse("gemeinde:ort", args=[gemeindemandat.gemeinde.kennziffer])).content.decode()
    assert verwalten in client.get(reverse("mandatare:mein_mandat", args=[gemeindemandat.pk])).content.decode()
    assert "noch keine Haushaltsunterlagen" in Client().get(liste).content.decode()
    assert client.post(verwalten, DATEN).url == liste
    assert client.post(verwalten, DATEN).status_code == 302
    assert Gemeindehaushaltsquelle.objects.count() == 1
    assert QUELLE in Client().get(liste).content.decode()
    assert client.post(verwalten, {**DATEN, "url": KORREKTUR}).status_code == 302
    assert QUELLE not in Client().get(liste).content.decode()
    assert KORREKTUR in Client().get(liste).content.decode()
    absage = {"art": "voranschlag", "jahr": "2026", "aktion": "zurueckziehen"}
    assert client.post(verwalten, absage).status_code == 302
    assert client.post(verwalten, absage).status_code == 200
    html = Client().get(liste).content.decode()
    assert KORREKTUR not in html and "Link zurückgezogen" in html
    assert list(Gemeindehaushaltsquelle.objects.order_by("pk").values_list("url", flat=True)) == [
        QUELLE, KORREKTUR, "",
    ]
    audit = AuditEintrag.objects.filter(ereignis__typ="gemeindehaushaltsquelle")
    assert audit.count() == 3 and all("url" not in e.ereignis for e in audit)


@pytest.mark.parametrize("daten", [
    {"art": "leer"}, {"jahr": ""}, {"jahr": "10000"}, {"jahr": "0"}, {"bis_jahr": "2027"},
    {"art": "finanzplan"}, {"art": "finanzplan", "bis_jahr": "2025"}, {"art": "finanzplan", "bis_jahr": "10000"},
    {"url": ""}, {"url": "http://gemeinde.example.org/test"}, {"url": "https://[falsch"},
    {"url": "https://zugang:geheim@gemeinde.example.org/"}, {"bestaetigt": ""},
])
def test_nur_oeffentliche_quellen_mit_passendem_zeitraum(client, gemeindemandat, daten):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    antwort = client.post(_verwaltung(gemeindemandat), {**DATEN, **daten})
    assert antwort.status_code == 200 and antwort.context["form"].errors
    assert not Gemeindehaushaltsquelle.objects.exists()


def test_planzeitraum_jahresreihung_und_datenbankschutz(client, gemeindemandat):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    verwalten = _verwaltung(gemeindemandat)
    assert client.post(verwalten, {**DATEN, "jahr": "2025", "art": "rechnungsabschluss"}).status_code == 302
    assert client.post(verwalten, DATEN).status_code == 302
    plan = {**DATEN, "art": "finanzplan", "bis_jahr": "2030"}
    assert client.post(verwalten, plan).status_code == 302
    antwort = Client().get(_liste(gemeindemandat.gemeinde))
    assert [q.art for q in antwort.context["seite"]] == ["finanzplan", "voranschlag", "rechnungsabschluss"]
    assert "2026–2030" in antwort.content.decode()
    assert client.post(verwalten, {**plan, "bis_jahr": "2031"}).status_code == 302
    assert "2026–2031" in Client().get(_liste(gemeindemandat.gemeinde)).content.decode()
    assert client.post(verwalten, {"art": "finanzplan", "jahr": "2026", "aktion": "zurueckziehen"}).status_code == 302
    with pytest.raises(IntegrityError), transaction.atomic():
        Gemeindehaushaltsquelle.objects.create(
            mandat=gemeindemandat, gemeinde=gemeindemandat.gemeinde, art="finanzplan", jahr=2026,
        )


def test_rechte_und_ort_bleiben_gebunden(client, gemeindemandat):  # noqa: F811
    verwalten = _verwaltung(gemeindemandat)
    alter_ort = gemeindemandat.gemeinde
    anderer_ort = Gemeinde.objects.create(
        kennziffer="41419", name=alter_ort.name, bezirk="Schärding", bundesland="oberoesterreich",
    )
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(verwalten, DATEN).status_code == 404
    ohne_csrf = Client(enforce_csrf_checks=True)
    ohne_csrf.force_login(gemeindemandat.mitglied)
    assert ohne_csrf.post(verwalten, DATEN).status_code == 403
    client.force_login(gemeindemandat.mitglied)
    assert client.get(verwalten).status_code == 200
    assert not Gemeindehaushaltsquelle.objects.exists()
    assert client.post(verwalten, DATEN).status_code == 302
    assert QUELLE not in Client().get(_liste(anderer_ort)).content.decode()
    gemeindemandat.gemeinde = anderer_ort
    gemeindemandat.beendet = timezone.localdate()
    gemeindemandat.save(update_fields=["gemeinde", "beendet"])
    assert client.post(verwalten, DATEN).status_code == 404
    assert QUELLE in Client().get(_liste(alter_ort)).content.decode()
