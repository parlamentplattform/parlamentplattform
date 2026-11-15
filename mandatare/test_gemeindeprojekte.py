"""Rechte, Herkunft und sichtbarer Projektverlauf nach Berichtigung und Rücknahme."""

from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Gemeindeprojekt, Gemeindeprojektstand
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401
from mitglieder.models import Gemeinde
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

QUELLE = "https://gemeinde.example.org/projekt/stand.pdf"
KORREKTUR = "https://gemeinde.example.org/projekt/neu.pdf"
TITEL = "Öffentlich dokumentiertes Platzprojekt"


def projekt_daten():
    return {"aktion": "veroeffentlichen", "titel": TITEL, "lage": "vorgestellt",
            "stand_am": timezone.localdate().isoformat(), "quelle": QUELLE, "bestaetigt": "on",
            "vermerk": "Erster öffentlicher Bericht."}


def _verwalten(mandat, projekt=None):
    if projekt is None:
        return reverse("mandatare:projekt_verwalten", args=[mandat.pk])
    return reverse("mandatare:projekt_verwalten", args=[mandat.pk, projekt.pk])


def test_berichtigung_und_ruecknahme_erhalten_alte_projektstaende(
    client, gemeindemandat,  # noqa: F811
):
    client.force_login(gemeindemandat.mitglied)
    neu = _verwalten(gemeindemandat)
    assert neu in client.get(reverse("mandatare:mein_mandat", args=[gemeindemandat.pk])).content.decode()
    daten = projekt_daten()
    detail = client.post(neu, daten).url
    projekt = Gemeindeprojekt.objects.get()
    daten["ausgang"] = projekt.staende.get().pk
    bearbeiten = _verwalten(gemeindemandat, projekt)
    assert client.post(bearbeiten, daten).status_code == 302
    assert projekt.staende.count() == 1
    assert client.post(bearbeiten, {**daten, "lage": "umsetzung", "quelle": KORREKTUR,
                                   "vermerk": "<script>Beispiel</script>"}).status_code == 302
    gast = Client()
    html = gast.get(detail).content.decode()
    assert "In Umsetzung" in html and KORREKTUR in html
    assert "&lt;script&gt;Beispiel&lt;/script&gt;" in html
    assert "<script>Beispiel</script>" not in html and QUELLE not in html
    assert "Frühere Projektstände" in html and "Vorgestellt" in html
    assert bearbeiten not in html
    letzter = projekt.staende.latest("pk").pk
    for _ in range(2):
        assert client.post(bearbeiten, {"aktion": "zurueckziehen", "ausgang": letzter}).status_code == 302
    html = gast.get(detail).content.decode()
    assert "Veröffentlichung zurückgezogen" in html and KORREKTUR not in html and TITEL not in html
    assert list(projekt.staende.order_by("pk").values_list("quelle", flat=True)) == [QUELLE, KORREKTUR, ""]
    audit = AuditEintrag.objects.filter(ereignis__typ="gemeindeprojektstand")
    assert audit.count() == 3
    assert all("quelle" not in eintrag.ereignis and "vermerk" not in eintrag.ereignis for eintrag in audit)


@pytest.mark.parametrize("aenderung", [
    {"lage": "zurueckgezogen"}, {"lage": "keine"}, {"titel": " "}, {"quelle": ""},
    {"quelle": "http://gemeinde.example.org/projekt/"}, {"bestaetigt": ""},
    {"stand_am": ""}, {"stand_am": "kaputt"},
])
def test_aktuelle_projektangabe_braucht_oeffentliche_quelle(client, gemeindemandat, aenderung):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    antwort = client.post(_verwalten(gemeindemandat), {**projekt_daten(), **aenderung})
    assert antwort.status_code == 200 and antwort.context["form"].errors
    assert not Gemeindeprojekt.objects.exists()


def test_zukuenftiges_belegdatum_ist_kein_oeffentlicher_stand(client, gemeindemandat, monkeypatch):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    jetzt = datetime(2026, 11, 15, 8, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: jetzt)
    morgen = (timezone.localdate() + timedelta(days=1)).isoformat()
    antwort = client.post(_verwalten(gemeindemandat), {**projekt_daten(), "stand_am": morgen})
    assert "stand_am" in antwort.context["form"].errors
    assert not Gemeindeprojektstand.objects.exists()


def test_projekt_bleibt_in_der_ersten_gemeinde_und_fremde_koennen_nicht_schreiben(client, gemeindemandat):  # noqa: F811
    ursprung = gemeindemandat.gemeinde
    anderer_ort = Gemeinde.objects.create(
        kennziffer="41419", name=ursprung.name, bezirk="Schärding", bundesland="oberoesterreich",
    )
    neu = _verwalten(gemeindemandat)
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(neu, projekt_daten()).status_code == 404
    ohne_csrf = Client(enforce_csrf_checks=True)
    ohne_csrf.force_login(gemeindemandat.mitglied)
    assert ohne_csrf.post(neu, projekt_daten()).status_code == 403
    client.force_login(gemeindemandat.mitglied)
    assert client.get(neu).status_code == 200
    assert not Gemeindeprojekt.objects.exists()
    detail = client.post(neu, projekt_daten()).url
    projekt = Gemeindeprojekt.objects.get()
    gemeindemandat.gemeinde = anderer_ort
    gemeindemandat.save(update_fields=["gemeinde"])
    assert client.post(_verwalten(gemeindemandat, projekt), {"aktion": "zurueckziehen"}).status_code == 404
    gast = Client()
    liste = reverse("gemeinde:projekte", args=[ursprung.kennziffer])
    assert detail in gast.get(liste).content.decode()
    assert QUELLE in gast.get(detail).content.decode()
    assert gast.get(reverse("gemeinde:projekt", args=[anderer_ort.kennziffer, projekt.pk])).status_code == 404


def test_fortschreibung_veraendert_reihenfolge_nach_erstveroeffentlichung_nicht(client, gemeindemandat):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    neu = _verwalten(gemeindemandat)
    alt = client.post(neu, projekt_daten()).url
    aelter = Gemeindeprojekt.objects.get()
    assert client.post(neu, {**projekt_daten(), "titel": "Zweites Projekt"}).status_code == 302
    aeltere_daten = {**projekt_daten(), "lage": "beschlossen", "ausgang": aelter.staende.get().pk}
    assert client.post(_verwalten(gemeindemandat, aelter), aeltere_daten).url == alt
    liste = Client().get(reverse("gemeinde:projekte", args=[gemeindemandat.gemeinde.kennziffer]))
    assert [s.titel for s in liste.context["seite"]] == ["Zweites Projekt", TITEL]


def test_alter_formularstand_aendert_oder_entfernt_keine_neuere_fassung(client, gemeindemandat):  # noqa: F811
    client.force_login(gemeindemandat.mitglied)
    daten = projekt_daten()
    client.post(_verwalten(gemeindemandat), daten)
    projekt = Gemeindeprojekt.objects.get()
    ausgang = projekt.staende.get().pk
    bearbeiten = _verwalten(gemeindemandat, projekt)
    assert client.post(bearbeiten, {**daten, "ausgang": ausgang, "quelle": KORREKTUR}).status_code == 302
    alte_ruecknahme = {"aktion": "zurueckziehen", "ausgang": ausgang}
    alte_korrektur = {**daten, "ausgang": ausgang, "titel": "Veralteter Entwurf"}
    for eingabe in (alte_ruecknahme, alte_korrektur):
        antwort = client.post(bearbeiten, eingabe)
        assert antwort.status_code == 200 and antwort.context["zwischenzeitlich_geaendert"]
        assert projekt.staende.latest("pk").quelle == KORREKTUR
    assert projekt.staende.count() == 2
