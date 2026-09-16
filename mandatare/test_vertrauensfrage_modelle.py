"""Die Modelle der Vertrauensfrage (§ 7 Abs 10, S10c): Sperrprüfung nach lit g, Anlass-Ausstände,
Stellungnahme (lit d), Vermerke des Rechenschaftsregisters, das Ende der Vertretung (lit f Z 8),
ruhende Gremienrollen — und dass nichts davon `Mandat.beendet` setzt."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from gremien.models import Gremium, Rolle, quoren_fuer
from gremien.test_werkstatt import rolle_geben
from mandatare import models as mm
from mandatare.models import (
    Aufgabe,
    Mandat,
    Stellungnahme,
    VertrauensfrageFehler,
    rueckgabezusage_vermerken,
    sperren_pruefen,
    stellungnahme_abgeben,
)
from mitglieder.models import Mitgliedsstatus
from plattform_core import Phase
from verfahren.models import Rueckgabezusage
from verfahren.test_vertrauensfrage import (  # noqa: F401
    _verloren,
    abweichung,
    altmandat,
    audit,
    einbringen,
    tage,
)
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


# ── Sperren (lit g) ────────────────────────────────────────────────────────────────────────


def test_keine_sperre_bei_einem_alten_mandat(altmandat):  # noqa: F811
    assert sperren_pruefen(altmandat) == ""


def test_schonfrist_rechnet_fuer_altmandate_ab_dem_inkrafttreten(monkeypatch):
    monkeypatch.setattr(mm, "INKRAFTTRETEN_ABS_10", date(2026, 9, 15))
    alt = Mandat.objects.create(mitglied=mitglied_anlegen("alt"), bezeichnung="Landtag", ebene="land", angetreten=date(2024, 1, 1))
    hinweis = sperren_pruefen(alt, timezone.make_aware(timezone.datetime(2026, 10, 1, 12)))
    assert "Schonfrist" in hinweis and "14.12.2026" in hinweis and "lit j" in hinweis
    assert sperren_pruefen(alt, timezone.make_aware(timezone.datetime(2026, 12, 14, 12))) == ""
    neu = Mandat.objects.create(mitglied=mitglied_anlegen("neu"), bezeichnung="Landtag", ebene="land", angetreten=date(2026, 11, 1))
    hinweis = sperren_pruefen(neu, timezone.make_aware(timezone.datetime(2026, 12, 20, 12)))
    assert "Schonfrist" in hinweis and "30.01.2027" in hinweis and "lit j" not in hinweis


def test_vierter_fall_mandat_mitgliedschaft_oder_vertretung_beendet(altmandat):  # noqa: F811
    altmandat.beendet = date(2026, 9, 1)
    assert "geendet (lit g vierter Fall)" in sperren_pruefen(altmandat)
    altmandat.beendet = None
    altmandat.vertretung_beendet_am = date(2026, 9, 1)
    assert "nicht mehr Mandatsträger" in sperren_pruefen(altmandat)
    altmandat.vertretung_beendet_am = None
    altmandat.mitglied.status = Mitgliedsstatus.AUSGETRETEN
    assert "Mitgliedschaft" in sperren_pruefen(altmandat)


def test_zweiter_und_dritter_fall(ordnung, altmandat):  # noqa: F811
    t0 = timezone.now()
    laufend = einbringen(mitglied_anlegen("anna"), altmandat, ordnung, jetzt=t0)
    hinweis = sperren_pruefen(altmandat, t0 + tage(1))
    assert f"Antrag #{laufend.pk}" in hinweis and "zweiter Fall" in hinweis
    laufend.phase = Phase.ABGELEHNT.value  # gewonnen — sperrt trotzdem sechs Monate (dritter Fall)
    laufend.phase_beginn = t0 + tage(20)
    laufend.save(update_fields=["phase", "phase_beginn"])
    hinweis = sperren_pruefen(altmandat, t0 + tage(30))
    assert "dritter Fall" in hinweis and "zweiter Fall" not in hinweis
    assert sperren_pruefen(altmandat, t0 + tage(20 + 190)) == ""


def test_anlass_ausstaende_nur_ueber_30_tage(altmandat):  # noqa: F811
    Aufgabe.objects.create(mandat=altmandat, titel="jung", frist=timezone.now() - tage(20), sitzungstag=True)
    assert altmandat.anlass_ausstaende() == []  # Frist um 13 Tage — noch kein Anlass
    Aufgabe.objects.create(mandat=altmandat, titel="alt", frist=timezone.now() - tage(60), sitzungstag=True)
    treffer = altmandat.anlass_ausstaende()
    assert {a["art"] for a in treffer} == {"rechenschaft", "sammelbericht"}
    assert all(a["tage"] > 30 and isinstance(a["seit"], date) and a["bezug"] for a in treffer)
    monate = [a for a in altmandat.anlass_ausstaende(date(2026, 12, 15)) if a["art"] == "monatsbericht"]
    assert monate and monate[0]["kennung"].startswith("monatsbericht:2026-10-01")


# ── Stellungnahme (lit d) ──────────────────────────────────────────────────────────────────


def test_stellungnahme_nur_vom_betroffenen_nur_laufend_und_nie_geaendert(ordnung, altmandat):  # noqa: F811
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    vf = antrag.vertrauensfrage
    with pytest.raises(VertrauensfrageFehler, match="betroffene"):
        stellungnahme_abgeben(vf, mitglied_anlegen("fremd"), "Ich finde das falsch.")
    with pytest.raises(VertrauensfrageFehler, match="Text"):
        stellungnahme_abgeben(vf, altmandat.mitglied, "   ")
    erste = stellungnahme_abgeben(vf, altmandat.mitglied, "Ich habe so gestimmt, weil …")
    zweite = stellungnahme_abgeben(vf, altmandat.mitglied, "Ergänzung.")
    assert list(vf.stellungnahmen.all()) == [erste, zweite]
    assert Stellungnahme.objects.count() == 2 and audit("vertrauensfrage_stellungnahme").__len__() == 2
    antrag.phase = Phase.ABGELEHNT.value
    antrag.save(update_fields=["phase"])
    vf.refresh_from_db()
    with pytest.raises(VertrauensfrageFehler, match="beendet"):
        stellungnahme_abgeben(vf, altmandat.mitglied, "Zu spät.")
    # Die Phase ist lazy: Auch ohne vorherigen Aufruf von `fortschreiben` endet das Gehör mit dem
    # Fristende der Abstimmung (lit d „bis zum Ende der Abstimmung“), nicht mit dem nächsten Seitenaufruf.
    antrag.phase = Phase.ABSTIMMUNG.value
    antrag.phase_beginn = timezone.now() - timedelta(days=antrag.policy().abstimmung_tage + 1)
    antrag.save(update_fields=["phase", "phase_beginn"])
    vf.refresh_from_db()
    with pytest.raises(VertrauensfrageFehler, match="beendet"):
        stellungnahme_abgeben(vf, altmandat.mitglied, "Auch zu spät.")


# ── Vermerke und Zustände ──────────────────────────────────────────────────────────────────


def test_rueckgabe_vermerk_ist_ein_sachverhalt_ohne_wertung(altmandat):  # noqa: F811
    assert altmandat.rueckgabe_vermerk == ""
    altmandat.vertrauen_entzogen_am = timezone.now() - tage(40)
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() + tage(1)
    assert altmandat.rueckgabe_vermerk == ""  # Frist läuft
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() - tage(1)
    assert altmandat.rueckgabe_vermerk == "keine Rückgabezusage abgegeben"
    altmandat.rueckgabezusage = Rueckgabezusage.ABGEGEBEN
    assert altmandat.rueckgabe_vermerk == "Rückgabezusage nicht eingehalten"
    altmandat.beendet = date(2026, 10, 3)
    # neutral „beendet“, nicht „zurückgelegt“: ob das Ende dem Ersuchen folgte, weiß die Plattform nicht (B3)
    assert altmandat.rueckgabe_vermerk == "Mandat beendet am 03.10.2026"


def test_rueckgabe_vermerk_liest_die_zusage_aus_der_bewerbung(ordnung, altmandat):  # noqa: F811
    """Register, Seite und JSON lesen dieselbe Quelle: Trägt die Verwaltung keine Zusage am Mandat ein,
    gilt die öffentliche Erklärung aus der Bewerbung (§ 7 Abs 3) — der Vermerk nach Fristablauf darf
    nicht „keine Rückgabezusage abgegeben“ sagen, wo die Bewerbung eine trägt."""
    from verfahren.models import Antragsart, Bewerbung, antrag_einbringen
    from verfahren.test_vertrauensfrage import ANTRAG

    kandidatur = antrag_einbringen(mitglied_anlegen("k"), **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(
        antrag=kandidatur, mitglied=altmandat.mitglied, vorstellung="Ich trete an.", rueckgabezusage="abgegeben"
    )
    altmandat.kandidatur = kandidatur
    altmandat.save(update_fields=["kandidatur"])
    assert altmandat.rueckgabezusage_wirksam() == ("abgegeben", "bewerbung")
    altmandat.vertrauen_entzogen_am = timezone.now() - tage(40)
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() - tage(1)
    assert altmandat.rueckgabe_vermerk == "Rückgabezusage nicht eingehalten"
    altmandat.rueckgabezusage = Rueckgabezusage.NICHT_ABGEGEBEN  # der Vermerk am Mandat geht vor
    assert altmandat.rueckgabezusage_wirksam() == ("nicht_abgegeben", "mandat")
    assert altmandat.rueckgabe_vermerk == "keine Rückgabezusage abgegeben"


def test_ein_widerruf_der_rueckgabezusage_geht_der_bewerbung_vor(ordnung, altmandat):  # noqa: F811
    """§ 7 Abs 3: Nichtabgabe, Widerruf und Nichteinhaltung sind drei Sachverhalte. Der Widerruf setzt
    den Vermerk am Mandat auf „keine Angabe“ zurück — nur das Datum zeigt ihn. Fiele die Rechnung dann
    auf die Bewerbung zurück, sagte das Register nach der Frist „nicht eingehalten“ über eine Person,
    die widerrufen hat (Befund B3)."""
    from verfahren.models import Antragsart, Bewerbung, antrag_einbringen
    from verfahren.test_vertrauensfrage import ANTRAG

    kandidatur = antrag_einbringen(mitglied_anlegen("k"), **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(
        antrag=kandidatur, mitglied=altmandat.mitglied, vorstellung="Ich trete an.", rueckgabezusage="abgegeben"
    )
    altmandat.kandidatur = kandidatur
    altmandat.save(update_fields=["kandidatur"])
    assert altmandat.rueckgabezusage_wirksam() == ("abgegeben", "bewerbung")
    rueckgabezusage_vermerken(altmandat, "")  # Widerruf: der Verwaltungsvermerk „keine Angabe“, datiert
    altmandat.refresh_from_db()
    assert altmandat.rueckgabezusage == "" and altmandat.rueckgabezusage_am == timezone.localdate()
    assert altmandat.rueckgabezusage_wirksam() == ("", "mandat")
    altmandat.vertrauen_entzogen_am = timezone.now() - tage(40)
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() - tage(1)
    assert "nicht eingehalten" not in altmandat.rueckgabe_vermerk
    assert altmandat.rueckgabe_vermerk == "keine Rückgabezusage abgegeben"
    # ohne jeden Vermerk am Mandat (kein Datum) gilt die Bewerbung weiter
    altmandat.rueckgabezusage_am = None
    assert altmandat.rueckgabezusage_wirksam() == ("abgegeben", "bewerbung")


def test_rueckgabezusage_nachtragen_und_widerrufen(altmandat):  # noqa: F811
    rueckgabezusage_vermerken(altmandat, "abgegeben")
    altmandat.refresh_from_db()
    assert altmandat.rueckgabezusage == "abgegeben" and altmandat.rueckgabezusage_am == timezone.localdate()
    rueckgabezusage_vermerken(altmandat, "nicht_abgegeben")
    altmandat.refresh_from_db()
    assert altmandat.rueckgabezusage == "nicht_abgegeben"
    assert [e["wert"] for e in audit("rueckgabezusage")] == ["abgegeben", "nicht_abgegeben"]
    with pytest.raises(ValueError):
        rueckgabezusage_vermerken(altmandat, "vielleicht")


def test_ende_der_vertretung_beendet_die_pflichten_nicht_aber_das_mandat(altmandat):  # noqa: F811
    Aufgabe.objects.create(mandat=altmandat, titel="vorher", frist=timezone.now() - tage(60), sitzungstag=True)
    Aufgabe.objects.create(mandat=altmandat, titel="nachher", frist=timezone.now() - tage(2), sitzungstag=True)
    assert len(altmandat.offene_pflichten()["rechenschaften"]) == 2
    altmandat.vertretung_beendet_am = timezone.localdate() - tage(30)
    altmandat.save()
    assert altmandat.beendet is None and not altmandat.aktiv and altmandat.pflichtende == altmandat.vertretung_beendet_am
    pflichten = altmandat.offene_pflichten()
    assert [p["aufgabe"].titel for p in pflichten["rechenschaften"]] == ["vorher"]  # danach nichts mehr geschuldet
    assert not altmandat.mitglied.ist_mandatar
    assert Mandat.zugaenglich_von(altmandat.mitglied).count() == 1  # der Bereich bleibt lesbar
    # Die Nachfrist läuft ab dem Ende der Pflichten — dieselbe Grenze wie `offene_pflichten`
    ende = altmandat.vertretung_beendet_am
    assert altmandat.nachfrist_bis == ende + tage(mm.NACHFRIST_TAGE)
    assert altmandat.in_nachfrist(ende + tage(mm.NACHFRIST_TAGE)) and not altmandat.in_nachfrist(ende + tage(mm.NACHFRIST_TAGE + 1))


def test_vertrauensfrage_eigenschaften(ordnung, altmandat):  # noqa: F811
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    vf = antrag.vertrauensfrage
    assert vf.laeuft and not vf.verloren and not vf.gewonnen and vf.ergebnis_wort == "" and vf.ergebnis_am is None
    assert vf.anfechtungsfrist_ende is None and vf.rueckgabefrist_ende is None and vf.endgueltig_ab() is None
    assert vf.rechtsschutz_stand == "" and not vf.nicht_eroeffnet
    assert "Vertrauensfrage zu Mandat" in str(vf)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    assert vf.ergebnis_am == ende and vf.anfechtungsfrist_ende == ende + tage(7)
    assert vf.rueckgabefrist_ende == ende + tage(30) and vf.endgueltig_ab() == ende + tage(7)
    assert not vf.laeuft


# ── Ruhende Gremienrollen ──────────────────────────────────────────────────────────────────


def test_eine_ruhende_rolle_zaehlt_nicht_bleibt_aber_lesbar():
    anna = mitglied_anlegen("anna")
    bert = mitglied_anlegen("bert")
    r1 = rolle_geben(anna, Gremium.INTEGRITAETSRAT)
    rolle_geben(bert, Gremium.INTEGRITAETSRAT)
    assert Rolle.aktive(Gremium.INTEGRITAETSRAT).count() == 2 and Rolle.hat(anna, Gremium.INTEGRITAETSRAT)
    r1.ruht_seit = timezone.now()
    r1.ruht_grund = mm.RUHENSGRUND
    r1.save()
    assert not r1.aktiv and r1.ruht
    assert Rolle.aktive(Gremium.INTEGRITAETSRAT).count() == 1
    assert not Rolle.hat(anna, Gremium.INTEGRITAETSRAT) and Rolle.hat(bert, Gremium.INTEGRITAETSRAT)
    assert Rolle.letzte(anna, Gremium.INTEGRITAETSRAT) == r1
    assert Rolle.aktive_von(anna).count() == 0 and Rolle.aktive_von(bert).count() == 1
    from gremien.models import GremienBeschluss

    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT, gegenstand="x", optionen=[{"wert": "dafuer", "name": "dafür"}], angelegt_von=bert
    )
    assert quoren_fuer([beschluss]) == {beschluss.pk: 1}
    assert beschluss.aktive_rollen() == 1
    r1.beendet_grund = "abberufen"
    r1.save()
    assert not r1.ruht  # beendet geht vor
