"""Die Einreichung als Beschluss und der Drei-Spalten-Arbeitsplatz (FB-I2, FB-I4).

Bis 0.44 zählte die Einreich-Abstimmung der Gruppe 1 mit einer eigenen Regel und einem
parteiweiten Nenner — seit der Auslosung war das falsch: Bei zwei Anträgen mit je drei
Gelosten brauchte jede Gruppe vier Ja-Stimmen von drei Menschen. Jetzt ist die Einreichung ein
Beschluss wie jeder andere (§ 6 Abs 2 lit e), gebunden an den Antrag (§ 6 Abs 7), und jede
Stimme trägt die Interessenbindungen zu dieser Sache (§ 6 Abs 7).
"""

import pytest
from django.urls import reverse

from gremien.models import (
    Anlass,
    BeschlussStatus,
    EntwurfsBeitrag,
    EntwurfsStatus,
    GremienBeschluss,
    Gremium,
    Interessenbindung,
    Rolle,
    WunschVermerk,
)
from gremien.test_werkstatt import (  # noqa: F401
    einreichen,
    fenster_oeffnen,
    mitglied_anlegen,
    ordnung,
    rolle_geben,
    werkstatt_lage,
)

pytestmark = pytest.mark.django_db


def zur_einreichung_stellen(client, antrag, rat):
    client.force_login(rat)
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "einreichung"})
    return GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag, status=BeschlussStatus.OFFEN)


def stimmen(client, beschluss, rat, option="dafuer", bindung="keine"):
    client.force_login(rat)
    return client.post(
        reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
        {"option": option, "begruendung": "Die Fassung ist reif.", "interessenbindung": bindung},
    )


def test_die_einreichung_ist_ein_beschluss_der_gruppe(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=3)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    beschluss = zur_einreichung_stellen(client, antrag, er[0])
    assert beschluss.gremium == Gremium.EXPERTENRAT_1 and beschluss.entwurf_id == entwurf.pk
    assert "Fassung 1" in beschluss.gegenstand
    stimmen(client, beschluss, er[0])
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT, "eine von drei reicht nicht"
    stimmen(client, beschluss, er[1])
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and beschluss.status == BeschlussStatus.OFFEN
    stimmen(client, beschluss, er[2])
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == "dafuer"
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER and entwurf.review_frist is not None
    assert "Eingereicht" in beschluss.umsetzungsvermerk


def test_die_helfer_der_werkstatt_tests_reichen_weiter_ein(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER


def test_ohne_interessenbindung_keine_stimme(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    fenster_oeffnen(client, antrag, er[0])
    beschluss = zur_einreichung_stellen(client, antrag, er[0])
    stimmen(client, beschluss, er[0], bindung="")
    assert beschluss.stimmen.count() == 0
    stimmen(client, beschluss, er[0], bindung="Ich berate den Radverband ehrenamtlich.")
    assert beschluss.stimmen.count() == 1
    bindung = Interessenbindung.objects.get(antrag=antrag, mitglied=er[0])
    assert bindung.text.startswith("Ich berate") and bindung.runde == 1


def test_die_interessenbindungen_stehen_oeffentlich_beim_vorschlag(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    fenster_oeffnen(client, antrag, er[0])
    beschluss = zur_einreichung_stellen(client, antrag, er[0])
    stimmen(client, beschluss, er[0], bindung="Mitglied im Verkehrsclub.")
    stimmen(client, beschluss, er[1])
    client.logout()
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Mitglied im Verkehrsclub." in seite and "Interessenbindungen" in seite


def test_waehrend_der_abstimmung_ruht_die_fassung(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    zur_einreichung_stellen(client, antrag, er[0])
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "fassung", "wortlaut": "Ein ganz anderer Text.", "begruendung": "Weil."},
    )
    assert entwurf.fassungen.count() == 1, "über einen Text, der sich ändert, stimmt niemand ab"


def test_das_quorum_zaehlt_nur_die_fuer_diesen_antrag_gelosten(client, ordnung):  # noqa: F811
    """Der Fehler, der die Umstellung nötig machte: parteiweiter Nenner bei antragsgebundenen Rollen."""
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    for rat in er:
        Rolle.objects.filter(mitglied=rat).update(antrag=antrag)
    from verfahren.models import antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG

    anderer = antrag_einbringen(mitglied_anlegen("andere"), **ANTRAG, ordnung=ordnung)
    fremde = mitglied_anlegen("fremde")
    rolle_geben(fremde, Gremium.EXPERTENRAT_1, antrag=anderer)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    beschluss = zur_einreichung_stellen(client, antrag, er[0])
    assert beschluss.aktive_rollen() == 2
    stimmen(client, beschluss, er[0])
    stimmen(client, beschluss, er[1])
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert stimmen(client, beschluss, fremde).status_code == 302 and beschluss.stimmen.count() == 2


def test_dagegen_laesst_die_werkstatt_weiterarbeiten(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    beschluss = zur_einreichung_stellen(client, antrag, er[0])
    stimmen(client, beschluss, er[0], option="dagegen")
    stimmen(client, beschluss, er[1], option="dagegen")
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and entwurf.status == EntwurfsStatus.IN_ARBEIT
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "fassung", "wortlaut": "Zweiter Anlauf.", "begruendung": "Kürzer."},
    )
    assert entwurf.fassungen.count() == 2


def test_die_drei_spalten_und_der_diff(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "fassung", "wortlaut": "Die Gemeinde legt Radwege an.\n\nSie beginnt im Norden.", "begruendung": "Zwei Absätze."},
    )
    seite = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert 'id="antrag"' in seite and 'id="entwurf"' in seite and 'id="werkzeuge"' in seite
    assert "Diff zu Fassung 1" in seite and "Arbeitsunterlage" in seite
    mit_diff = client.get(reverse("gremien:fenster", args=[antrag.pk]) + "?diff=1").content.decode()
    assert "<ins>" in mit_diff or "<del>" in mit_diff


def test_ein_beitrag_kann_an_einem_absatz_haengen(client, ordnung):  # noqa: F811
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = fenster_oeffnen(client, antrag, er[0])
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "fassung", "wortlaut": "Erster Absatz.\n\nZweiter Absatz.", "begruendung": ""},
    )
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "beitrag", "text": "Der zweite Absatz ist zu vage.", "absatz": "2"},
    )
    client.post(
        reverse("gremien:fenster_aktion", args=[antrag.pk]),
        {"aktion": "beitrag", "text": "Absatz neun gibt es nicht.", "absatz": "9"},
    )
    beitraege = list(EntwurfsBeitrag.objects.filter(entwurf=entwurf).order_by("pk"))
    assert beitraege[0].absatz == 2 and beitraege[1].absatz is None
    seite = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "Der zweite Absatz ist zu vage." in seite


def test_wuensche_der_unterstuetzer_lassen_sich_abhaken(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import frist_verstreichen, reagieren, schreiben, systembeitrag

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    kritik = schreiben(
        client,
        antrag,
        unterstuetzer[0],
        "Bitte den Zeitplan nennen: Bis wann steht der erste Abschnitt, wer trägt die Kosten, und "
        "wie wird die Umsetzung öffentlich berichtet? Ohne diese drei Angaben bleibt der Vorschlag vage.",
        kritik=True,
        absatz=1,
    )
    assert kritik is not None
    reagieren(client, antrag, systembeitrag(antrag), unterstuetzer[0], art="ablehnung")
    reagieren(client, antrag, systembeitrag(antrag), unterstuetzer[1], art="ablehnung")
    frist_verstreichen(entwurf)
    entwurf.refresh_from_db()
    entwurf.fortschreiben(antrag)
    entwurf.refresh_from_db()
    assert entwurf.runde == 2
    client.force_login(er[0])
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "wunsch", "kommentar": kritik.pk})
    vermerk = WunschVermerk.objects.get(entwurf=entwurf, kommentar=kritik)
    assert vermerk.fassung == 1 and vermerk.durch == er[0]
    seite = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "berücksichtigt in Fassung 1" in seite
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "wunsch", "kommentar": kritik.pk})
    assert not WunschVermerk.objects.filter(entwurf=entwurf).exists()
