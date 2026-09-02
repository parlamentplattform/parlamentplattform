"""P3/P4 — Kachel-Raster: Wichtige Abstimmungen und Meine Region (F-42/F-43).
Kernregel: Während einer laufenden Abstimmung zeigt die Kachel die Beteiligung
und die Restzeit — nie die Tendenz (F-15, kein Bandwagon)."""

import pytest
from django.urls import reverse

from mitglieder.models import Gemeinde
from verfahren.models import Antrag, Antragsart, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def test_wichtige_kachel_zeigt_beteiligung_und_resttage_aber_keine_tendenz(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(
        antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:]
    )
    Antrag.objects.filter(pk=antrag.pk).update(
        hervorgehoben=True, hervorhebung_begruendung="Beschluss IR-2026-09."
    )
    from verfahren.models import stimme_abgeben

    stimme_abgeben(antrag, leute[1], "ja")
    stimme_abgeben(antrag, leute[2], "nein")

    inhalt = client.get("/parlament/").content.decode()
    assert "% der Stimmberechtigten haben abgestimmt" in inhalt
    assert "Tendenz verdeckt bis Fristende" in inhalt
    assert "Beschluss IR-2026-09." in inhalt
    assert "noch <strong>" in inhalt  # Resttage
    # Keine Ja/Nein-Zählung irgendwo in den Kacheln:
    assert "Ja 1" not in inhalt and "Nein 1" not in inhalt


def test_unterstuetzungs_kachel_zeigt_fortschritt_zur_schwelle(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung, ebene="gemeinde",
                               gebiet="St. Marienkirchen an der Polsenz")
    antrag.unterstuetzungen.create(mitglied=anna)
    inhalt = client.get("/parlament/").content.decode()
    assert "1 von 2 Unterstützungen" in inhalt  # Test-Schwelle: 2


def test_meine_region_filtert_nach_wohnsitz_und_zeigt_drei_zeilen(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    fremd = mitglied_anlegen("fremd", gemeinde="Wels", bundesland="oberoesterreich")
    antrag_einbringen(anna, "Radweg sanieren", "W.", "", ordnung,
                      ebene="gemeinde", gebiet="St. Marienkirchen an der Polsenz")
    antrag_einbringen(fremd, "Welser Stadtpark", "W.", "", ordnung, ebene="gemeinde", gebiet="Wels")

    client.force_login(anna)
    region = client.get("/parlament/").content.decode().split('id="feld-region"')[1]
    assert "Radweg sanieren" in region
    assert "Welser Stadtpark" not in region  # fremde Gemeinde gefiltert (im Regions-Feld)
    assert "Noch nichts in Ihrem Bezirk." in region  # Band 2 immer da (FB-E3: kurz)
    assert "Noch nichts in Ihrem Land." in region  # Band 3 immer da

    client.logout()
    region = client.get("/parlament/").content.decode().split('id="feld-region"')[1]
    assert "Radweg sanieren" in region and "Welser Stadtpark" in region  # Gäste: alle Orte


def test_direktabstimmung_aus_der_kachel_kehrt_ins_parlament_zurueck(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = antrag_einbringen(leute[0], "Ortskern beleben", "W.", "", ordnung,
                               ebene="gemeinde", gebiet="St. Marienkirchen an der Polsenz")
    in_abstimmung_bringen(antrag, leute[1:])

    client.force_login(leute[2])
    inhalt = client.get("/parlament/").content.decode()
    assert 'name="stimme" value="ja"' in inhalt  # Knöpfe direkt in der Kachel

    antwort = client.post(
        reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja", "weiter": "/parlament/"}
    )
    assert antwort.url == "/parlament/"
    assert antrag.stimmabgaben.count() == 1
    inhalt = client.get("/parlament/").content.decode()
    assert "gewaehlt" in inhalt  # die eigene Stimme ist markiert

    antwort = client.post(
        reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja", "weiter": "https://boese"}
    )
    assert antwort.url.startswith("/antrag/")  # unsichere Ziele fallen auf die Antragsseite zurück


def test_mandat_kachel_fuehrt_zur_wahl_statt_ja_nein(client, ordnung):  # noqa: F811
    from verfahren.models import bewerbung_einreichen

    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = antrag_einbringen(leute[0], "Listenreihung Gemeinderat", "W.", "", ordnung,
                               ebene="gemeinde", gebiet="St. Marienkirchen an der Polsenz",
                               art=Antragsart.MANDAT)
    bewerbung_einreichen(antrag, leute[1], "Ich trete an.")
    in_abstimmung_bringen(antrag, leute[1:])

    client.force_login(leute[2])
    inhalt = client.get("/parlament/").content.decode()
    assert "Zur Wahl der Bewerbungen" in inhalt
    assert f'action="/antrag/{antrag.pk}/abstimmen/"' not in inhalt  # keine Ja/Nein-Knöpfe


def test_bezirksantrag_folgt_dem_wohnsitzprofil(client, ordnung):  # noqa: F811
    g = Gemeinde.objects.create(kennziffer="41310", name="St. Marienkirchen an der Polsenz",
                                bezirk="Eferding", bundesland="oberoesterreich")
    anna = mitglied_anlegen("anna")
    anna.wohnsitz = g
    anna.save(update_fields=["wohnsitz"])

    client.force_login(anna)
    inhalt = client.get(reverse("verfahren:einbringen")).content.decode()
    assert "Mein Bezirk (Eferding)" in inhalt
    client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "bezirk"})
    antrag = Antrag.objects.get()
    assert antrag.ebene == "bezirk" and antrag.gebiet == "Eferding"

    inhalt = client.get("/parlament/").content.decode()
    assert "Bezirk · Eferding" in inhalt  # die Bezirkszeile trägt jetzt den eigenen Ort
