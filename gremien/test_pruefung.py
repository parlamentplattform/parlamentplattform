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
    frist_verstreichen,
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
        1
        for e in AuditEintrag.objects.all()
        if e.ereignis["typ"] == "gremienstimme_abgegeben" and e.ereignis.get("beschluss") == beschluss.pk
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


def korat_beschliessen(client, korat, pruefung, option, grund):
    """Der Koordinationsrat entscheidet als Rat (§ 6 Abs 2 lit e): Beschluss anlegen, abstimmen."""
    from gremien.models import Anlass, GremienBeschluss

    client.force_login(korat)
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "austausch", "pruefung": pruefung.pk, "beschreibung": grund},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=pruefung.entwurf.antrag)
    client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": option, "begruendung": grund})
    return beschluss


def test_korat_stattgeben_tauscht_gruppe_1_aus(client, ordnung):  # noqa: F811
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    korat_beschliessen(client, korat, pruefung, "dafuer", "Die Zweifel wiegen schwerer als die Verzögerung.")
    entwurf.refresh_from_db()
    pruefung.refresh_from_db()
    assert pruefung.korat_entscheid == "stattgegeben" and "KR-" in pruefung.korat_begruendung
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT  # die neue Gruppe übernimmt den Entwurf
    for rat in er:
        rolle = Rolle.objects.get(mitglied=rat)
        assert not rolle.aktiv and "Austausch" in rolle.beendet_grund
    assert any(e.ereignis["typ"] == "austausch_entschieden" for e in AuditEintrag.objects.all())


def test_korat_ablehnen_laesst_die_pruefung_bestehen(client, ordnung):  # noqa: F811
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    korat_beschliessen(client, korat, pruefung, "dagegen", "Kein Anhaltspunkt für Befangenheit.")
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


def test_ohne_gruppe_2_geht_der_vorschlag_nach_der_prueffrist_weiter(client, ordnung):  # noqa: F811
    """Befund #8: Ist niemand in Gruppe 2 berufen, entstand bis 0.45 nie ein Beschluss — und
    `haelt_beratung_offen` hielt den Antrag unbefristet in der Beratung. Jetzt läuft die
    Prüffrist der eingefrorenen Ordnung ab der Einreichung; verstreicht sie, geht der Vorschlag
    mit offenem Vermerk an die Unterstützer (§ 5 Abs 12: Untätigkeit hemmt nie)."""
    from gremien.models import Entwurf

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    tage = antrag.policy().pruefung_tage
    entwurf.fortschreiben(antrag)
    assert entwurf.status == EntwurfsStatus.PRUEFUNG  # die Frist läuft noch
    Entwurf.objects.filter(pk=entwurf.pk).update(eingereicht_am=timezone.now() - timedelta(days=tage, hours=1))
    entwurf.refresh_from_db()
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER and entwurf.review_frist is not None
    vermerk = Pruefung.objects.get(entwurf=entwurf)
    assert vermerk.ergebnis == Pruefung.Ergebnis.VALIDIERT and vermerk.beschluss is None
    assert "keine Rolle besetzt" in vermerk.begruendung and "Untätigkeit hemmt nie" in vermerk.begruendung
    assert any(
        e.ereignis["typ"] == "pruefung_frist_verstrichen" and e.ereignis["grund"] == "keine_gruppe_2"
        for e in AuditEintrag.objects.all()
    )
    # Und das Verfahren läuft wirklich weiter: Nach der Unterstützerfrist folgt die Endabstimmung
    # (im Zeitraffer samt Beratungsende, vor dem die Schleife sie nicht öffnet — GP-003).
    frist_verstreichen(entwurf)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"


def test_schweigt_der_korat_verfristet_der_austauschantrag(client, ordnung):  # noqa: F811
    """Befund #8, Fall b: Ein Austauschantrag ohne Entscheidung hielt den Antrag bis 0.45 ohne
    Frist fest. Jetzt verfristet er nach der Prüffrist, der Vorschlag geht weiter — und ein
    verspäteter Beschluss des Koordinationsrats bewirkt nichts mehr."""
    from gremien.models import Anlass, GremienBeschluss

    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    # Der Rat legt den Beschluss noch rechtzeitig an — stimmt aber nicht ab.
    client.force_login(korat)
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "austausch", "pruefung": pruefung.pk, "beschreibung": "Prüfen wir."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=antrag)
    tage = antrag.policy().pruefung_tage
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=timezone.now() - timedelta(days=tage, hours=1))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    entwurf.refresh_from_db()
    pruefung.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.VERFRISTET
    assert "Untätigkeit hemmt nie" in pruefung.korat_begruendung
    # Der Koordinationsrat sieht den Antrag nicht mehr als offene Aufgabe, sondern als erledigt …
    antwort = client.get(reverse("gremien:koordination"))
    assert antwort.context["offene"] == [] and pruefung in antwort.context["entschiedene"]
    # … ein neuer Beschluss dazu lässt sich nicht mehr anlegen …
    antwort = client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "austausch", "pruefung": pruefung.pk, "beschreibung": "Zu spät."},
    )
    assert antwort.status_code == 404
    # … und der verspätet entschiedene alte tauscht niemanden mehr aus.
    client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Doch."})
    beschluss.refresh_from_db()
    entwurf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and "Ohne Wirkung" in beschluss.umsetzungsvermerk
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert all(Rolle.objects.get(mitglied=rat).aktiv for rat in er)


def test_ohne_gruppe_2_wartet_der_vorschlag_sichtbar(client, ordnung):  # noqa: F811
    """Ist keine Rolle besetzt, entsteht keine Abstimmung — und die Seite sagt das auch."""
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    entwurf.fortschreiben(antrag)
    assert not entwurf.beschluesse.filter(gremium=Gremium.EXPERTENRAT_2).exists()
    admin = mitglied_anlegen("aufsicht")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    inhalt = client.get(reverse("gremien:pruefung")).content.decode()
    assert "keine Rolle in Gruppe 2 aktiv" in inhalt
    assert Pruefung.objects.count() == 0


def test_die_unterstuetzerfrist_nach_verfristeter_pruefung_laeuft_ab_der_frist(client, ordnung):  # noqa: F811
    """Ohne Gruppe 2 läuft die Unterstützerfrist ab der Prüffrist; mit schweigender Gruppe 2 lief sie
    ab dem zufälligen Zeitpunkt der Auswertung. Jetzt in beiden Fällen ab der Frist."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    frist = timezone.now() - timedelta(days=3)
    beschluss.frist = frist
    beschluss.save(update_fields=["frist"])
    antrag.fortschreiben_bis_zum_stand()
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.entschieden_am == frist
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert entwurf.review_frist == frist + timedelta(days=antrag.policy().review_tage)


# --- GP-001: Die Schleife gibt die Beratung erst nach dem regulären Ende frei ----------------


def _abstimmung_beginnt_mit_der_freigabe(antrag):
    """Nach der Freigabe durch die Schleife: Die Abstimmung beginnt jetzt, nicht rückwirkend."""
    antrag.refresh_from_db()
    jetzt = timezone.now()
    assert antrag.phase == 'abstimmung'
    assert jetzt - antrag.phase_beginn < timedelta(minutes=1)
    assert antrag.stimmberechtigung_stichtag == timezone.localdate()
    assert antrag.stimme_zulaessig()
    # Die Frist am Ende: das volle Abstimmungsfenster der eingefrorenen Ordnung (§ 5 Abs 5).
    ende = antrag.phase_beginn + timedelta(days=antrag.policy().abstimmung_tage)
    assert ende - jetzt > timedelta(days=antrag.policy().abstimmung_tage) - timedelta(minutes=1)
    wechsel = [
        e.ereignis
        for e in AuditEintrag.objects.order_by('lfd')
        if e.ereignis['typ'] == 'phasenwechsel' and e.ereignis.get('antrag') == antrag.pk
    ]
    assert [w['neue_phase'] for w in wechsel][-1] == 'abstimmung'
    assert wechsel[-1]['wirksam_ab'] == antrag.phase_beginn.isoformat()


@pytest.mark.parametrize('tage', [27, 29])
def test_rueckgabe_nach_dem_beratungsende_beginnt_die_abstimmung_nicht_rueckwirkend(client, ordnung, tage):  # noqa: F811
    """GP-001: Gibt Gruppe 2 in Runde 1 nach dem regulären Beratungsende zurück, begann die
    Abstimmung rückwirkend zum Beratungsende — nach 29 Tagen war sie im selben Aufruf schon
    geschlossen (abgelehnt, 0 Stimmen). Der Übergang wirkt frühestens ab der Freigabe."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    antrag.phase_beginn = timezone.now() - timedelta(days=tage)
    antrag.save(update_fields=['phase_beginn'])
    antrag.fortschreiben_bis_zum_stand()
    assert antrag.phase == 'beratung'  # die Prüfung hält die Beratung offen
    stimme(client, beschluss, gruppe2[0], 'zurueck', 'Die Vergabekriterien fehlen.')
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 1
    client.logout()
    assert client.get(reverse('verfahren:antrag', args=[antrag.pk])).status_code == 200
    _abstimmung_beginnt_mit_der_freigabe(antrag)
    # Ein zweiter Aufruf und ein Wächterlauf ändern daran nichts.
    client.get(reverse('verfahren:antrag', args=[antrag.pk]))
    antrag.fortschreiben_bis_zum_stand()
    _abstimmung_beginnt_mit_der_freigabe(antrag)


def test_stattgegebener_austausch_nach_dem_beratungsende_beginnt_die_abstimmung_nicht_rueckwirkend(client, ordnung):  # noqa: F811
    """GP-001, zweiter Weg: Der Koordinationsrat gibt dem Austausch nach dem Beratungsende statt."""
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    antrag.phase_beginn = timezone.now() - timedelta(days=29)
    antrag.save(update_fields=['phase_beginn'])
    pruefung = entwurf.pruefungen.get()
    korat_beschliessen(client, korat, pruefung, 'dafuer', 'Die Zweifel wiegen schwerer.')
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT
    client.logout()
    assert client.get(reverse('verfahren:antrag', args=[antrag.pk])).status_code == 200
    _abstimmung_beginnt_mit_der_freigabe(antrag)


def test_rueckgabe_vor_dem_beratungsende_laesst_das_beratungsende_gelten(client, ordnung):  # noqa: F811
    """GP-001, Gegenprobe: Liegt die Freigabe vor dem regulären Ende, bleibt es beim Beratungsende
    der eingefrorenen Ordnung — die Korrektur verschiebt nichts, was nicht verschoben war."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], 'zurueck', 'Die Vergabekriterien fehlen.')
    beginn = timezone.now() - timedelta(days=22)
    antrag.phase_beginn = beginn
    antrag.save(update_fields=['phase_beginn'])
    Entwurf = type(entwurf)
    frei = Entwurf.objects.get(pk=entwurf.pk).beratung_freigegeben_am
    Entwurf.objects.filter(pk=entwurf.pk).update(beratung_freigegeben_am=frei - timedelta(days=5))
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'
    assert antrag.phase_beginn == beginn + timedelta(days=antrag.policy().beratung_tage)


# --- GP-027: Die Rückgabe der Gruppe 2 wirkt zum Beschlusszeitpunkt ---------------------------


def test_die_ueberarbeitungsfrist_nach_rueckgabe_der_gruppe_2_laeuft_ab_dem_beschluss(client, ordnung):  # noqa: F811
    """GP-027: Schließt die Frist den Prüfbeschluss, gilt er zur Frist — die Überarbeitungsfrist der
    Gruppe 1 begann aber mit dem zufälligen Zeitpunkt der Auswertung (Wächter, Seitenaufruf). Zwei
    Anträge mit gleichen Fristen bekamen so verschieden lange Überarbeitungsfenster."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=3)
    type(entwurf).objects.filter(pk=entwurf.pk).update(runde=2)  # eine Überarbeitungsrunde liegt zur Prüfung vor
    for mitglied in gruppe2[:2]:
        stimme(client, beschluss, mitglied, 'zurueck', 'Die Vergabekriterien fehlen.')
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OFFEN  # die dritte Stimme fehlt — die Frist schließt
    frist = timezone.now() - timedelta(days=3)
    type(beschluss).objects.filter(pk=beschluss.pk).update(frist=frist)
    antrag.fortschreiben_bis_zum_stand()
    beschluss.refresh_from_db()
    entwurf.refresh_from_db()
    assert beschluss.entschieden_am == frist and beschluss.ergebnis == 'zurueck'
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.runde == 2
    assert entwurf.ueberarbeitung_frist == frist + timedelta(days=antrag.policy().ueberarbeitung_tage)
    rueckgabe = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'vorschlag_zurueckgegeben'][-1]
    assert rueckgabe['wirksam_ab'] == frist.isoformat()


def test_die_freigabe_nach_rueckgabe_in_runde_1_ist_der_beschlusszeitpunkt(client, ordnung):  # noqa: F811
    """GP-027 und GP-001 zusammen: In Runde 1 gibt die Rückgabe die Beratung frei — zum Beschlusszeitpunkt."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=3)
    for mitglied in gruppe2[:2]:
        stimme(client, beschluss, mitglied, 'zurueck', 'Die Vergabekriterien fehlen.')
    frist = timezone.now() - timedelta(hours=2)
    type(beschluss).objects.filter(pk=beschluss.pk).update(frist=frist)
    antrag.fortschreiben_bis_zum_stand()
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.beratung_freigegeben_am == frist


# --- GP-011: Kein Name, keine Kennung, kein Stimmtext im Audit ------------------------------


def test_die_rueckgabe_der_gruppe_2_schreibt_keinen_namen_ins_audit(client, ordnung):  # noqa: F811
    """GP-011: Die Rückgabe hängte Name oder „Mitglied n“ samt Stimmtext als `grund` an die
    öffentliche Kette — dort nicht mehr zu entfernen. Jetzt steht dort nur ein Verweis; die
    Antragsseite liest die Begründungen aus den Stimmen, mit dem jeweils geltenden Anzeigenamen."""
    import json

    from mitglieder.profil import austreten

    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    petra, ohne = gruppe2
    petra.first_name, petra.last_name, petra.klarname_oeffentlich = 'Petra', 'Probekind', True
    petra.save()
    stimme(client, beschluss, petra, 'zurueck', 'Die Vergabekriterien fehlen völlig.')
    stimme(client, beschluss, ohne, 'zurueck', 'Kein Vergleichsangebot vorhanden.')
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT
    kette = '\n'.join(json.dumps(e.ereignis, ensure_ascii=False) for e in AuditEintrag.objects.all())
    assert 'Probekind' not in kette and f'Mitglied {ohne.pk}' not in kette
    assert 'Vergabekriterien' not in kette and 'Vergleichsangebot' not in kette
    rueckgabe = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'vorschlag_zurueckgegeben'][-1]
    assert rueckgabe['grund'] == 'gruppe_2' and rueckgabe['beschluss'] == beschluss.pk
    pruefung = Pruefung.objects.get(entwurf=entwurf)
    assert 'Probekind' not in pruefung.begruendung and f'Mitglied {ohne.pk}' not in pruefung.begruendung
    client.logout()
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'Petra Probekind' in seite and 'Die Vergabekriterien fehlen völlig.' in seite
    austreten(petra)
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'Probekind' not in seite and f'Ehemaliges Mitglied {petra.pk}' in seite
    assert 'Die Vergabekriterien fehlen völlig.' in seite


# --- GP-010: Der Austauschbeschluss schließt spätestens mit der Verfristung -------------------


def test_ein_austauschbeschluss_mit_mehrheit_verfristet_nicht(client, ordnung):  # noqa: F811
    """GP-010: Die Beschlussfrist (sieben Tage ab Anlegen) reichte über die Verfristung des
    Austauschantrags (Prüffrist ab Urteil) hinaus — schwieg ein einziges Ratsmitglied, verfristete der
    Antrag trotz 4 : 0. Jetzt endet der Beschluss spätestens mit der Verfristung und entscheidet zuerst."""
    from gremien.models import Anlass, GremienBeschluss

    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    rat = [korat] + [mitglied_anlegen(f'korat{i}') for i in range(4)]
    for mitglied in rat[1:]:
        rolle_geben(mitglied, Gremium.KOORDINATIONSRAT)
    pruefung = entwurf.pruefungen.get()
    tage = timedelta(days=antrag.policy().pruefung_tage)
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=timezone.now() - timedelta(days=1))  # Urteil gestern
    pruefung.refresh_from_db()
    client.force_login(korat)
    karte = client.get(reverse('gremien:koordination')).content.decode()
    assert f'{timezone.localtime(pruefung.erstellt_am + tage):%d.%m.%Y %H:%M}' in karte  # die maßgebliche Frist steht da
    client.post(
        reverse('gremien:koordination_beschluss'),
        {'anlass': 'austausch', 'pruefung': pruefung.pk, 'beschreibung': 'Die Zweifel wiegen schwer.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=antrag)
    assert beschluss.frist == pruefung.erstellt_am + tage
    for mitglied in rat[:4]:  # das fünfte Mitglied schweigt
        stimme(client, beschluss, mitglied, 'dafuer', 'Austauschen.')
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OFFEN
    # Zeitraffer: Urteil und Beschlussfrist rücken gemeinsam zurück — die Frist ist seit einer Stunde um.
    versatz = tage - timedelta(days=1) + timedelta(hours=1)
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=pruefung.erstellt_am - versatz)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=beschluss.frist - versatz)
    antrag.refresh_from_db()
    antrag.fortschreiben_bis_zum_stand()
    pruefung.refresh_from_db()
    beschluss.refresh_from_db()
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.STATTGEGEBEN
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and 'Ohne Wirkung' not in beschluss.umsetzungsvermerk
    assert all(not Rolle.objects.get(mitglied=m).aktiv for m in er)


def test_nach_der_verfristung_entsteht_kein_austauschbeschluss_mehr(client, ordnung):  # noqa: F811
    """GP-010, Kehrseite der Kappung: Ist die Frist schon um und nur noch nicht ausgewertet, entsteht kein
    Beschluss mit einer Frist in der Vergangenheit — der Antrag verfristet, und die Seite sagt es."""
    from gremien.models import Anlass, GremienBeschluss

    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    pruefung = entwurf.pruefungen.get()
    tage = antrag.policy().pruefung_tage
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=timezone.now() - timedelta(days=tage, hours=1))
    client.force_login(korat)
    antwort = client.post(
        reverse('gremien:koordination_beschluss'),
        {'anlass': 'austausch', 'pruefung': pruefung.pk, 'beschreibung': 'Zu spät.'},
        follow=True,
    )
    assert not GremienBeschluss.objects.filter(anlass=Anlass.AUSTAUSCH, antrag=antrag).exists()
    assert 'Frist für diesen Austauschantrag ist verstrichen' in antwort.content.decode()
    pruefung.refresh_from_db()
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.VERFRISTET


def test_ein_austauschbeschluss_ohne_ergebnis_zur_frist_verfristet(client, ordnung):  # noqa: F811
    """GP-010, Rückschritt der ersten Runde: Verfehlt der auf die Verfristung gekappte Beschluss das Quorum,
    blieb der Entwurf mit „ohne Ergebnis“ bei Gruppe 2, die einen neuen Prüfbeschluss mit frischer Frist
    bekam — Schweigen des Koordinationsrats verlängerte die Beratung. Jetzt verfristet der Antrag wie zuvor
    und der Vorschlag geht an die Unterstützer (§ 5 Abs 12: Untätigkeit hemmt nie)."""
    from gremien.models import Anlass, GremienBeschluss

    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    rat = [korat] + [mitglied_anlegen(f'korat{i}') for i in range(4)]
    for mitglied in rat[1:]:
        rolle_geben(mitglied, Gremium.KOORDINATIONSRAT)
    pruefung = entwurf.pruefungen.get()
    tage = timedelta(days=antrag.policy().pruefung_tage)
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=timezone.now() - timedelta(days=1))  # Urteil gestern
    pruefung.refresh_from_db()
    client.force_login(korat)
    client.post(
        reverse('gremien:koordination_beschluss'),
        {'anlass': 'austausch', 'pruefung': pruefung.pk, 'beschreibung': 'Prüfen wir.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=antrag)
    assert beschluss.frist == pruefung.austausch_frist  # gekappt auf die Verfristung
    stimme(client, beschluss, korat, 'dafuer', 'Austauschen.')  # eine von fünf Stimmen: Quorum verfehlt
    # Zeitraffer: Urteil und Beschlussfrist rücken gemeinsam zurück — die Frist ist seit einer Stunde um.
    versatz = tage - timedelta(days=1) + timedelta(hours=1)
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=pruefung.erstellt_am - versatz)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=beschluss.frist - versatz)
    antrag.refresh_from_db()
    antrag.fortschreiben_bis_zum_stand()
    pruefung.refresh_from_db()
    beschluss.refresh_from_db()
    entwurf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    assert 'verfristet' in beschluss.umsetzungsvermerk and 'bleibt bei Gruppe 2' not in beschluss.umsetzungsvermerk
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.VERFRISTET
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    # Die Unterstützerfrist läuft ab der Verfristung, nicht ab dem Aufruf …
    assert entwurf.review_frist == pruefung.austausch_frist + timedelta(days=antrag.policy().review_tage)
    # … Gruppe 2 bekommt keinen zweiten Prüfbeschluss mit frischer Frist …
    assert entwurf.beschluesse.filter(gremium=Gremium.EXPERTENRAT_2).count() == 1
    assert all(Rolle.objects.get(mitglied=m).aktiv for m in er)
    # … und das Audit nennt die Verfristung, keinen Entscheid des Rates.
    typen = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get('antrag') == antrag.pk]
    assert any(e['typ'] == 'pruefung_frist_verstrichen' and e['grund'] == 'austausch_ohne_entscheid' for e in typen)
    assert not any(e['typ'] == 'austausch_entschieden' for e in typen)


def test_ein_von_der_gremienseite_geschlossener_austauschbeschluss_ohne_ergebnis_verfristet_ebenso(client, ordnung):  # noqa: F811
    """GP-010: Auch wenn nicht der Antrag, sondern der Sammellauf der Gremienseiten den Beschluss zur Frist
    schließt, bleibt der Entscheid leer — die nächste Fortschreibung des Antrags verfristet ihn."""
    from gremien.models import Anlass, GremienBeschluss

    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    zweite = mitglied_anlegen('koordinator2')
    rolle_geben(zweite, Gremium.KOORDINATIONSRAT)
    pruefung = entwurf.pruefungen.get()
    client.force_login(korat)
    client.post(
        reverse('gremien:koordination_beschluss'),
        {'anlass': 'austausch', 'pruefung': pruefung.pk, 'beschreibung': 'Prüfen wir.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=antrag)
    versatz = timedelta(days=antrag.policy().pruefung_tage, hours=1)
    Pruefung.objects.filter(pk=pruefung.pk).update(erstellt_am=pruefung.erstellt_am - versatz)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=beschluss.frist - versatz)
    assert GremienBeschluss.faellige_abschliessen() == 1
    pruefung.refresh_from_db()
    assert pruefung.korat_entscheid == ''
    antrag.refresh_from_db()
    antrag.fortschreiben_bis_zum_stand()
    pruefung.refresh_from_db()
    entwurf.refresh_from_db()
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.VERFRISTET
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
