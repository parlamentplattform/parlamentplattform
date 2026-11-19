"""Sitzungsunterlagen bleiben am dokumentierten Ort und werden nur mit Bestätigung öffentlich."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Gemeindesitzungsquelle, Sitzung
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401
from mitglieder.models import Gemeinde
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

ERSTE_URL = "https://gemeinde.example.org/sitzungen/einladung.pdf"
NEUE_URL = "https://gemeinde.example.org/sitzungen/berichtigte-einladung.pdf"
QUELLE = {"art": "einladung", "url": ERSTE_URL, "bestaetigt": "on", "aktion": "veroeffentlichen"}


@pytest.fixture
def aufgabe(gemeindemandat):  # noqa: F811
    return Aufgabe.objects.create(
        mandat=gemeindemandat, titel="Angekündigte öffentliche Sitzung",
        sitzungstag=True, frist=timezone.now() + timedelta(days=2),
    )


def _verwalten(aufgabe):
    return reverse("mandatare:sitzungsquelle_verwalten", args=[aufgabe.mandat_id, aufgabe.pk])


def _liste(gemeinde):
    return reverse("gemeinde:sitzungsquellen", args=[gemeinde.kennziffer])


def test_berichtigung_und_ruecknahme_mit_geschuetzter_historie(client, aufgabe):
    mandat = aufgabe.mandat
    client.force_login(mandat.mitglied)
    verwalten, liste = _verwalten(aufgabe), _liste(mandat.gemeinde)
    assert verwalten in client.get(reverse("mandatare:mein_mandat", args=[mandat.pk])).content.decode()
    assert liste in client.get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()
    assert client.post(verwalten, QUELLE).url == liste
    gast = Client()
    assert ERSTE_URL in gast.get(liste).content.decode()
    assert client.post(verwalten, {**QUELLE, "url": NEUE_URL}).status_code == 302
    assert client.post(verwalten, {**QUELLE, "url": NEUE_URL}).status_code == 302
    public = gast.get(liste).content.decode()
    assert ERSTE_URL not in public and NEUE_URL in public
    assert client.post(verwalten, {"art": "einladung", "aktion": "zurueckziehen"}).status_code == 302
    public = gast.get(liste).content.decode()
    assert NEUE_URL not in public and "Link zurückgezogen" in public
    assert list(Gemeindesitzungsquelle.objects.order_by("pk").values_list("url", flat=True)) == [
        ERSTE_URL, NEUE_URL, "",
    ]
    audit = AuditEintrag.objects.filter(ereignis__typ="gemeindesitzungsquelle")
    assert audit.count() == 3 and audit.filter(ereignis__zurueckgezogen=True).count() == 1
    assert all("url" not in e.ereignis for e in audit)


@pytest.mark.parametrize("daten", [
    {"bestaetigt": ""},
    {"url": ""},
    {"url": "http://gemeinde.example.org/"},
    {"url": "ftp://gemeinde.example.org/"},
    {"url": "javascript:alert(1)"},
    {"url": "https://name:passwort@gemeinde.example.org/"},
    {"url": "https://gemeinde.example.org/weg\\falsch"},
    {"url": "https://[falsch"},
    {"art": "vertraulich"},
    {"art": "niederschrift"},
    {"aktion": "zurueckziehen"},
    {"aktion": ""},
])
def test_nur_bestaetigte_oeffentliche_links_zu_zulaessigen_unterlagen(client, aufgabe, daten):
    client.force_login(aufgabe.mandat.mitglied)
    r = client.post(_verwalten(aufgabe), {**QUELLE, **daten})
    assert r.status_code == 200 and r.context["form"].errors
    assert not Gemeindesitzungsquelle.objects.exists()


def test_angekuendigter_sitzungstag_mit_einladung_und_spaeterer_niederschrift(client, aufgabe):
    aufgabe.frist -= timedelta(days=3)
    aufgabe.save(update_fields=["frist"])
    client.force_login(aufgabe.mandat.mitglied)
    for art, link in [("niederschrift", NEUE_URL), ("einladung", ERSTE_URL)]:
        assert client.post(_verwalten(aufgabe), {**QUELLE, "art": art, "url": link}).status_code == 302
    oeffentlich = Client().get(_liste(aufgabe.mandat.gemeinde))
    assert [q.art for q in oeffentlich.context["seite"]] == ["einladung", "niederschrift"]
    assert oeffentlich.content.decode().index(ERSTE_URL) < oeffentlich.content.decode().index(NEUE_URL)


def test_live_nachlese_zeigt_nur_die_neuesten_unterlagen_dieser_sitzung(client, aufgabe):
    mandat = aufgabe.mandat
    jetzt = timezone.now()
    aufgabe.frist = jetzt - timedelta(days=1)
    aufgabe.save(update_fields=["frist"])
    sitzung = Sitzung.objects.create(aufgabe=aufgabe, mandat=mandat, beginn=aufgabe.frist, ende=jetzt)
    andere = Aufgabe.objects.create(mandat=mandat, sitzungstag=True, frist=jetzt, titel="Andere Sitzung")
    fremder_link = "https://gemeinde.example.org/andere.pdf"
    client.force_login(mandat.mitglied)
    for ziel, daten in [
        (aufgabe, QUELLE), (aufgabe, {**QUELLE, "url": NEUE_URL}),
        (andere, {**QUELLE, "url": fremder_link}),
    ]:
        assert client.post(_verwalten(ziel), daten).status_code == 302
    pfad = reverse("mandatare:live", args=[mandat.pk])
    gast = Client()
    html = gast.get(pfad, {"sitzung": sitzung.pk}).content.decode()
    assert 'id="live-unterlagen"' in html and NEUE_URL in html
    assert ERSTE_URL not in html and fremder_link not in html
    assert mandat.gemeinde.anzeige in html
    assert client.post(_verwalten(aufgabe), {"art": "einladung", "aktion": "zurueckziehen"}).status_code == 302
    vorher = AuditEintrag.objects.count()
    html = gast.get(pfad, {"sitzung": sitzung.pk}).content.decode()
    assert "Link zurückgezogen" in html and NEUE_URL not in html
    assert AuditEintrag.objects.count() == vorher


def test_rechte_csrf_alter_ort_und_mandatsende(client, aufgabe):
    mandat = aufgabe.mandat
    verwalten, alt = _verwalten(aufgabe), _liste(mandat.gemeinde)
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(verwalten, QUELLE).status_code == 404
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(mandat.mitglied)
    assert csrf.post(verwalten, QUELLE).status_code == 403
    client.force_login(mandat.mitglied)
    assert client.get(verwalten, QUELLE).status_code == 200
    assert not Gemeindesitzungsquelle.objects.exists()
    assert client.post(verwalten, QUELLE).status_code == 302
    mandat.gemeinde = Gemeinde.objects.create(
        kennziffer="41419", name=mandat.gemeinde.name, bezirk="Schärding", bundesland="oberoesterreich",
    )
    mandat.save(update_fields=["gemeinde"])
    assert client.post(verwalten, {**QUELLE, "url": NEUE_URL}).status_code == 403
    assert ERSTE_URL in Client().get(alt).content.decode()
    assert ERSTE_URL not in Client().get(_liste(mandat.gemeinde)).content.decode()
    mandat.beendet = timezone.localdate()
    mandat.save(update_fields=["beendet"])
    assert client.post(verwalten, QUELLE).status_code == 404
    assert ERSTE_URL in Client().get(alt).content.decode()


def test_nur_aufgaben_mit_sitzungstag_und_geprueftem_mitglied(client, aufgabe):
    mitglied = aufgabe.mandat.mitglied
    client.force_login(mitglied)
    verwalten = _verwalten(aufgabe)
    aufgabe.sitzungstag = False
    aufgabe.save(update_fields=["sitzungstag"])
    assert client.post(verwalten, QUELLE).status_code == 404
    mitglied.identitaetsstufe = "ungeprueft"
    mitglied.save(update_fields=["identitaetsstufe"])
    assert client.post(verwalten, QUELLE).status_code == 403
    assert not Gemeindesitzungsquelle.objects.exists()
