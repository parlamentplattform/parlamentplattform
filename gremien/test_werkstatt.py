"""Ring 0a — die Gremien-Werkstatt (F-66/F-67): Rollen auf Zeit, das
Entwurfsfenster des Expertenrats und die Entwurfsschleife (§ 5 Abs 12).
Leitsatz der Fristlogik: Untätigkeit hemmt nie."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Entwurf, EntwurfsStatus, Gremium, Rolle, standard_ende
from verfahren.models import Antrag, AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def rolle_geben(mitglied, gremium=Gremium.EXPERTENRAT_1, **extra):
    return Rolle.objects.create(
        mitglied=mitglied, gremium=gremium, endet_am=standard_ende(), bestaetigt=True, **extra
    )


def in_beratung_bringen(antrag, unterstuetzer):
    for u in unterstuetzer:
        antrag.unterstuetzungen.create(mitglied=u)
    antrag.fortschreiben()
    assert antrag.phase == "beratung"
    return antrag


def beratungsfrist_ablaufen_lassen(antrag):
    antrag.phase_beginn = timezone.now() - timedelta(days=22)  # beratung_tage=21
    antrag.save(update_fields=["phase_beginn"])


def werkstatt_lage(ordnung, raete=2):  # noqa: F811
    """Ein Antrag in der Beratung, zwei Unterstützer, n Expertenräte."""
    stellerin = mitglied_anlegen("stellerin")
    unterstuetzer = [mitglied_anlegen(f"u{i}") for i in range(2)]
    er = [mitglied_anlegen(f"rat{i}") for i in range(raete)]
    for m in er:
        rolle_geben(m)
    antrag = in_beratung_bringen(antrag_einbringen(stellerin, **ANTRAG, ordnung=ordnung), unterstuetzer)
    return antrag, unterstuetzer, er


def fenster_oeffnen(client, antrag, rat):
    client.force_login(rat)
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "oeffnen"})
    return Entwurf.objects.get(antrag=antrag)


def einreichen(client, antrag, raete, vollzugsbezug=False):
    """Werkstatt im Zeitraffer: öffnen, Mehrheit stimmt, einreichen."""
    entwurf = fenster_oeffnen(client, antrag, raete[0])
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    if vollzugsbezug:
        client.post(aktion, {"aktion": "vollzugsbezug", "vollzugsbezug": "ja"})
    for rat in raete:
        client.force_login(rat)
        client.post(aktion, {"aktion": "stimme", "einverstanden": "ja"})
    client.post(aktion, {"aktion": "einreichen"})
    entwurf.refresh_from_db()
    return entwurf


# --- Rollen auf Zeit (§ 6 Abs 8) ---------------------------------------------


def test_oeffentliche_gremien_seite_zeigt_besetzung(client, ordnung):  # noqa: F811
    rolle_geben(mitglied_anlegen("erika"))
    abgelaufen = rolle_geben(mitglied_anlegen("wanda_vormals"))
    abgelaufen.endet_am = timezone.localdate() - timedelta(days=1)
    abgelaufen.save()
    inhalt = client.get("/gremien/").content.decode()
    assert "erika" in inhalt and "wanda_vormals" not in inhalt  # Rollen erlöschen automatisch
    assert "Koordinationsrat" in inhalt  # unbesetzte Gremien stehen trotzdem da


def test_arbeitsbereich_nur_fuer_rolleninhaber(client, ordnung):  # noqa: F811
    ohne = mitglied_anlegen("ohne")
    client.force_login(ohne)
    assert client.get(reverse("gremien:expertenrat")).status_code == 403
    rolle_geben(ohne)
    assert client.get(reverse("gremien:expertenrat")).status_code == 200
    beendet = Rolle.objects.get(mitglied=ohne)
    beendet.beendet_grund = "Austausch (Testfall)"
    beendet.save()
    assert client.get(reverse("gremien:expertenrat")).status_code == 403


def test_rollen_verwaltung_beruft_bestaetigt_und_beendet(client, ordnung):  # noqa: F811
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    wer = mitglied_anlegen("berufene")
    client.force_login(admin)
    client.post(
        reverse("gremien:rollen_aktion"),
        {
            "aktion": "berufen",
            "mitglied": wer.pk,
            "gremium": Gremium.EXPERTENRAT_1,
            "endet_am": standard_ende().isoformat(),
        },
    )
    rolle = Rolle.objects.get(mitglied=wer)
    assert not rolle.bestaetigt and rolle.aktiv
    client.post(reverse("gremien:rollen_aktion"), {"aktion": "bestaetigen", "rolle": rolle.pk})
    client.post(reverse("gremien:rollen_aktion"), {"aktion": "beenden", "rolle": rolle.pk, "grund": "Rücktritt"})
    rolle.refresh_from_db()
    assert rolle.bestaetigt and not rolle.aktiv and rolle.beendet_grund == "Rücktritt"
    typen = [e.ereignis["typ"] for e in AuditEintrag.objects.all()]
    assert {"rolle_berufen", "rolle_bestaetigt", "rolle_beendet"} <= set(typen)


def test_nav_zeigt_mein_gremium_nur_mit_rolle(client, ordnung):  # noqa: F811
    m = mitglied_anlegen("magda")
    client.force_login(m)
    assert "Mein Gremium" not in client.get("/parlament/").content.decode()
    rolle_geben(m)
    assert "Mein Gremium" in client.get("/parlament/").content.decode()
    antwort = client.get(reverse("gremien:mein"))
    assert antwort.url == reverse("gremien:expertenrat")


# --- Das Entwurfsfenster (F-66) ----------------------------------------------


def test_fenster_oeffnen_uebernimmt_antragswortlaut(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    fassung = entwurf.aktuelle_fassung()
    assert fassung.nummer == 1 and fassung.wortlaut == ANTRAG["wortlaut"]
    assert any(e.ereignis["typ"] == "entwurfsfenster_geoeffnet" for e in AuditEintrag.objects.all())


def test_fassungen_bleiben_append_only(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "fassung", "wortlaut": "Zweiter Wurf.", "begruendung": "Präziser."})
    client.post(aktion, {"aktion": "fassung", "wortlaut": "Dritter Wurf."})
    nummern = list(entwurf.fassungen.values_list("nummer", flat=True))
    assert nummern == [1, 2, 3]  # nichts wird überschrieben, nichts gelöscht


def test_schreiben_nur_mit_aktiver_rolle(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    admin = mitglied_anlegen("aufsicht")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    assert client.get(reverse("gremien:fenster", args=[antrag.pk])).status_code == 200  # zuschauen ja
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "oeffnen"})
    assert not Entwurf.objects.filter(antrag=antrag).exists()  # schreiben nein


def test_einreichen_braucht_dokumentierte_mehrheit(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=3)  # nötig: 2 von 3
    entwurf = fenster_oeffnen(client, antrag, er[0])
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "stimme", "einverstanden": "ja"})
    client.post(aktion, {"aktion": "einreichen"})
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT  # 1 Ja reicht nicht
    client.force_login(er[1])
    client.post(aktion, {"aktion": "stimme", "einverstanden": "ja"})
    client.post(aktion, {"aktion": "einreichen"})
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER and entwurf.review_frist is not None


def test_vollzugsbezug_geht_zuerst_an_gruppe_2(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    assert entwurf.status == EntwurfsStatus.PRUEFUNG  # § 6 Abs 7 vor den Unterstützern


# --- Die Entwurfsschleife (§ 5 Abs 12) ---------------------------------------


def test_laufende_schleife_haelt_die_beratung_offen(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "beratung"  # der Regelübergang wartet auf die Schleife


def test_unfertiges_fenster_hat_keine_blockademacht(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])  # geöffnet, aber nie eingereicht
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"  # die Beratung endet regulär


def test_annahme_der_unterstuetzer_oeffnet_die_endabstimmung(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "fassung", "wortlaut": "Egal."})  # Werkstatt ruht: abgewiesen
    entwurf = Entwurf.objects.get(antrag=antrag)
    for u in unterstuetzer:
        client.force_login(u)
        client.post(reverse("gremien:votum", args=[entwurf.pk]), {"votum": "annehmen"})
    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    assert antrag.phase == "abstimmung" and entwurf.status == EntwurfsStatus.ANGENOMMEN
    assert antrag.aktueller_text().wortlaut == ANTRAG["wortlaut"]  # der Vorschlag als neue Fassung
    assert "§ 5 Abs 12" in antrag.aktueller_text().begruendung
    assert antrag.stimmberechtigte_anzahl is not None


def test_rueckgabe_mehrheit_startet_neue_runde(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    for u in unterstuetzer:
        client.force_login(u)
        client.post(
            reverse("gremien:votum", args=[entwurf.pk]),
            {"votum": "zurueckgeben", "wunsch": "Bitte die Frist auf 24 Stunden schärfen."},
        )
    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    assert antrag.phase == "beratung"  # zurück in die Werkstatt …
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 2
    assert entwurf.ueberarbeitung_frist is not None
    assert entwurf.haelt_beratung_offen()  # … und die Überarbeitung hält die Beratung offen


def test_rueckgabe_braucht_einen_wunsch(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    client.force_login(unterstuetzer[0])
    client.post(reverse("gremien:votum", args=[entwurf.pk]), {"votum": "zurueckgeben", "wunsch": ""})
    assert entwurf.unterstuetzer_voten.count() == 0  # ohne Wunsch kein Votum


def test_votum_nur_fuer_unterstuetzer(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    fremde = mitglied_anlegen("fremde")
    client.force_login(fremde)
    client.post(reverse("gremien:votum", args=[entwurf.pk]), {"votum": "annehmen"})
    assert entwurf.unterstuetzer_voten.count() == 0


def test_stille_hemmt_nie(client, ordnung):  # noqa: F811
    """Kein einziger Unterstützer rührt sich — nach Fristablauf geht der
    Vorschlag trotzdem zur Endabstimmung (§ 5 Abs 12)."""
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    Entwurf.objects.filter(pk=entwurf.pk).update(review_frist=timezone.now() - timedelta(hours=1))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"


def test_verstrichene_ueberarbeitung_geht_zur_endabstimmung(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    for u in unterstuetzer:
        client.force_login(u)
        client.post(
            reverse("gremien:votum", args=[entwurf.pk]),
            {"votum": "zurueckgeben", "wunsch": "Schärfer bitte."},
        )
    Entwurf.objects.filter(pk=entwurf.pk).update(
        ueberarbeitung_frist=timezone.now() - timedelta(hours=1)
    )
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "abstimmung"  # die zuletzt vorgelegte Fassung — Untätigkeit hemmt nie
    assert entwurf.status == EntwurfsStatus.ANGENOMMEN


def test_antragsseite_zeigt_vorschlag_und_voten_offen(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    client.force_login(unterstuetzer[0])
    client.post(
        reverse("gremien:votum", args=[entwurf.pk]),
        {"votum": "zurueckgeben", "wunsch": "Auch Ausschüsse erfassen."},
    )
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Entwurfsschleife" in inhalt
    assert ANTRAG["wortlaut"] in inhalt  # der Vorschlag im Wortlaut
    assert "Auch Ausschüsse erfassen." in inhalt  # Voten offen geführt
    assert "Mit Wunsch zurückgeben ✓" in inhalt  # mein Votum markiert
    # Gäste sehen die Schleife, aber kein Formular:
    client.logout()
    gast = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Entwurfsschleife" in gast and "Vorschlag annehmen" not in gast


def test_altverfahren_ohne_entwurf_bleiben_unberuehrt(client, ordnung):  # noqa: F811
    """§ 5 Abs 5: Kein Antrag braucht die Werkstatt — ohne Entwurf läuft alles wie bisher."""
    antrag, *_ = werkstatt_lage(ordnung)
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"
    assert not Entwurf.objects.filter(antrag=antrag).exists()
    assert Antrag.objects.get(pk=antrag.pk).aktueller_text().nummer == 1
