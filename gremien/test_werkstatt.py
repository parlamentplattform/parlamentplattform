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


def systembeitrag(antrag):
    """Der Beitrag „Passt alles", den die Plattform beim Öffnen des Abstimmungs-Chats anlegt."""
    return antrag.kommentare.get(system=True, archiviert_am__isnull=True)


def reagieren(client, antrag, beitrag, mitglied, art="zustimmung"):
    client.force_login(mitglied)
    return client.post(reverse("verfahren:reagieren", args=[antrag.pk, beitrag.pk]), {"art": art})


def schreiben(client, antrag, mitglied, text, kritik=False, absatz=None):
    client.force_login(mitglied)
    daten = {"text": text}
    if kritik:
        daten["ist_kritik"] = "1"
        if absatz:
            daten["bezug_absatz"] = str(absatz)
    client.post(reverse("verfahren:kommentieren", args=[antrag.pk]), daten)
    return antrag.kommentare.filter(mitglied=mitglied).order_by("-erstellt_am").first()


def frist_setzen(entwurf, frist):
    """Zeitraffer der Unterstützer-Frist: Die Frist rückt in die Vergangenheit, und mit ihr die Reaktionen
    dieses Antrags — sie wurden ja vor dem Fristende abgegeben. Gezählt wird der Stand zum Fristende
    (§ 5 Abs 13, Bestandsaufnahme A8); ohne die Verschiebung lägen die Klicks des Tests „nach“ der Frist."""
    from django.db.models import F

    from verfahren.models import Reaktion

    versatz = timezone.now() - frist + timedelta(minutes=5)
    Reaktion.objects.filter(kommentar__antrag_id=entwurf.antrag_id).update(
        erstellt_am=F("erstellt_am") - versatz, zurueckgenommen_am=F("zurueckgenommen_am") - versatz
    )
    Entwurf.objects.filter(pk=entwurf.pk).update(review_frist=frist)


def frist_verstreichen(entwurf):
    """Ausgewertet wird nach Fristablauf — bis dahin sind Reaktionen umschaltbar (FB-G6)."""
    frist_setzen(entwurf, timezone.now() - timedelta(hours=1))


def fenster_oeffnen(client, antrag, rat):
    client.force_login(rat)
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "oeffnen"})
    return Entwurf.objects.get(antrag=antrag)


def einreichen(client, antrag, raete, vollzugsbezug=False):
    """Werkstatt im Zeitraffer: öffnen, die Einreichung beschließen (alle stimmen dafür)."""
    from gremien.models import Anlass, BeschlussStatus, GremienBeschluss

    entwurf = fenster_oeffnen(client, antrag, raete[0])
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    if vollzugsbezug:
        client.post(aktion, {"aktion": "vollzugsbezug", "vollzugsbezug": "ja"})
    client.post(aktion, {"aktion": "einreichung"})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag, status=BeschlussStatus.OFFEN)
    for rat in raete:
        client.force_login(rat)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": "dafuer", "begruendung": "Reif.", "interessenbindung": "keine"},
        )
    entwurf.refresh_from_db()
    return entwurf


# --- Rollen auf Zeit (§ 6 Abs 8) ---------------------------------------------


def test_oeffentliche_gremien_seite_zeigt_besetzung(client, ordnung):  # noqa: F811
    erika, wanda = mitglied_anlegen("erika"), mitglied_anlegen("wanda_vormals")
    rolle_geben(erika)
    abgelaufen = rolle_geben(wanda)
    abgelaufen.endet_am = timezone.localdate() - timedelta(days=1)
    abgelaufen.save()
    inhalt = client.get("/gremien/").content.decode()
    assert erika.anzeigename in inhalt and wanda.anzeigename not in inhalt  # Rollen erlöschen automatisch
    assert "erika" not in inhalt and "wanda_vormals" not in inhalt  # der Anmeldename steht nirgends
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
    # Seit 0.45 liest, wer eine Rolle hatte, weiter — mit Band; schreiben nicht (FB-I1).
    antwort = client.get(reverse("gremien:expertenrat"))
    assert antwort.status_code == 200 and "Ihre Rolle wurde beendet" in antwort.content.decode()
    client.post(reverse("gremien:rat_beschluss", args=["expertenrat1"]), {"gegenstand": "X", "beschreibung": "Y"})
    from gremien.models import GremienBeschluss

    assert not GremienBeschluss.objects.exists()


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


def test_eine_zweite_parteiweite_rolle_derselben_person_wird_abgewiesen(client, ordnung):  # noqa: F811
    """Befund #38: Doppelklick oder Verlängerung vor Ablauf legten eine zweite Zeile an — und die
    Person zählte doppelt im Quorum. Geloste Rollen bleiben unberührt: Wer für einen Antrag gelost
    ist, darf trotzdem parteiweit berufen werden."""
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    wer = mitglied_anlegen("doppelt")
    antrag, *_ = werkstatt_lage(ordnung)
    Rolle.objects.create(mitglied=wer, gremium=Gremium.EXPERTENRAT_1, endet_am=standard_ende(), antrag=antrag)
    client.force_login(admin)
    daten = {
        "aktion": "berufen",
        "mitglied": wer.pk,
        "gremium": Gremium.EXPERTENRAT_1,
        "endet_am": standard_ende().isoformat(),
    }
    client.post(reverse("gremien:rollen_aktion"), daten)
    assert Rolle.objects.filter(mitglied=wer, antrag__isnull=True).count() == 1  # trotz geloster Rolle
    antwort = client.post(reverse("gremien:rollen_aktion"), {**daten, "endet_am": (standard_ende() + timedelta(days=30)).isoformat()}, follow=True)
    assert Rolle.objects.filter(mitglied=wer, antrag__isnull=True).count() == 1
    assert "schon eine aktive Rolle" in antwort.content.decode()
    assert sum(1 for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "rolle_berufen") == 1


def test_nach_dem_beratungsende_ruht_die_werkstatt(client, ordnung):  # noqa: F811
    """Befund #34: Nur „öffnen“ war an die Beratung gebunden. Nach dem Phasenwechsel konnte
    Gruppe 1 weiter Fassungen anhängen und einreichen — das archivierte den Chat der laufenden
    Abstimmung und sperrte ihn, und niemand wertete die Schleife je wieder aus."""
    from verfahren.models import Kommentar

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"  # ein unfertiges Fenster hält nichts auf
    beitrag = antrag.kommentare.create(mitglied=unterstuetzer[0], text="Ein Beitrag zur laufenden Abstimmung.", phase="abstimmung")

    client.force_login(er[0])
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "fassung", "wortlaut": "Nachgeschoben."})
    client.post(aktion, {"aktion": "beitrag", "text": "Noch ein Beitrag."})
    client.post(aktion, {"aktion": "vollzugsbezug", "vollzugsbezug": "ja"})
    client.post(aktion, {"aktion": "einreichung"})
    entwurf.refresh_from_db()
    assert entwurf.fassungen.count() == 1 and entwurf.beitraege.count() == 0
    assert entwurf.vollzugsbezug is False and entwurf.einreichungsbeschluss() is None
    assert entwurf.einreichen() is False  # auch der direkte Weg (Wirkung eines späten Beschlusses)
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.eingereicht_am is None
    beitrag.refresh_from_db()
    assert beitrag.archiviert_am is None and not Kommentar.objects.filter(system=True).exists()
    assert any(e.ereignis["typ"] == "vorschlag_einreichung_verworfen" for e in AuditEintrag.objects.all())
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert 'value="fassung"' not in inhalt and 'value="einreichung"' not in inhalt
    assert "nicht (mehr) in der Beratung" in inhalt


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
    """Seit 0.45 ein Beschluss nach § 6 Abs 2 lit e: beschlussfähig ab der Hälfte, entschieden
    mit einfacher Mehrheit — ausgewertet, wenn alle gestimmt haben oder die Frist um ist."""
    from datetime import timedelta

    from gremien.models import Anlass, GremienBeschluss

    antrag, _, er = werkstatt_lage(ordnung, raete=3)  # nötig: 2 von 3
    entwurf = fenster_oeffnen(client, antrag, er[0])
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "einreichung"})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    stimme = reverse("gremien:beschluss_stimme", args=[beschluss.pk])
    client.post(stimme, {"option": "dafuer", "begruendung": "Reif.", "interessenbindung": "keine"})
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=timezone.now() - timedelta(minutes=1))
    beschluss.refresh_from_db()
    beschluss.abschliessen()
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT  # 1 Ja von 3 reicht nicht — kein Ergebnis
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "einreichung"})
    zweiter = GremienBeschluss.objects.filter(anlass=Anlass.EINREICHUNG, antrag=antrag).order_by("-pk").first()
    for rat in er[:2]:
        client.force_login(rat)
        client.post(
            reverse("gremien:beschluss_stimme", args=[zweiter.pk]),
            {"option": "dafuer", "begruendung": "Reif.", "interessenbindung": "keine"},
        )
    GremienBeschluss.objects.filter(pk=zweiter.pk).update(frist=timezone.now() - timedelta(minutes=1))
    zweiter.refresh_from_db()
    zweiter.abschliessen()
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


def test_zustimmung_im_chat_oeffnet_die_endabstimmung(client, ordnung):  # noqa: F811
    """FB-G6: „Passt alles" steht oben und trägt mehr als 50 % — der Vorschlag geht weiter."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "fassung", "wortlaut": "Egal."})  # Werkstatt ruht: abgewiesen
    entwurf = Entwurf.objects.get(antrag=antrag)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "abstimmung" and entwurf.status == EntwurfsStatus.ANGENOMMEN
    assert antrag.aktueller_text().wortlaut == ANTRAG["wortlaut"]  # der Vorschlag als neue Fassung
    assert "§ 5 Abs 12" in antrag.aktueller_text().begruendung
    from verfahren.models import AuditEintrag

    gruende = [e.ereignis.get("grund", "") for e in AuditEintrag.objects.all()]
    assert any("an erster Stelle" in g for g in gruende), "die Rechnung steht offen im Audit"
    assert antrag.stimmberechtigte_anzahl is not None


def test_kritik_mit_mehr_engagement_startet_eine_neue_runde(client, ordnung):  # noqa: F811
    """Steht ein Kritik-Beitrag oben, geht der Vorschlag zurück — auch wenn „Passt alles"
    für sich genommen Zustimmung hätte (D-G6b: oben *und* über der Schwelle)."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0])
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Die Frist von 48 Stunden ist zu lang — binnen 24 Stunden muss das Protokoll stehen.",
        kritik=True, absatz=1,
    )
    assert kritik is not None and kritik.ist_kritik and kritik.bezug_absatz == 1
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "beratung"  # zurück in die Werkstatt …
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 2
    assert entwurf.ueberarbeitung_frist is not None
    assert entwurf.haelt_beratung_offen()  # … und die Überarbeitung hält die Beratung offen
    from verfahren.chat import kritik_der_runde

    wuensche = kritik_der_runde(antrag, 1)
    assert len(wuensche) == 1 and wuensche[0]["absatz"] == 1, "die Kritik liegt als Wunsch bereit"


def test_die_annahme_schwelle_folgt_der_eingefrorenen_ordnung(client, ordnung):  # noqa: F811
    """Befund #3: Die Schwelle, die über Endabstimmung oder Rückgabe entscheidet, stand bis
    0.44 im laufenden Register — und die Verwaltung konnte sie am Tag vor der Frist ändern.
    § 5 Abs 5 schreibt sie beim Einbringen fest; ein Verstoß macht die Abstimmung ungültig.
    Hier: 3:2 (60 %) für „Passt alles“, das Register sagt danach 70 % — der Vorschlag geht
    trotzdem zur Endabstimmung, weil für diesen Antrag 50 % gelten."""
    from parameter.models import Parameter

    stellerin = mitglied_anlegen("stellerin")
    unterstuetzer = [mitglied_anlegen(f"u{i}") for i in range(5)]
    er = [mitglied_anlegen(f"rat{i}") for i in range(2)]
    for m in er:
        rolle_geben(m)
    antrag = in_beratung_bringen(antrag_einbringen(stellerin, **ANTRAG, ordnung=ordnung), unterstuetzer)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer[:3]:
        reagieren(client, antrag, passt, u)
    for u in unterstuetzer[3:]:
        reagieren(client, antrag, passt, u, art="ablehnung")
    Parameter.objects.update_or_create(
        schluessel="vorschlag-annahme-prozent",
        defaults={"wert": "70", "beschreibung": "x", "quelle": "Test"},
    )
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "abstimmung" and entwurf.status == EntwurfsStatus.ANGENOMMEN
    gruende = [e.ereignis.get("grund", "") for e in AuditEintrag.objects.all()]
    assert any("Schwelle 50 %" in g for g in gruende), "gerechnet wurde mit der eingefrorenen Schwelle"


def test_die_hoechstrunden_folgen_der_eingefrorenen_ordnung(client, ordnung):  # noqa: F811
    """Befund #3/#16: `gremien-hoechstrunden` von 3 auf 1 gesenkt — ein Antrag, für den beim
    Einbringen drei Runden galten, bekommt bei Rückgabe-Mehrheit trotzdem seine zweite Runde."""
    from parameter.models import Parameter

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Die Frist von 48 Stunden ist zu lang — binnen 24 Stunden muss das Protokoll stehen.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    Parameter.objects.update_or_create(
        schluessel="gremien-hoechstrunden",
        defaults={"wert": "1", "beschreibung": "x", "quelle": "Test"},
    )
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "beratung"
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 2


def test_kritik_braucht_bezug_und_konkretheit(client, ordnung):  # noqa: F811
    """A0-07: „muss konkrete Kritik beinhalten" — ohne Textstelle und Länge keine Kritik."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    knapp = schreiben(client, antrag, unterstuetzer[0], "Gefällt mir nicht.", kritik=True, absatz=1)
    assert knapp is None, "zu kurz — kein Beitrag"
    ohne_bezug = schreiben(
        client, antrag, unterstuetzer[0],
        "Die Frist von 48 Stunden ist zu lang — binnen 24 Stunden muss das Protokoll stehen.",
        kritik=True,
    )
    assert ohne_bezug is None, "ohne Absatzbezug keine Kritik"


def test_reagieren_nur_fuer_unterstuetzer(client, ordnung):  # noqa: F811
    """Im Abstimmungs-Chat wählen die Unterstützer (§ 5 Abs 12) — mitreden dürfen alle."""
    antrag, _, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    fremde = mitglied_anlegen("fremde")
    reagieren(client, antrag, passt, fremde)
    assert passt.reaktionen.count() == 0
    assert schreiben(client, antrag, fremde, "Ich lese hier mit und möchte etwas anmerken.") is not None


def test_ablehnung_zaehlt_und_laesst_sich_umschalten(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0], art="ablehnung")
    assert passt.reaktionen.aktive().get().art == "ablehnung"
    reagieren(client, antrag, passt, unterstuetzer[0], art="zustimmung")
    assert passt.reaktionen.aktive().get().art == "zustimmung", "eine geltende Reaktion je Mitglied, umschaltbar"
    reagieren(client, antrag, passt, unterstuetzer[0], art="zustimmung")
    assert passt.reaktionen.aktive().count() == 0, "derselbe Knopf nimmt zurück"
    # Append-only (Bestandsaufnahme A8): Die Geschichte bleibt — zwei gestempelte Zeilen, keine gelöscht.
    assert passt.reaktionen.count() == 2 and not passt.reaktionen.filter(zurueckgenommen_am__isnull=True).exists()


def _audit_reaktionen():
    return [e.ereignis for e in AuditEintrag.objects.order_by("lfd") if e.ereignis["typ"].startswith("reaktion")]


def test_jeder_klick_im_abstimmungschat_steht_im_audit_ohne_person(client, ordnung):  # noqa: F811
    """Entscheidung E7 (Bauplan 0.51.0): Im Abstimmungs-Chat ist die Reaktion das Votum — Abgabe, Wechsel
    und Rücknahme je ein Eintrag, ohne Mitglied und ohne Pseudonym."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    u = unterstuetzer[0]
    reagieren(client, antrag, passt, u, art="zustimmung")
    reagieren(client, antrag, passt, u, art="ablehnung")
    reagieren(client, antrag, passt, u, art="ablehnung")
    ereignisse = _audit_reaktionen()
    assert [e["typ"] for e in ereignisse] == ["reaktion", "reaktion_gewechselt", "reaktion_zurueckgenommen"]
    assert ereignisse[0] == {**ereignisse[0], "antrag": antrag.pk, "beitrag": passt.pk, "runde": 1, "reaktion": "zustimmung"}
    assert ereignisse[1]["von"] == "zustimmung" and ereignisse[1]["zu"] == "ablehnung"
    assert ereignisse[2]["reaktion"] == "ablehnung"
    import json

    roh = json.dumps(ereignisse)
    assert "mitglied" not in roh and "pseudonym" not in roh and u.username not in roh


def test_die_auswertung_zaehlt_nur_geltende_reaktionen_zum_fristende(client, ordnung):  # noqa: F811
    """Drei Unterstützer stimmen „Passt alles“ zu; einer nimmt zurück, einer wechselt auf Ablehnung.
    Gezählt werden 1 Ja und 1 Nein — nichts wurde gelöscht (Bestandsaufnahme A8)."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    dritte = mitglied_anlegen("u-dritte")
    antrag.unterstuetzungen.create(mitglied=dritte)
    unterstuetzer = [*unterstuetzer, dritte]
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer[:3]:
        reagieren(client, antrag, passt, u)
    reagieren(client, antrag, passt, unterstuetzer[1])  # zurück
    reagieren(client, antrag, passt, unterstuetzer[2], art="ablehnung")  # gewechselt
    assert passt.reaktionen.count() == 4
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    auswertung = [e.ereignis for e in AuditEintrag.objects.all() if "auswertung" in e.ereignis][-1]["auswertung"]
    assert (auswertung["ja"], auswertung["nein"]) == (1, 1)  # 50 % — nicht über der Schwelle: zurück


def test_nach_dem_fristende_zaehlt_keine_reaktion_mehr(client, ordnung):  # noqa: F811
    """§ 5 Abs 13: „bis zum Fristende“. Eine Reaktion nach der Frist wird abgewiesen — der Klick schreibt
    zuerst fort, die Runde ist ausgewertet, der Beitrag im Archiv."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0])
    frist_verstreichen(entwurf)  # niemand hat die Seite seither geöffnet
    reagieren(client, antrag, passt, unterstuetzer[1], art="ablehnung")
    assert not passt.reaktionen.filter(mitglied=unterstuetzer[1]).exists()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    auswertung = [
        e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == "phasenwechsel" and "auswertung" in e.ereignis
    ][-1]["auswertung"]
    assert (auswertung["ja"], auswertung["nein"]) == (1, 0)


def test_eine_reaktion_nach_der_stichzeit_zaehlt_in_der_rechnung_nicht(client, ordnung):  # noqa: F811
    """Auch wenn eine Zeile nach dem Fristende gespeichert wurde (Nebenläufigkeit, Altbestand), rechnet
    die Auswertung mit dem Stand zum Fristende."""
    from verfahren.chat import abstimmung_stand
    from verfahren.models import Reaktion

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0])
    stichzeit = timezone.now()
    Reaktion.objects.create(
        kommentar=passt, mitglied=unterstuetzer[1], art="ablehnung", erstellt_am=stichzeit + timedelta(minutes=1)
    )
    entwurf.refresh_from_db()
    assert abstimmung_stand(antrag, entwurf, 0.5)["nein"] == 1
    assert abstimmung_stand(antrag, entwurf, 0.5, stichzeit=stichzeit)["nein"] == 0


def test_alle_zurueckgenommen_ist_stille_und_hemmt_nie(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u, art="ablehnung")
        reagieren(client, antrag, passt, u, art="ablehnung")
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"  # Untätigkeit hemmt nie (§ 5 Abs 12, 13)


def test_stille_hemmt_nie(client, ordnung):  # noqa: F811
    """Kein einziger Unterstützer rührt sich — nach Fristablauf geht der
    Vorschlag trotzdem zur Endabstimmung (§ 5 Abs 12)."""
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"


def test_verstrichene_ueberarbeitung_geht_zur_endabstimmung(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()  # Rückgabe: Runde 2 läuft
    Entwurf.objects.filter(pk=entwurf.pk).update(
        ueberarbeitung_frist=timezone.now() - timedelta(hours=1)
    )
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert antrag.phase == "abstimmung"  # die zuletzt vorgelegte Fassung — Untätigkeit hemmt nie
    assert entwurf.status == EntwurfsStatus.ANGENOMMEN


def test_die_schleife_wirkt_ab_fristablauf_nicht_ab_seitenaufruf(client, ordnung):  # noqa: F811
    """Befund #33: Niemand öffnet den Antrag fünf Tage lang — die Endabstimmung beginnt trotzdem
    mit dem Fristzeitpunkt, nicht mit dem zufälligen Moment des Aufrufs. Sonst bekämen zwei
    Anträge mit gleichen Fristen je nach Besucherverhalten verschiedene Abstimmungsfenster."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    frist = timezone.now() - timedelta(days=5)
    frist_setzen(entwurf, frist)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung" and antrag.phase_beginn == frist
    assert antrag.stimmberechtigung_stichtag == timezone.localdate(frist)
    wechsel = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "phasenwechsel"][-1]
    assert wechsel["wirksam_ab"] == frist.isoformat()


def test_die_ueberarbeitungsfrist_zaehlt_ab_dem_fristablauf_der_rueckgabe(client, ordnung):  # noqa: F811
    """Befund #33, Rückgabe-Fall: Der Expertenrat bekommt keine Tage geschenkt, weil niemand hinsah."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist = timezone.now() - timedelta(days=5)
    frist_setzen(entwurf, frist)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert entwurf.runde == 2
    assert entwurf.ueberarbeitung_frist == frist + timedelta(days=antrag.policy().ueberarbeitung_tage)
    rueckgabe = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "vorschlag_zurueckgegeben"][-1]
    assert rueckgabe["wirksam_ab"] == frist.isoformat()


def test_ein_nie_eingereichter_arbeitsstand_geht_nicht_zur_endabstimmung(client, ordnung):  # noqa: F811
    """Befund #5: Nach der Rückgabe hängt Gruppe 1 einen Arbeitsstand an und schweigt dann.
    Verstreicht die Überarbeitungsfrist, geht die zuletzt **vorgelegte** Fassung zur
    Endabstimmung (§ 5 Abs 12) — nicht der Arbeitsstand, den kein Organ freigegeben hat."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    assert entwurf.eingereichte_fassung == 1
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()  # Rückgabe: Runde 2 läuft
    client.force_login(er[0])
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "fassung", "wortlaut": "Arbeitsstand — Absatz 4 fehlt noch.", "begruendung": "unfertig"},
    )
    entwurf.refresh_from_db()
    assert entwurf.aktuelle_fassung().nummer == 2 and entwurf.eingereichte_fassung == 1
    Entwurf.objects.filter(pk=entwurf.pk).update(ueberarbeitung_frist=timezone.now() - timedelta(hours=1))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    text = antrag.aktueller_text()
    assert antrag.phase == "abstimmung"
    assert text.wortlaut == ANTRAG["wortlaut"] and "Arbeitsstand" not in text.wortlaut
    assert "Entwurfsfassung 1" in text.begruendung


def test_antragsseite_zeigt_den_abstimmungschat_offen(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    schreiben(
        client, antrag, unterstuetzer[0],
        "Auch die Ausschüsse gehören erfasst — der erste Absatz nennt nur die Sitzungen des Gemeinderats.",
        kritik=True, absatz=1,
    )
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Entwurfsschleife" in inhalt
    assert ANTRAG["wortlaut"] in inhalt  # der Vorschlag im Wortlaut, gepinnt
    assert "Passt alles" in inhalt  # der Systembeitrag, auf den sich die Auswertung bezieht
    assert "Auch die Ausschüsse gehören erfasst" in inhalt  # die Kritik steht offen
    assert "Kritik · Absatz 1" in inhalt  # mit Textstellenbezug
    assert "Reihung: Engagement" in inhalt  # die Regel ist offengelegt (§ 2 Abs 6)
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


def test_das_fenster_nennt_die_frist_fuer_den_erstvorschlag(client, ordnung):  # noqa: F811
    """FB-J1: Der Expertenrat muss sehen, bis wann sein erster Vorschlag da sein muss.

    Das Fenster zeigte bisher nur die Fristen der späteren Runden. Genannt wird das Datum aus
    der **eingefrorenen** Ordnung des Antrags (§ 5 Abs 5) — eine kürzere Frist im Register darf
    einem laufenden Verfahren keine Zeit nehmen."""
    from datetime import timedelta

    from django.utils.timezone import localtime

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    # In Ortszeit vergleichen: Die Vorlage zeigt Wiener Zeit, gespeichert wird UTC — abends
    # liegen die beiden Daten einen Tag auseinander.
    ende = localtime(antrag.phase_beginn + timedelta(days=antrag.policy().beratung_tage))
    assert "Erstvorschlag bis" in inhalt
    assert ende.strftime("%d.%m.%Y") in inhalt
    assert "Untätigkeit hemmt nie" in inhalt

    # Auch mit offenem Fenster in Runde 1 steht die Frist da — dann wird ja gearbeitet
    fenster_oeffnen(client, antrag, er[0])
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "Erstvorschlag bis" in inhalt


def test_die_frist_folgt_der_eingefrorenen_ordnung_nicht_dem_register(client, ordnung):  # noqa: F811
    """Wer im Register kürzt, verkürzt kein laufendes Verfahren (§ 5 Abs 5)."""
    from datetime import timedelta

    from django.utils.timezone import localtime

    from parameter.models import Parameter

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    Parameter.objects.update_or_create(
        schluessel="expertenrat-erstvorschlag-tage",
        defaults={"wert": "21", "beschreibung": "x", "quelle": "Test"},
    )
    Parameter.objects.filter(schluessel="expertenrat-erstvorschlag-tage").update(wert="1")
    client.force_login(er[0])
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    ende = localtime(antrag.phase_beginn + timedelta(days=antrag.policy().beratung_tage))
    assert ende.strftime("%d.%m.%Y") in inhalt


def test_die_anzeige_des_abstimmungschats_liest_die_schwelle_aus_der_ordnung(client, ordnung):  # noqa: F811
    """Bestandsaufnahme A6: Chat, Entwurfsfenster und Archiv zeigen die Schwelle, mit der entschieden
    wird — die eingefrorene, nicht die des Registers."""
    from parameter.models import Parameter
    from verfahren import chat as chatkern

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    Parameter.objects.update_or_create(
        schluessel="vorschlag-annahme-prozent", defaults={"wert": "70", "einheit": "%", "beschreibung": "x"}
    )
    stand = chatkern.abstimmung_stand(antrag)
    assert stand["schwelle"] == 0.5 and stand["schwelle_prozent"] == 50 and stand["schwelle_vorgabe"] is False
    client.logout()
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Schwelle 50 %" in seite and "Schwelle 70 %" not in seite
    client.force_login(er[0])
    fenster = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "Schwelle 50 %" in fenster
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER


# ── „So kam der Vorschlag zustande“ in der Endabstimmung (D-G5, 0.51.0) ─────────────────────


def _zone_chat(inhalt: str) -> str:
    return inhalt.split('id="zone-chat"', 1)[1].split('id="zone-archiv"', 1)[0]


def _block(inhalt: str) -> str:
    teil = inhalt.split('id="zustandekommen"', 1)[1]
    return teil.split("</details>", 1)[0]


def _zur_endabstimmung_mit_kritik(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Die Frist von 48 Stunden ist zu lang — binnen 24 Stunden muss das Protokoll stehen.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    reagieren(client, antrag, kritik, unterstuetzer[1])
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    return antrag, unterstuetzer


def test_in_der_endabstimmung_steht_der_eingefrorene_chat_in_zone_3(client, ordnung):  # noqa: F811
    """FB-G5: „in Zone 3 der Endabstimmung als aufklappbarer Block ‚So kam der Vorschlag zustande‘ —
    die Abstimmenden sollen die Kritik sehen.“ Für Gast und Mitglied gleich, ohne Formulare."""
    antrag, unterstuetzer = _zur_endabstimmung_mit_kritik(client, ordnung)
    for wer in (None, unterstuetzer[0]):
        client.logout()
        if wer is not None:
            client.force_login(wer)
        inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
        zone = _zone_chat(inhalt)
        assert 'id="zustandekommen"' in zone and "So kam der Vorschlag zustande" in zone
        assert zone.index('id="zustandekommen"') < zone.index('id="chat-faden"')  # außerhalb des Fadens
        block = _block(inhalt)
        assert "binnen 24 Stunden muss das Protokoll stehen" in block and "Kritik · Absatz 1" in block
        assert "an erster Stelle" in block and "zur Endabstimmung" in block and "Schwelle 50 %" in block
        assert "<form" not in block and "csrfmiddlewaretoken" not in block
        assert '<details class="klappe zustandekommen" id="zustandekommen">' in inhalt  # zugeklappt, nativ


def test_der_block_reiht_nach_beteiligung_zum_fristende(client, ordnung):  # noqa: F811
    antrag, _u = _zur_endabstimmung_mit_kritik(client, ordnung)
    block = _block(client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode())
    # „Passt alles“ (2 Reaktionen) vor der Kritik (1 Reaktion) — Regel engagement-v1, verlinkt
    assert block.index("Die Plattform") < block.index("binnen 24 Stunden")
    assert "engagement-v1" in block


def test_ohne_entwurfsschleife_und_nach_dem_ergebnis_gibt_es_keinen_block(client, ordnung):  # noqa: F811
    from plattform_core import Phase

    antrag = antrag_einbringen(mitglied_anlegen("ohne"), **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(phase=Phase.ABSTIMMUNG.value)
    assert 'id="zustandekommen"' not in client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()

    mit, _u = _zur_endabstimmung_mit_kritik(client, ordnung)
    Antrag.objects.filter(pk=mit.pk).update(
        phase_beginn=timezone.now() - timedelta(days=60)
    )  # Zeitraffer: die Abstimmung ist vorbei
    inhalt = client.get(reverse("verfahren:antrag", args=[mit.pk])).content.decode()
    mit.refresh_from_db()
    assert mit.phase in ("angenommen", "abgelehnt")
    assert 'id="zustandekommen"' not in inhalt  # das Archiv behält alles (E2)


def test_zwei_runden_zeigen_die_letzte_und_verlinken_die_fruehere(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()  # zurück: Runde 2
    entwurf.refresh_from_db()
    assert entwurf.runde == 2
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    block = _block(inhalt)
    assert "Runde 2" in block.split("</summary>", 1)[0]
    assert "Ausschüsse" not in block.split("?archiv=vorschlag-r1", 1)[0].split("</summary>", 1)[1]
    assert "?archiv=vorschlag-r1#archiv-vorschlag-r1" in block and "zurück an den Expertenrat" in block


def test_verstrichene_ueberarbeitung_zeigt_die_zurueckgegebene_runde(client, ordnung):  # noqa: F811
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    Entwurf.objects.filter(pk=entwurf.pk).update(ueberarbeitung_frist=timezone.now() - timedelta(hours=1))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    block = _block(client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode())
    assert "Ausschüsse" in block and "zurück an den Expertenrat" in block


def test_bei_erreichter_hoechstzahl_der_runden_steht_zur_endabstimmung(client, ordnung):  # noqa: F811
    """§ 5 Abs 12: Die Zahl der Runden begrenzt die Ordnung — danach geht der Vorschlag zur Abstimmung,
    auch wenn „Passt alles“ nicht getragen hat. Der Block sagt, wohin er ging."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    regeln = dict(antrag.policy_snapshot, hoechstrunden=1)
    Antrag.objects.filter(pk=antrag.pk).update(policy_snapshot=regeln)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client, antrag, unterstuetzer[0],
        "Der Vorschlag lässt die Ausschüsse aus — sie gehören ausdrücklich in den ersten Absatz.",
        kritik=True, absatz=1,
    )
    for u in unterstuetzer:
        reagieren(client, antrag, kritik, u)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    block = _block(client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode())
    assert "zur Endabstimmung" in block and "zurück an den Expertenrat" not in block


def test_mit_geoeffnetem_archiv_gibt_es_keine_doppelte_kennung(client, ordnung):  # noqa: F811
    antrag, _u = _zur_endabstimmung_mit_kritik(client, ordnung)
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk]) + "?archiv=vorschlag-r1").content.decode()
    passt = antrag.kommentare.get(system=True, phase="vorschlag-r1")
    assert inhalt.count(f'id="a-{passt.pk}"') == 1 and inhalt.count(f'id="z-{passt.pk}"') == 1


def test_der_block_braucht_hoechstens_eine_abfrage_mehr(client, ordnung):  # noqa: F811
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from verfahren import archiv as archivkern

    antrag, _u = _zur_endabstimmung_mit_kritik(client, ordnung)
    bloecke = archivkern.zeitleiste(antrag)
    with CaptureQueriesContext(connection) as erfasst:
        block = archivkern.zustandekommen(antrag, bloecke)
    assert block is not None and len(erfasst) <= 2  # die Beiträge der Runde (+ Registerwert der Grenze)


# --- Gegnerische Prüfung 0.51.0 ----------------------------------------------


def test_eine_reaktion_ab_dem_fristende_wird_abgewiesen_auch_vor_der_auswertung(client, ordnung):  # noqa: F811
    """Prüfung 0.51.0 (zeit): Wer reagiert, prüft das Fristende unter derselben Sperre wie die Auswertung.
    Ein Klick ab dem Fristende zählt nie — auch wenn noch niemand ausgewertet hat."""
    from verfahren.chat import ReaktionGeschlossen, reaktion_umschalten

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    with pytest.raises(ReaktionGeschlossen):
        reaktion_umschalten(passt, unterstuetzer[0], jetzt=entwurf.review_frist)
    assert not passt.reaktionen.exists()
    assert not _audit_reaktionen()
    reaktion_umschalten(passt, unterstuetzer[0], jetzt=entwurf.review_frist - timedelta(seconds=1))
    assert passt.reaktionen.count() == 1


def test_nach_der_auswertung_nimmt_der_beitrag_keine_reaktion_mehr(client, ordnung):  # noqa: F811
    """Auch ein direkter Aufruf nach der Auswertung (die Anfrage prüfte vorher, die Runde ging inzwischen
    weiter) schreibt nichts: Die Runde ist nicht mehr bei den Unterstützern."""
    from verfahren.chat import ReaktionGeschlossen, reaktion_umschalten

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    with pytest.raises(ReaktionGeschlossen):
        reaktion_umschalten(passt, unterstuetzer[0], jetzt=timezone.now() - timedelta(days=1))
    assert not passt.reaktionen.exists()


def test_ein_fehler_der_audit_kette_geht_nicht_still_verloren(client, ordnung, monkeypatch):  # noqa: F811
    """Prüfung 0.51.0 (zeit): Scheitert der Audit-Eintrag, bleibt nichts gespeichert — und das Mitglied
    erfährt es, statt dass der Klick unbemerkt verschwindet."""
    from django.db import IntegrityError

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)

    def kette_ueberholt(ereignis):
        raise IntegrityError("Kettenkopf überholt")

    monkeypatch.setattr(AuditEintrag, "anhaengen", staticmethod(kette_ueberholt))
    client.force_login(unterstuetzer[0])
    antwort = client.post(
        reverse("verfahren:reagieren", args=[antrag.pk, passt.pk]), {"art": "zustimmung"}, HTTP_HX_REQUEST="true"
    )
    assert antwort.status_code == 200
    assert 'role="alert"' in antwort.content.decode()
    assert "noch einmal" in antwort.content.decode()
    assert not passt.reaktionen.exists()


def test_reagieren_nach_fristende_mit_htmx_meldet_und_zeichnet_neu(client, ordnung):  # noqa: F811
    """Prüfung 0.51.0 (bedienung): Mit htmx steht die Meldung im Chat-Fragment, nicht als Flash; hat der
    Klick die Runde ausgewertet, zeichnet die Seite ganz neu (Abstimmen-Karte, Block D-G5)."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    frist_verstreichen(entwurf)
    client.force_login(unterstuetzer[0])
    antwort = client.post(
        reverse("verfahren:reagieren", args=[antrag.pk, passt.pk]), {"art": "zustimmung"}, HTTP_HX_REQUEST="true"
    )
    inhalt = antwort.content.decode()
    assert 'role="alert"' in inhalt and "nicht mehr reagieren" in inhalt
    assert antwort.headers.get("HX-Refresh") == "true"
    # Die Meldung wartet nicht als Flash auf den nächsten Seitenaufruf
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "nicht mehr reagieren" not in seite


def test_der_block_zaehlt_die_abgeschlossene_runde_zum_fristende(client, ordnung):  # noqa: F811
    """Prüfung 0.51.0 (zeit): Eine Zeile, die erst nach dem Fristende gespeichert wurde, ändert weder die
    Zahlen noch die Reihung im Block „So kam der Vorschlag zustande“ noch im Archiv."""
    from verfahren.archiv import zeitleiste, zustandekommen
    from verfahren.models import Reaktion

    antrag, unterstuetzer = _zur_endabstimmung_mit_kritik(client, ordnung)
    runde = [b for b in zeitleiste(antrag, alles=True) if b["phase"] == "vorschlag-r1"][0]
    vorher = [(b["id"], b["zustimmungen"], b["ablehnungen"]) for b in runde["beitraege"]]
    passt = antrag.kommentare.get(system=True, phase="vorschlag-r1")
    Reaktion.objects.create(
        kommentar=passt, mitglied=mitglied_anlegen("spaet"), art="ablehnung", erstellt_am=timezone.now()
    )
    bloecke = zeitleiste(antrag, alles=True)
    runde = [b for b in bloecke if b["phase"] == "vorschlag-r1"][0]
    assert [(b["id"], b["zustimmungen"], b["ablehnungen"]) for b in runde["beitraege"]] == vorher
    block = zustandekommen(antrag, bloecke)
    assert [(b["id"], b["zustimmungen"], b["ablehnungen"]) for b in block["beitraege"] if not b["antwort_auf"]] == [
        v for v in vorher if v[0] in {b["id"] for b in block["beitraege"] if not b["antwort_auf"]}
    ]


def test_eine_zurueckgewiesene_runde_ging_nicht_zur_endabstimmung(client, ordnung):  # noqa: F811
    """Prüfung 0.51.0 (daten): Endet das Verfahren, während der Vorschlag bei den Unterstützern liegt
    (Zurückweisung, Rückzug), wurde die Runde nie ausgewertet — Archiv und Export sagen das, statt
    „zur Endabstimmung“ zu behaupten."""
    from verfahren.archiv import als_markdown, zeitleiste

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0])
    # wie zurueckweisung_wirkung: Phase zurückgewiesen, die Schleife ruht (Entwurf ANGENOMMEN, keine Frist)
    Antrag.objects.filter(pk=antrag.pk).update(phase="zurueckgewiesen")
    Entwurf.objects.filter(antrag=antrag).update(status=EntwurfsStatus.ANGENOMMEN, review_frist=None)
    antrag.refresh_from_db()
    runde = [b for b in zeitleiste(antrag) if b["phase"] == "vorschlag-r1"][0]
    assert runde["auswertung"]["weiter"] is None
    zeile = [z for z in als_markdown(antrag).splitlines() if z.startswith("*Auswertung")][0]
    assert "nicht ausgewertet" in zeile and "zur Endabstimmung" not in zeile
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk]) + "?archiv=vorschlag-r1").content.decode()
    zeile = seite[seite.index('class="archiv-auswertung"'):][:600]
    assert "nicht ausgewertet" in zeile and "zur Endabstimmung" not in zeile


def test_der_link_zur_reihung_fuehrt_auf_die_regel(client, ordnung):  # noqa: F811
    """Prüfung 0.51.0 (bedienung): „Reihung: Engagement …“ zeigt auf die Regel im Regelverzeichnis —
    die Registerliste trägt keinen Anker dieses Namens."""
    antrag, _unterstuetzer = _zur_endabstimmung_mit_kritik(client, ordnung)
    ziel = reverse("parameter:regeln")
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert f'href="{ziel}#regel-vorschlagschat"' in inhalt and "#vorschlag-chat-reihung" not in inhalt
    assert 'id="regel-vorschlagschat"' in client.get(ziel).content.decode()
