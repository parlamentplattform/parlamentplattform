"""Die Modelle der Vertrauensfrage (§ 7 Abs 10, S10c): Sperrprüfung nach lit g, Anlass-Ausstände,
Stellungnahme (lit d), Vermerke des Rechenschaftsregisters, das Ende der Vertretung (lit f Z 8),
ruhende Gremienrollen — und dass nichts davon `Mandat.beendet` setzt."""

from datetime import date, datetime, time, timedelta

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
from verfahren.models import Antrag, Rueckgabezusage
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


def test_die_sperrpruefung_rechnet_mit_dem_fortgeschriebenen_stand(ordnung, altmandat):  # noqa: F811
    """Befunde B17/B25: Ein Antrag verfällt mit der Sammelfrist (lit c) — ob jemand ihn danach aufruft oder
    nicht. Ohne Fortschreibung stand am Tag 40 „anhängig (zweiter Fall)“ im gespeicherten Sperrhinweis,
    obwohl der fünfte Fall zutrifft; auch über ein zweites Mandat derselben Person."""
    t0 = timezone.now()
    alter_anlass = abweichung(altmandat, eingetragen_am=t0 - tage(5))
    alt = einbringen(mitglied_anlegen("anna"), altmandat, ordnung, anlaesse=[alter_anlass], jetzt=t0)
    assert alt.phase == Phase.UNTERSTUETZUNG.value  # nie fortgeschrieben
    hinweis = sperren_pruefen(altmandat, t0 + tage(40), anlaesse=[alter_anlass])
    assert "fünfter Fall" in hinweis and "zweiter Fall" not in hinweis
    alt.refresh_from_db()
    assert alt.phase == Phase.VERFALLEN.value and alt.phase_beginn == t0 + tage(30)
    # mit einem Anlass nach der Einbringung des verfallenen Antrags: keine Sperre
    neu = abweichung(altmandat, gegenstand="Kanal", eingetragen_am=t0 + tage(35))
    assert sperren_pruefen(altmandat, t0 + tage(40), anlaesse=[neu]) == ""
    # zweites Mandat derselben Person: die laufende Vertrauensfrage zum ersten wird auch hier fortgeschrieben
    zweites = Mandat.objects.create(
        mitglied=altmandat.mitglied, bezeichnung="Landtag", ebene="land", gebiet="OÖ", angetreten=date(2025, 1, 1)
    )
    laufend = einbringen(mitglied_anlegen("bert"), altmandat, ordnung, anlaesse=[neu], jetzt=t0 + tage(41))
    assert "zweiter Fall" in sperren_pruefen(zweites, t0 + tage(50))
    assert "zweiter Fall" not in sperren_pruefen(zweites, t0 + tage(80), anlaesse=[neu])
    laufend.refresh_from_db()
    assert laufend.phase == Phase.VERFALLEN.value


def test_ein_liegengebliebener_bestaetigungsantrag_sperrt_den_naechsten_nicht(ordnung, altmandat):  # noqa: F811
    """Befund B25: Die Prüfung „Ein Bestätigungsantrag läuft bereits“ las die lazy Phase — ein an der
    Frist abgelaufener, nie aufgerufener Antrag hätte den nächsten für immer gesperrt."""
    from verfahren.models import vertrauensfrage_einbringen

    antrag, ende = _verloren(ordnung, altmandat)
    ich = altmandat.mitglied
    t1 = ende + tage(200)
    erster = vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1, art="bestaetigung")
    # niemand ruft ihn auf: Abstimmung ab Tag 7, Ende Tag 14 — gespeichert bleibt „unterstuetzung“
    assert erster.phase == Phase.UNTERSTUETZUNG.value
    t2 = t1 + tage(200)
    with pytest.raises(VertrauensfrageFehler, match="frühestens"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1 + tage(20), art="bestaetigung")
    zweiter = vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t2, art="bestaetigung")
    erster.refresh_from_db()
    assert erster.phase == Phase.ABGELEHNT.value  # ohne Stimmen: nicht bestätigt — fortgeschrieben, nicht „läuft“
    assert zweiter.phase == Phase.UNTERSTUETZUNG.value and zweiter.pk != erster.pk


def test_ein_liegengebliebener_angenommener_bestaetigungsantrag_hebt_die_sperre_vor_dem_tor_auf(ordnung, altmandat):  # noqa: F811
    """Kehrseite von B25: Wurde der liegengebliebene Bestätigungsantrag angenommen, hebt das Fortschreiben
    die Kandidatursperre auf (`Mandat.bestaetigen` auf einer anderen Instanz). Läse das Tor die Sperre
    vorher vom veralteten Objekt, entstünde ein zweiter Bestätigungsantrag zu einer schon bestätigten
    Person — jetzt liest es sie nach dem Fortschreiben aus der Datenbank."""
    from verfahren.models import stimme_abgeben, vertrauensfrage_einbringen

    antrag, ende = _verloren(ordnung, altmandat)
    ich = altmandat.mitglied
    t1 = ende + tage(200)
    erster = vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1, art="bestaetigung")
    erster.fortschreiben(t1 + tage(7))
    for m in [mitglied_anlegen(f"ja{i}") for i in range(3)] + [ich]:
        stimme_abgeben(erster, m, "ja", jetzt=t1 + tage(8))
    assert erster.phase == Phase.ABSTIMMUNG.value  # Abstimmung zu Ende (Tag 14), niemand hat fortgeschrieben
    assert altmandat.kandidatursperre
    with pytest.raises(VertrauensfrageFehler, match="keine verlorene Vertrauensfrage"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1 + tage(400), art="bestaetigung")
    assert mm.Vertrauensfrage.objects.filter(mandat=altmandat, art=mm.VertrauensfrageArt.BESTAETIGUNG).count() == 1
    # Die Fachoperation ist atomar: Mit dem Fehler rollt auch das Fortschreiben zurück — lazy, der nächste
    # Aufruf holt es nach; gespeichert ist nichts Halbes.
    erster.refresh_from_db()
    altmandat.refresh_from_db()
    assert erster.phase == Phase.ABSTIMMUNG.value and altmandat.bestaetigt_am is None
    assert erster.fortschreiben(t1 + tage(400)) is True
    altmandat.refresh_from_db()
    assert erster.phase == Phase.ANGENOMMEN.value and not altmandat.kandidatursperre


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
    # Widerruf auf „keine Angabe“ — datierter Vermerk der Verwaltung verdrängt die Bewerbung (E5)
    mm.rueckgabezusage_vermerken(altmandat, "")
    altmandat.refresh_from_db()
    altmandat.vertrauen_entzogen_am = timezone.now() - tage(40)
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() - tage(1)
    assert altmandat.rueckgabezusage_wirksam() == ("", "mandat")
    assert altmandat.rueckgabe_vermerk == "keine Rückgabezusage abgegeben"


def test_eine_aufgehobene_bestaetigung_stellt_die_kandidatursperre_wieder_her(ordnung, altmandat):  # noqa: F811
    """lit h: „die Wirkungen entfallen“ — auch die Aufhebung der Kandidatursperre durch einen angenommenen
    Bestätigungsantrag (lit f Z 3)."""
    antrag, ende = _verloren(ordnung, altmandat)
    altmandat.refresh_from_db()
    assert altmandat.kandidatursperre
    bestaetigung = einbringen(altmandat.mitglied, altmandat, ordnung, art="bestaetigung", jetzt=ende + tage(190))
    vf = bestaetigung.vertrauensfrage
    Antrag.objects.filter(pk=bestaetigung.pk).update(phase=Phase.ANGENOMMEN.value)  # angenommen …
    altmandat.bestaetigen("antrag", jetzt=ende + tage(200))  # … und die Sperre aufgehoben (lit f Z 3)
    assert not altmandat.kandidatursperre
    mm.vertrauensfrage_anfechtung_vermerken(vf, "PSG-2027-1", jetzt=ende + tage(201))
    mm.vertrauensfrage_entscheidung_vermerken(vf, "aufgehoben", jetzt=ende + tage(220))
    altmandat.refresh_from_db()
    assert altmandat.bestaetigt_am is None and altmandat.kandidatursperre
    assert altmandat.vertrauen_entzogen_am is not None  # die verlorene Vertrauensfrage bleibt, wie sie war
    eintrag = [e for e in audit("vertrauensfrage_aufgehoben") if e["antrag"] == bestaetigung.pk][0]
    assert eintrag["bestaetigung_entfallen"] is True and eintrag["rollen_wiederhergestellt"] == []


def test_rueckgabe_vermerk_fuer_rechnet_wie_die_property_ohne_eigene_abfrage(altmandat, django_assert_num_queries):  # noqa: F811
    """Befund B28: Listen reichen die gebündelt geladene Zusage durch — der Vermerk selbst fragt nichts ab."""
    altmandat.vertrauen_entzogen_am = timezone.now() - tage(40)
    altmandat.rueckgabe_ersucht_bis = timezone.localdate() - tage(1)
    with django_assert_num_queries(0):
        assert mm.rueckgabe_vermerk_fuer(altmandat, "abgegeben") == "Rückgabezusage nicht eingehalten"
        assert mm.rueckgabe_vermerk_fuer(altmandat, "") == "keine Rückgabezusage abgegeben"
        assert mm.rueckgabe_vermerk_fuer(altmandat, "", heute=altmandat.rueckgabe_ersucht_bis) == ""  # Frist läuft
    assert altmandat.rueckgabe_vermerk == mm.rueckgabe_vermerk_fuer(altmandat, altmandat.rueckgabezusage_wirksam()[0])


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
    assert vf.rueckgabefrist_tag() == altmandat.rueckgabe_ersucht_bis == timezone.localdate(ende) + tage(30)
    assert vf.rueckgabefrist_ende == timezone.make_aware(datetime.combine(vf.rueckgabefrist_tag() + tage(1), time.min))
    assert vf.endgueltig_ab() == ende + tage(7)
    assert not vf.laeuft


# ── Stufe 2: eine Frist, ein Kalendertag, je Vertrauensfrage atomar ────────────────────────


def _verlorene_vertrauensfrage(mandat, wirkungen_ab):
    """Eine verlorene Vertrauensfrage mit gestempelter Stufe 1 — direkt gesetzt, damit der Zeitpunkt
    des Ergebnisses frei wählbar ist (Zeitumstellung, Nachtstunden)."""
    from verfahren.models import Antrag, Antragsart

    antrag = Antrag.objects.create(
        titel="Vertrauensfrage: Gemeinderätin, Polsenz",
        art=Antragsart.VERTRAUENSFRAGE,
        eingebracht_von=mitglied_anlegen(f"steller{antrag_nr()}"),
        eingebracht_am=wirkungen_ab - tage(20),
        phase=Phase.ANGENOMMEN.value,
        phase_beginn=wirkungen_ab,
        policy_snapshot={},
    )
    vf = mm.Vertrauensfrage.objects.create(antrag=antrag, mandat=mandat, wirkungen_ab=wirkungen_ab)
    mandat.vertrauen_entzogen_am = wirkungen_ab
    mandat.rueckgabe_ersucht_bis = timezone.localdate(wirkungen_ab) + tage(mm.RUECKGABEFRIST_TAGE)
    mandat.save(update_fields=["vertrauen_entzogen_am", "rueckgabe_ersucht_bis"])
    return vf


_ANTRAG_NR = iter(range(1, 10_000))


def antrag_nr():
    return next(_ANTRAG_NR)


def wien(jahr, monat, tag, stunde=0, minute=0):
    return timezone.make_aware(datetime(jahr, monat, tag, stunde, minute))


@pytest.mark.parametrize(
    ("ergebnis", "fristtag"),
    [
        (wien(2026, 10, 24, 0, 30), date(2026, 11, 23)),  # vor der Zeitumstellung: UTC + 30 Tage läge am 22.11.
        (wien(2027, 3, 1, 23, 30), date(2027, 3, 31)),  # vor der Zeitumstellung im Frühjahr: UTC + 30 Tage läge am 1.4.
        (wien(2026, 10, 4, 14, 0), date(2026, 11, 3)),  # ohne Zeitumstellung: bisher endete die Vertretung um 13:00
    ],
)
def test_die_vertretung_endet_mit_ablauf_des_ausgewiesenen_fristtags(altmandat, ergebnis, fristtag):  # noqa: F811
    """§ 7 Abs 10 lit f Z 4, 5 und 8 knüpfen drei Wirkungen an eine Frist — die, die das Register als
    Kalendertag ausweist (`rueckgabe_ersucht_bis`, einschließlich). Stufe 2 rechnete bisher mit
    `wirkungen_ab + 30 Tage` in UTC und stempelte über die Zeitumstellung einen anderen Tag, im Normalfall
    schon zur Uhrzeit des Ergebnisses am letzten Fristtag (Befunde B10/B18/B24)."""
    vf = _verlorene_vertrauensfrage(altmandat, ergebnis)
    assert altmandat.rueckgabe_ersucht_bis == fristtag == vf.rueckgabefrist_tag()
    assert vf.rueckgabefrist_ende == wien(fristtag.year, fristtag.month, fristtag.day) + tage(1)
    # am Fristtag um 23:45 Wiener Zeit läuft die Frist noch — Vermerk leer, Vertretung besteht
    assert mm.vertrauensfragen_fortschreiben(wien(fristtag.year, fristtag.month, fristtag.day, 23, 45)) == 1  # nur (a)
    altmandat.refresh_from_db()
    assert altmandat.vertretung_beendet_am is None
    # der Folgetag um 00:01: Vertretung beendet, gestempelt mit dem Fristtag des Registers
    folgetag = fristtag + tage(1)
    assert mm.vertrauensfragen_fortschreiben(wien(folgetag.year, folgetag.month, folgetag.day, 0, 1)) == 1
    altmandat.refresh_from_db()
    assert altmandat.vertretung_beendet_am == fristtag == altmandat.rueckgabe_ersucht_bis
    assert audit("vertretung_beendet")[0]["ab"] == fristtag.isoformat()


def test_stufe_zwei_laeuft_je_vertrauensfrage_atomar(monkeypatch, ordnung, altmandat):  # noqa: F811
    """Befund B29: Bricht die Verarbeitung nach dem Stempel `wirkungen_endgueltig_am` und vor dem Ende
    der Rollen ab, blieb der Stempel stehen, der nächste Lauf übersprang den Block — die Rollen ruhten
    dauerhaft, das Audit fehlte. Jetzt wird je Vertrauensfrage alles oder nichts geschrieben."""
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    echte_save = Rolle.save
    aufrufe = []

    def bricht_ab(self, *args, **kwargs):
        aufrufe.append(self.pk)
        if len(aufrufe) == 1:
            raise RuntimeError("Verbindung abgerissen")
        return echte_save(self, *args, **kwargs)

    monkeypatch.setattr(Rolle, "save", bricht_ab)
    with pytest.raises(RuntimeError):
        mm.vertrauensfragen_fortschreiben(ende + tage(8))
    vf.refresh_from_db()
    rolle.refresh_from_db()
    assert vf.wirkungen_endgueltig_am is None and rolle.beendet_grund == "" and not audit("vertrauensfrage_endgueltig")
    assert mm.vertrauensfragen_fortschreiben(ende + tage(8)) == 1
    vf.refresh_from_db()
    rolle.refresh_from_db()
    assert vf.wirkungen_endgueltig_am == ende + tage(7) and rolle.beendet_grund == mm.BEENDIGUNGSGRUND
    assert len(audit("vertrauensfrage_endgueltig")) == 1


def test_stufe_zwei_laedt_nur_was_noch_etwas_zu_tun_hat(altmandat):  # noqa: F811
    """Befund B29: Bisher lud jeder Seitenaufruf alle jemals verlorenen Vertrauensfragen samt Mandat
    und Mitglied — auch die längst vollzogenen."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    t0 = timezone.now() - tage(100)
    for i in range(5):
        mandat = Mandat.objects.create(mitglied=mitglied_anlegen(f"v{i}"), bezeichnung="Gemeinderat", ebene="gemeinde")
        vf = _verlorene_vertrauensfrage(mandat, t0)
        vf.wirkungen_endgueltig_am = t0 + tage(7)
        vf.save(update_fields=["wirkungen_endgueltig_am"])
        mandat.vertretung_beendet_am = mandat.rueckgabe_ersucht_bis
        mandat.save(update_fields=["vertretung_beendet_am"])
    with CaptureQueriesContext(connection) as abfragen:
        assert mm.vertrauensfragen_fortschreiben() == 0
    assert len(abfragen) == 1, [a["sql"] for a in abfragen]
    # mit lit h und noch offener Mandatsvereinbarung wird die Vertrauensfrage weiter geladen — Schritt (c)
    mandat.mandatsvereinbarung_lit_h_am = date(2026, 9, 20)
    mandat.save(update_fields=["mandatsvereinbarung_lit_h_am"])
    assert mm.vertrauensfragen_fortschreiben() == 1
    mandat.refresh_from_db()
    assert mandat.mandatsvereinbarung_endet_am == mandat.rueckgabe_ersucht_bis
    assert mm.vertrauensfragen_fortschreiben() == 0


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
