"""Ring 0a, Teil 2 — Gruppe 2 (§ 6 Abs 7) und der Koordinationsrat:
validieren, begründet zurückgeben, Austausch beantragen und entscheiden."""

import pytest
from django.urls import reverse

from gremien.models import EntwurfsStatus, Gremium, Rolle
from gremien.test_werkstatt import (  # noqa: F401
    beratungsfrist_ablaufen_lassen,
    einreichen,
    mitglied_anlegen,
    ordnung,
    rolle_geben,
    werkstatt_lage,
)
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def pruef_lage(client, ordnung):  # noqa: F811
    """Ein Vorschlag mit Vollzugsbezug liegt der Gruppe 2 vor."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    zwei = mitglied_anlegen("zweite")
    rolle_geben(zwei, Gremium.EXPERTENRAT_2)
    return antrag, entwurf, er, zwei


def test_pruefung_nur_fuer_gruppe_2(client, ordnung):  # noqa: F811
    antrag, entwurf, er, zwei = pruef_lage(client, ordnung)
    client.force_login(er[0])  # Gruppe 1 hat hier nichts verloren
    assert client.get(reverse("gremien:pruefung")).status_code == 403
    client.force_login(zwei)
    inhalt = client.get(reverse("gremien:pruefung")).content.decode()
    assert antrag.titel in inhalt and "Validieren" in inhalt


def test_pruefung_haelt_die_beratung_offen(client, ordnung):  # noqa: F811
    antrag, entwurf, *_ = pruef_lage(client, ordnung)
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "beratung"  # § 6 Abs 7 ist Teil der arbeitenden Schleife


def test_validieren_gibt_an_die_unterstuetzer(client, ordnung):  # noqa: F811
    antrag, entwurf, er, zwei = pruef_lage(client, ordnung)
    client.force_login(zwei)
    client.post(
        reverse("gremien:pruefung_aktion", args=[entwurf.pk]),
        {"ergebnis": "validiert", "begruendung": "Kein Beschaffungsrisiko erkennbar."},
    )
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER and entwurf.review_frist is not None
    # § 6 Abs 7: Die Begründung steht öffentlich auf der Antragsseite.
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Kein Beschaffungsrisiko erkennbar." in inhalt


def test_zurueckgeben_bringt_die_werkstatt_ans_werk(client, ordnung):  # noqa: F811
    antrag, entwurf, er, zwei = pruef_lage(client, ordnung)
    client.force_login(zwei)
    client.post(
        reverse("gremien:pruefung_aktion", args=[entwurf.pk]),
        {"ergebnis": "zurueck", "begruendung": "Die Vergabekriterien fehlen."},
    )
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 1
    assert any(e.ereignis["typ"] == "vorschlag_geprueft" for e in AuditEintrag.objects.all())


def test_pruefung_braucht_begruendung(client, ordnung):  # noqa: F811
    antrag, entwurf, er, zwei = pruef_lage(client, ordnung)
    client.force_login(zwei)
    client.post(reverse("gremien:pruefung_aktion", args=[entwurf.pk]), {"ergebnis": "validiert"})
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG and entwurf.pruefungen.count() == 0


def korat_lage(client, ordnung):  # noqa: F811
    antrag, entwurf, er, zwei = pruef_lage(client, ordnung)
    client.force_login(zwei)
    client.post(
        reverse("gremien:pruefung_aktion", args=[entwurf.pk]),
        {"ergebnis": "austausch", "begruendung": "Wiederholte Gefälligkeits-Formulierungen."},
    )
    korat = mitglied_anlegen("koordinatorin")
    rolle_geben(korat, Gremium.KOORDINATIONSRAT)
    return antrag, entwurf, er, korat


def test_austausch_geht_zum_korat(client, ordnung):  # noqa: F811
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG  # bleibt liegen, bis der KoRat entscheidet
    client.force_login(korat)
    inhalt = client.get(reverse("gremien:koordination")).content.decode()
    assert antrag.titel in inhalt and "Wiederholte Gefälligkeits-Formulierungen." in inhalt


def test_korat_stattgeben_tauscht_gruppe_1_aus(client, ordnung):  # noqa: F811
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    client.force_login(korat)
    client.post(
        reverse("gremien:koordination_aktion", args=[pruefung.pk]),
        {"entscheid": "stattgegeben", "begruendung": "Die Zweifel wiegen schwerer als die Verzögerung."},
    )
    entwurf.refresh_from_db()
    pruefung.refresh_from_db()
    assert pruefung.korat_entscheid == "stattgegeben"
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT  # die neue Gruppe übernimmt den Entwurf
    for rat in er:
        rolle = Rolle.objects.get(mitglied=rat)
        assert not rolle.aktiv and "Austausch" in rolle.beendet_grund
    assert any(e.ereignis["typ"] == "austausch_entschieden" for e in AuditEintrag.objects.all())


def test_korat_ablehnen_laesst_die_pruefung_bestehen(client, ordnung):  # noqa: F811
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    client.force_login(korat)
    client.post(
        reverse("gremien:koordination_aktion", args=[pruefung.pk]),
        {"entscheid": "abgelehnt", "begruendung": "Kein Anhaltspunkt für Befangenheit."},
    )
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG  # Gruppe 2 muss nun validieren oder zurückgeben
    assert all(Rolle.objects.get(mitglied=rat).aktiv for rat in er)


def test_mein_verzweigt_je_rolle(client, ordnung):  # noqa: F811
    zwei = mitglied_anlegen("zwei")
    rolle_geben(zwei, Gremium.EXPERTENRAT_2)
    client.force_login(zwei)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:pruefung")
    korat = mitglied_anlegen("korat")
    rolle_geben(korat, Gremium.KOORDINATIONSRAT)
    client.force_login(korat)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:koordination")
