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
        frist=timezone.now() + timedelta(days=5),
    )
    Aufgabe.objects.create(
        mandat=mandat, titel="Altes Protokoll", frist=timezone.now() - timedelta(days=2)
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


def test_ohne_laufende_kandidatur_behauptet_die_seite_keine_wahl(client):
    """Ohne Mandat und ohne laufende Kandidatur standen „die Wahl läuft bereits" und „derzeit läuft
    keine Kandidatur" im selben Kasten — die Seite sagt jetzt nur, was stimmt."""
    inhalt = client.get(reverse("mandatare:liste")).content.decode()
    assert "kein öffentliches Mandat" in inhalt
    assert "läuft bereits" not in inhalt
    assert "derzeit läuft keine Kandidatur" in inhalt and "kann eine einbringen" in inhalt


# --- S10: Verwaltung verknüpft die Kandidatur, prüft die Unvereinbarkeit, nimmt Uhrzeiten ---


def test_verwaltung_verknuepft_die_kandidatur_und_uebernimmt_ebene_und_gebiet(client, ordnung):  # noqa: F811
    from verfahren.models import AuditEintrag

    anna = mitglied_anlegen("anna")
    kandidatur = antrag_einbringen(
        anna, "Listenreihung Landtag", "Reihung.", "", ordnung, art=Antragsart.MANDAT, ebene="land", gebiet="Oberösterreich"
    )
    client.force_login(admin_anlegen())
    client.post(
        reverse("mandatare:verwaltung_aktion"),
        {
            "aktion": "anlegen",
            "mitglied": anna.pk,
            "bezeichnung": "Landtagsabgeordnete",
            "kandidatur": kandidatur.pk,
            "ebene": "",
            "gebiet": "",
            "angetreten": timezone.localdate().isoformat(),
            "vorstellung": "",
        },
    )
    mandat = Mandat.objects.get()
    assert mandat.kandidatur == kandidatur
    assert mandat.ebene == "land" and mandat.gebiet == "Oberösterreich"  # exakt wie der Antrag (Regionsband)
    (e,) = [x.ereignis for x in AuditEintrag.objects.filter(ereignis__typ="mandat_angelegt")]
    assert e["kandidatur"] == kandidatur.pk and "mitglied" not in e
    verwaltung = client.get(reverse("mandatare:verwaltung")).content.decode()
    assert f'href="/antrag/{kandidatur.pk}/"' in verwaltung
    detail = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert f'href="/antrag/{kandidatur.pk}/"' in detail


def test_ohne_ebene_und_ohne_kandidatur_entsteht_kein_mandat(client):
    anna = mitglied_anlegen("anna")
    client.force_login(admin_anlegen())
    html = client.post(
        reverse("mandatare:verwaltung_aktion"),
        {"aktion": "anlegen", "mitglied": anna.pk, "bezeichnung": "Gemeinderat", "ebene": "", "gebiet": "",
         "angetreten": timezone.localdate().isoformat(), "vorstellung": ""},
        follow=True,
    ).content.decode()
    assert Mandat.objects.count() == 0 and "Pflichtfelder" in html


def test_mitglied_des_integritaetsrats_bekommt_kein_mandat(client):
    """§ 6 Abs 3 lit a: Die Verwaltung weist die Unvereinbarkeit beim Anlegen ab."""
    from gremien.models import Gremium, Rolle, standard_ende

    anna = mitglied_anlegen("anna")
    Rolle.objects.create(mitglied=anna, gremium=Gremium.INTEGRITAETSRAT, endet_am=standard_ende(), bestaetigt=True)
    client.force_login(admin_anlegen())
    html = client.post(
        reverse("mandatare:verwaltung_aktion"),
        {"aktion": "anlegen", "mitglied": anna.pk, "bezeichnung": "Gemeinderat", "ebene": "gemeinde",
         "gebiet": "Wels", "angetreten": timezone.localdate().isoformat(), "vorstellung": ""},
        follow=True,
    ).content.decode()
    assert Mandat.objects.count() == 0
    assert "Integritätsrat" in html and "§ 6 Abs 3 lit a" in html


def test_verwaltung_nimmt_frist_mit_uhrzeit_und_sitzungstag(client):
    from verfahren.models import AuditEintrag

    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    client.force_login(admin_anlegen())
    tag = timezone.localdate() + timedelta(days=10)
    client.post(
        reverse("mandatare:verwaltung_aktion"),
        {"aktion": "aufgabe", "mandat": mandat.pk, "titel": "Sitzung", "beschreibung": "", "frist": tag.isoformat(),
         "frist_zeit": "14:30", "sitzungstag": "on", "antrag": ""},
    )
    aufgabe = mandat.aufgaben.get()
    lokal = timezone.localtime(aufgabe.frist)
    assert lokal.date() == tag and (lokal.hour, lokal.minute) == (14, 30) and aufgabe.sitzungstag is True
    # unbrauchbares Datum: Meldung statt Absturz
    html = client.post(
        reverse("mandatare:verwaltung_aktion"),
        {"aktion": "aufgabe", "mandat": mandat.pk, "titel": "Kaputt", "frist": "gestern", "antrag": ""},
        follow=True,
    ).content.decode()
    assert mandat.aufgaben.count() == 1 and "gültiges Datum" in html
    # Foto und Statuswechsel der Verwaltung hinterlassen jetzt eine Spur
    client.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "aufgabe_status", "aufgabe": aufgabe.pk, "status": "laufend"})
    assert AuditEintrag.objects.filter(ereignis__typ="mandats_aufgabe_status").exists()


def test_meldungen_und_beschriftungen_der_mandatare_views_sind_uebersetzbar():
    """Befund #91, Wächter wie in mitglieder/test_verwaltung.py: nackte Strings in messages.*()
    oder label= fallen im Quelltext auf."""
    import re
    from pathlib import Path

    quelle = Path(__file__).with_name("views.py").read_text(encoding="utf-8")
    nackt = re.findall(r'messages\.\w+\(\s*request,\s*f?"', quelle)
    assert nackt == [], f"Meldungen ohne gettext: {nackt}"
    assert re.findall(r'label="', quelle) == []
    assert re.findall(r'help_text="', quelle) == []
    assert re.findall(r'ValidationError\(\s*f?"', quelle) == []
