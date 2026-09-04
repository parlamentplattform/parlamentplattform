"""Ring 0a, Teil 2 — Gruppe 2 (§ 6 Abs 7) als Beschluss des Gremiums und der Koordinationsrat.

Bis 0.41 entschied hier, wer zuerst auf einen der drei Knöpfe drückte: eine einzige Person,
sofort, ohne Frist. Gruppe 2 ist als Redundanz und Korruptionsprüfung gedacht — eine Redundanz
aus einer Person ist keine. Seit FB-I3 stimmt die Gruppe ab (§ 6 Abs 2 lit e), mit Frist und
veröffentlichten Begründungen (§ 6 Abs 9)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import BeschlussStatus, EntwurfsStatus, Gremium, Pruefung, Rolle
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


def pruef_lage(client, ordnung, zweitpruefer=1):  # noqa: F811
    """Ein Vorschlag mit Vollzugsbezug liegt der Gruppe 2 vor.

    Die Rollen entstehen erst nach dem Einreichen — genau der Fall, in dem beim Einreichen noch
    niemand berufen war. Die Abstimmung muss dann nachträglich entstehen."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    gruppe2 = [mitglied_anlegen(f"pruefer{i}") for i in range(zweitpruefer)]
    for mitglied in gruppe2:
        rolle_geben(mitglied, Gremium.EXPERTENRAT_2)
    entwurf.fortschreiben(antrag)  # legt die Abstimmung an
    beschluss = entwurf.beschluesse.filter(status=BeschlussStatus.OFFEN).first()
    return antrag, entwurf, er, gruppe2, beschluss


def stimme(client, beschluss, mitglied, option, begruendung="Geprüft.", **extra):
    client.force_login(mitglied)
    return client.post(
        reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
        {"option": option, "begruendung": begruendung, **extra},
    )


def test_pruefung_nur_fuer_gruppe_2(client, ordnung):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    client.force_login(er[0])  # Gruppe 1 hat hier nichts verloren
    assert client.get(reverse("gremien:pruefung")).status_code == 403
    client.force_login(gruppe2[0])
    inhalt = client.get(reverse("gremien:pruefung")).content.decode()
    assert antrag.titel in inhalt and "validieren" in inhalt
    assert "Bieterkreis" in inhalt  # die Prüfpunkte des § 6 Abs 7 stehen im Formular


def test_gruppe_1_darf_in_gruppe_2_nicht_abstimmen(client, ordnung):  # noqa: F811
    """Sonst prüfte sich der Entwerfende selbst — das ist der ganze Zweck der zweiten Gruppe."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, er[0], "validiert")
    assert beschluss.stimmen.count() == 0


def test_pruefung_haelt_die_beratung_offen(client, ordnung):  # noqa: F811
    antrag, entwurf, *_ = pruef_lage(client, ordnung)
    beratungsfrist_ablaufen_lassen(antrag)
    antrag.fortschreiben()
    assert antrag.phase == "beratung"  # § 6 Abs 7 ist Teil der arbeitenden Schleife


def test_validieren_gibt_an_die_unterstuetzer(client, ordnung):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "validiert", "Kein Beschaffungsrisiko erkennbar.")
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER and entwurf.review_frist is not None
    # § 6 Abs 7: Die Begründung steht öffentlich auf der Antragsseite.
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Kein Beschaffungsrisiko erkennbar." in inhalt


def test_abgehakte_pruefpunkte_stehen_in_der_begruendung(client, ordnung):  # noqa: F811
    """Eine Prüfliste, die niemand sieht, prüft nichts (§ 6 Abs 7)."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "validiert", "Sauber.", punkt_bieter="1", punkt_schwellen="1")
    text = entwurf.pruefungen.get().begruendung
    assert "Bieterkreis" in text and "Schwellenwerte" in text and "Sauber." in text


def test_zurueckgeben_bringt_die_werkstatt_ans_werk(client, ordnung):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "zurueck", "Die Vergabekriterien fehlen.")
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 1
    assert any(e.ereignis["typ"] == "vorschlag_geprueft" for e in AuditEintrag.objects.all())


def test_pruefung_braucht_begruendung(client, ordnung):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "validiert", "")
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG and entwurf.pruefungen.count() == 0


def test_eine_stimme_von_dreien_entscheidet_nichts(client, ordnung):  # noqa: F811
    """Beschlussfähig ist die Gruppe erst bei der Hälfte ihrer Mitglieder (§ 6 Abs 2 lit e)."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=3)
    stimme(client, beschluss, gruppe2[0], "validiert", "Sieht gut aus.")
    beschluss.refresh_from_db()
    entwurf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OFFEN
    assert entwurf.status == EntwurfsStatus.PRUEFUNG
    stimme(client, beschluss, gruppe2[1], "validiert", "Ebenso.")
    stimme(client, beschluss, gruppe2[2], "validiert", "Ebenso.")
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER  # alle haben gestimmt


def test_gleichstand_ist_kein_ergebnis_und_haelt_trotzdem_nichts_auf(client, ordnung):  # noqa: F811
    """Zwei Stimmen, zwei Richtungen: kein Beschluss — aber auch keine Blockade (§ 5 Abs 12).

    Der Vorschlag geht weiter an die Unterstützer, und der Vermerk sagt offen, dass Gruppe 2
    ihn **nicht** validiert hat. Als „validiert" durchzugehen wäre eine Unbedenklichkeits-
    bescheinigung, die niemand ausgestellt hat; liegen zu bleiben wäre die Blockademacht, die
    das ganze Verfahren nicht kennt."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    stimme(client, beschluss, gruppe2[0], "validiert", "Unbedenklich.")
    stimme(client, beschluss, gruppe2[1], "zurueck", "Die Vergabekriterien fehlen.")
    beschluss.refresh_from_db()
    entwurf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS and beschluss.ergebnis == ""
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    vermerk = entwurf.pruefungen.get().begruendung
    assert "ohne Ergebnis" in vermerk and "Gleichstand" in vermerk
    assert "Untätigkeit hemmt nie" in vermerk


def test_schweigen_der_gruppe_2_haelt_den_antrag_nicht_auf(client, ordnung):  # noqa: F811
    """Läuft die Frist ohne eine einzige Stimme ab, geht es weiter — mit offenem Vermerk."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    beschluss.frist = timezone.now() - timedelta(minutes=1)
    beschluss.save(update_fields=["frist"])
    entwurf.fortschreiben(antrag)
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert "0 von 1 nötigen Stimmen" in entwurf.pruefungen.get().begruendung


def test_eine_stimme_laesst_sich_bis_zum_abschluss_aendern(client, ordnung):  # noqa: F811
    """Solange der Beschluss offen ist, gilt die zuletzt abgegebene Stimme — die Änderung
    bleibt vermerkt (Grundregel 7: nichts verschwindet spurlos)."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=3)
    stimme(client, beschluss, gruppe2[0], "validiert", "Erst dachte ich, es passt.")
    stimme(client, beschluss, gruppe2[0], "zurueck", "Bei genauem Lesen fehlen die Kriterien.")
    assert beschluss.stimmen.count() == 1
    eine = beschluss.stimmen.get()
    assert eine.option == "zurueck" and eine.geaendert_am is not None
    assert sum(
        1 for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "gremienstimme_abgegeben"
    ) == 2


def korat_lage(client, ordnung):  # noqa: F811
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "austausch", "Wiederholte Gefälligkeits-Formulierungen.")
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
    assert entwurf.status == EntwurfsStatus.PRUEFUNG  # Gruppe 2 muss nun neu abstimmen
    assert all(Rolle.objects.get(mitglied=rat).aktiv for rat in er)
    # Und sie bekommt dafür eine frische Abstimmung — sonst bliebe der Vorschlag liegen.
    entwurf.fortschreiben(antrag)
    assert entwurf.beschluesse.filter(status=BeschlussStatus.OFFEN).exists()


def test_die_pruefung_bleibt_nachlesbar(client, ordnung):  # noqa: F811
    """Grundregel 7: Der Beschluss samt Stimmen bleibt stehen, auch wenn der Antrag weiterläuft."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], "validiert", "Unbedenklich.")
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == "validiert"
    assert beschluss.regel_version == 1 and beschluss.stimmen.count() == 1
    assert entwurf.pruefungen.get().beschluss_id == beschluss.pk


def test_mein_verzweigt_je_rolle(client, ordnung):  # noqa: F811
    zwei = mitglied_anlegen("zwei")
    rolle_geben(zwei, Gremium.EXPERTENRAT_2)
    client.force_login(zwei)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:pruefung")
    korat = mitglied_anlegen("korat")
    rolle_geben(korat, Gremium.KOORDINATIONSRAT)
    client.force_login(korat)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:koordination")


def test_ohne_gruppe_2_wartet_der_vorschlag_sichtbar(client, ordnung):  # noqa: F811
    """Ist keine Rolle besetzt, entsteht keine Abstimmung — und die Seite sagt das auch."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    entwurf.fortschreiben(antrag)
    assert not entwurf.beschluesse.exists()
    admin = mitglied_anlegen("aufsicht")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    inhalt = client.get(reverse("gremien:pruefung")).content.decode()
    assert "keine Rolle in Gruppe 2 aktiv" in inhalt
    assert Pruefung.objects.count() == 0
