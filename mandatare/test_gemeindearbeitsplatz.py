"""Der Arbeitsplatz zeigt die eigenen belegten Stände am zugeordneten Ort."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Gemeindehaushaltsquelle, Gemeindeprojektstand, Mandat
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def _ziel(mandat):
    return reverse("mandatare:gemeinde_arbeitsplatz", args=[mandat.pk])


def test_arbeitsplatz_buendelt_eigene_eintraege_mit_direkten_links(client, gemeindemandat):  # noqa: F811
    gemeinde = gemeindemandat.gemeinde
    anderer = Mandat.objects.create(
        mitglied=mitglied_anlegen("anderes-ratsmitglied"), bezeichnung="Anderes Gemeindemandat", gemeinde=gemeinde,
    )
    jetzt = timezone.now()
    erster_termin = jetzt + timedelta(days=1)
    gemeindemandat.sprechstunden.create(
        gemeinde=gemeinde, beginn=erster_termin, ende=erster_termin + timedelta(hours=1),
        treffpunkt="Abgesagte Sprechstunde", abgesagt_am=jetzt,
    )
    fremder_termin = erster_termin + timedelta(hours=2)
    anderer.sprechstunden.create(
        gemeinde=gemeinde, beginn=fremder_termin, ende=fremder_termin + timedelta(hours=1),
        treffpunkt="Termin des anderen Mandats",
    )
    gemeindemandat.sprechstunden.create(
        gemeinde=gemeinde, beginn=erster_termin + timedelta(days=1), ende=erster_termin + timedelta(days=1, hours=1),
        treffpunkt="Nächster eigener Raum",
    )
    initiative = gemeindemandat.ratsinitiativen.create(
        gemeinde=gemeinde, art="anfrage", titel="Eigene Ratsinitiative", text="Öffentliche Anfrage",
    )
    anderer.ratsinitiativen.create(
        gemeinde=gemeinde, art="anfrage", titel="Andere Ratsinitiative", text="Öffentliche Anfrage",
    )
    projekt = gemeindemandat.gemeindeprojekte.create(gemeinde=gemeinde)
    projekt.staende.create(
        lage=Gemeindeprojektstand.Lage.UMSETZUNG, titel="Eigenes Projekt",
        stand_am=timezone.localdate(), quelle="https://gemeinde.example.org/projekt.pdf",
    )
    neueres = gemeindemandat.gemeindeprojekte.create(gemeinde=gemeinde)
    neueres.staende.create(lage=Gemeindeprojektstand.Lage.ZURUECKGEZOGEN, stand_am=timezone.localdate())
    quelle = Gemeindehaushaltsquelle.objects.create(
        mandat=gemeindemandat, gemeinde=gemeinde, jahr=2026, art="voranschlag",
        url="https://gemeinde.example.org/haushalt.pdf",
    )
    Gemeindehaushaltsquelle.objects.create(mandat=gemeindemandat, gemeinde=gemeinde, jahr=2027, art="voranschlag")
    client.force_login(gemeindemandat.mitglied)
    assert _ziel(gemeindemandat) in client.get(reverse("mandatare:mein_mandat", args=[gemeindemandat.pk])).content.decode()
    audit_vorher = AuditEintrag.objects.count()
    antwort = client.get(_ziel(gemeindemandat))
    assert antwort.status_code == 200 and "private" in antwort.headers["Cache-Control"]
    html = antwort.content.decode()
    assert "Nächster eigener Raum" in html and "Abgesagte Sprechstunde" not in html
    assert "Termin des anderen Mandats" not in html and "Andere Ratsinitiative" not in html
    assert reverse("gemeinde:ratsinitiative", args=[gemeinde.kennziffer, initiative.pk]) in html
    assert reverse("gemeinde:projekt", args=[gemeinde.kennziffer, projekt.pk]) in html
    assert quelle.url in html and "Voranschlag" in html and antwort.context["haushaltsquelle"] == quelle
    assert client.post(_ziel(gemeindemandat)).status_code == 405
    assert AuditEintrag.objects.count() == audit_vorher


def test_nur_eigenes_aktives_zugeordnetes_mandat(client, gemeindemandat):  # noqa: F811
    ziel = _ziel(gemeindemandat)
    assert client.get(ziel).status_code == 302
    client.force_login(mitglied_anlegen("fremdes-konto"))
    assert client.get(ziel).status_code == 404
    client.force_login(gemeindemandat.mitglied)
    gemeindemandat.angetreten = timezone.localdate() + timedelta(days=7)
    gemeindemandat.save(update_fields=["angetreten"])
    assert client.get(ziel).status_code == 404
    gemeindemandat.angetreten = timezone.localdate() - timedelta(days=1)
    gemeindemandat.beendet = timezone.localdate()
    gemeindemandat.save(update_fields=["angetreten", "beendet"])
    assert client.get(ziel).status_code == 404
    gemeindemandat.beendet, gemeindemandat.gemeinde = None, None
    gemeindemandat.save(update_fields=["beendet", "gemeinde"])
    assert client.get(ziel).status_code == 404


def test_beim_lesen_ohne_mitwirkungsrecht_fehlen_die_schreibwege(client, gemeindemandat):  # noqa: F811
    mitglied = gemeindemandat.mitglied
    mitglied.identitaetsstufe = "ungeprueft"
    mitglied.save(update_fields=["identitaetsstufe"])
    client.force_login(mitglied)
    antwort = client.get(_ziel(gemeindemandat))
    assert antwort.status_code == 200 and not antwort.context["darf_schreiben"]
    html = antwort.content.decode()
    assert reverse("gemeinde:haushalt", args=[gemeindemandat.gemeinde.kennziffer]) in html
    for aktion in ("ratsinitiative_anlegen", "haushaltsquelle_verwalten", "sprechstunden", "projekt_verwalten"):
        assert reverse(f"mandatare:{aktion}", args=[gemeindemandat.pk]) not in html
