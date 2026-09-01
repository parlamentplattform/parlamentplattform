"""M1 — die Mandatare-Seite (§ 7 Abs 9 E-2.5, F-71)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Mandat, foto_typ_erkennen
from verfahren.models import Antragsart, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

PNG_MINI = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"IHDR" + b"\x00" * 60
)  # nur Kopfbytes — für die Typerkennung genügt das


def admin_anlegen(name="admina"):
    m = mitglied_anlegen(name)
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    return m


def mandat_anlegen(mitglied, **extra):
    return Mandat.objects.create(
        mitglied=mitglied,
        bezeichnung=extra.pop("bezeichnung", "Gemeinderat"),
        ebene=extra.pop("ebene", "gemeinde"),
        gebiet=extra.pop("gebiet", "St. Marienkirchen an der Polsenz"),
        **extra,
    )


def test_leere_seite_zeigt_ehrlich_den_stand_und_die_kandidaturen(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag_einbringen(anna, "Listenreihung Gemeinderat", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    inhalt = client.get(reverse("mandatare:liste")).content.decode()
    assert "kein öffentliches Mandat" in inhalt
    assert "Listenreihung Gemeinderat" in inhalt  # laufende Kandidatur wird gezeigt


def test_mandatar_erscheint_mit_aufgaben_und_fristen(client):
    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    Aufgabe.objects.create(
        mandat=mandat,
        titel="Budgetausschuss: Stellungnahme",
        frist=timezone.localdate() + timedelta(days=5),
    )
    Aufgabe.objects.create(
        mandat=mandat, titel="Altes Protokoll", frist=timezone.localdate() - timedelta(days=2)
    )
    inhalt = client.get(reverse("mandatare:liste")).content.decode()
    assert "Budgetausschuss: Stellungnahme" in inhalt and mandat.mitglied.anzeigename in inhalt

    inhalt = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "Budgetausschuss: Stellungnahme" in inhalt
    assert 'class="aufgabe-frist spaet"' in inhalt  # überfällige Frist wird markiert


def test_aufgabe_verlinkt_die_betreute_abstimmung(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    mandat = mandat_anlegen(anna)
    Aufgabe.objects.create(mandat=mandat, titel="Protokolle", antrag=antrag)
    inhalt = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert f'/antrag/{antrag.pk}/' in inhalt


def test_foto_typerkennung_und_auslieferung(client):
    assert foto_typ_erkennen(PNG_MINI) == "image/png"
    assert foto_typ_erkennen(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert foto_typ_erkennen(b"GIF89a") is None  # nicht erlaubt

    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    assert client.get(reverse("mandatare:foto", args=[mandat.pk])).status_code == 404
    mandat.foto = PNG_MINI
    mandat.foto_typ = "image/png"
    mandat.save(update_fields=["foto", "foto_typ"])
    antwort = client.get(reverse("mandatare:foto", args=[mandat.pk]))
    assert antwort.status_code == 200 and antwort["Content-Type"] == "image/png"
    assert antwort.content == PNG_MINI


def test_verwaltung_nur_fuer_admins(client):
    url = reverse("mandatare:verwaltung")
    assert client.get(url).status_code in (302, 403)
    client.force_login(mitglied_anlegen("bernd"))
    assert client.get(url).status_code == 403
    client.force_login(admin_anlegen())
    assert client.get(url).status_code == 200


def test_verwaltung_legt_mandat_und_aufgabe_an(client):
    anna = mitglied_anlegen("anna")
    client.force_login(admin_anlegen())
    client.post(
        reverse("mandatare:verwaltung_aktion"),
        {
            "aktion": "anlegen",
            "mitglied": anna.pk,
            "bezeichnung": "Gemeinderat",
            "ebene": "gemeinde",
            "gebiet": "St. Marienkirchen an der Polsenz",
            "angetreten": timezone.localdate().isoformat(),
            "vorstellung": "",
        },
    )
    mandat = Mandat.objects.get()
    assert mandat.mitglied == anna and mandat.aktiv

    client.post(
        reverse("mandatare:verwaltung_aktion"),
        {
            "aktion": "aufgabe",
            "mandat": mandat.pk,
            "titel": "Erste Sitzung vorbereiten",
            "beschreibung": "Tagesordnung sichten.",
            "frist": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "antrag": "",
        },
    )
    aufgabe = mandat.aufgaben.get()
    assert aufgabe.titel == "Erste Sitzung vorbereiten" and aufgabe.frist is not None

    client.post(
        reverse("mandatare:verwaltung_aktion"),
        {"aktion": "aufgabe_status", "aufgabe": aufgabe.pk, "status": "erledigt"},
    )
    aufgabe.refresh_from_db()
    assert aufgabe.status == "erledigt"

    client.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "beenden", "mandat": mandat.pk})
    mandat.refresh_from_db()
    assert not mandat.aktiv


def test_beendetes_mandat_verschwindet_aus_der_liste_bleibt_aber_abrufbar(client):
    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna, beendet=timezone.localdate())
    inhalt = client.get(reverse("mandatare:liste")).content.decode()
    assert "kein öffentliches Mandat" in inhalt  # nicht mehr in der aktiven Liste
    antwort = client.get(reverse("mandatare:detail", args=[mandat.pk]))
    assert antwort.status_code == 200 and "beendet am" in antwort.content.decode()


def test_navigation_fuehrt_zu_den_mandataren(client):
    inhalt = client.get("/").content.decode()
    assert 'href="/mandatare/"' in inhalt
