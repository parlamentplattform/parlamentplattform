"""Der Integritätsrat (FB-I6, § 6 Abs 3) — Hervorhebung und Zurückweisung als Beschluss.

Bis 0.41 setzte niemand eine Hervorhebung: `Antrag.hervorgehoben` wurde an genau einer Stelle
geschrieben — in den Demodaten, mit dem Text „Beschluss IR-2026-03", einem Beschluss, den es nie
gegeben hat. § 5 Abs 10 lit b will es anders: „Die Hervorhebung beschließt der Integritätsrat
durch veröffentlichten, begründeten Beschluss; sie erfolgt niemals durch einen Algorithmus."
"""

import itertools

import pytest
from django.urls import reverse

from gremien.models import (
    SATZUNG_MIN_INTEGRITAETSRAT,
    Anlass,
    BeschlussStatus,
    GremienBeschluss,
    Gremium,
    Rolle,
)
from gremien.test_werkstatt import mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from plattform_core import Phase
from verfahren.models import AuditEintrag, antrag_einbringen

pytestmark = pytest.mark.django_db

_ZAEHLER = itertools.count()

ANTRAG = {
    "titel": "Nachtbusse im Halbstundentakt",
    "wortlaut": "Die Nachtbusse verkehren an Wochenenden im Halbstundentakt.",
    "begruendung": "Wer nachts arbeitet, kommt sonst nicht heim.",
}


def rat(anzahl=SATZUNG_MIN_INTEGRITAETSRAT):
    """Ein satzungsgemäß besetzter Integritätsrat (§ 6 Abs 3 lit a: drei bis sieben)."""
    leute = [mitglied_anlegen(f"ir{next(_ZAEHLER)}") for _ in range(anzahl)]
    for m in leute:
        rolle_geben(m, Gremium.INTEGRITAETSRAT)
    return leute


def antrag_anlegen(ordnung):  # noqa: F811
    return antrag_einbringen(mitglied_anlegen(f"stellerin{next(_ZAEHLER)}"), **ANTRAG, ordnung=ordnung)


def antrag_in_abstimmung(ordnung):  # noqa: F811
    """Ein Antrag, dessen Abstimmung seit zwei Tagen läuft — das, was sich aussetzen lässt (§ 6 Abs 3 lit d)."""
    from datetime import timedelta

    from django.utils import timezone

    antrag = antrag_anlegen(ordnung)
    antrag.phase = Phase.ABSTIMMUNG.value
    antrag.phase_beginn = timezone.now() - timedelta(days=2)
    antrag.save(update_fields=["phase", "phase_beginn"])
    return antrag


def beschluss_fassen(client, leute, antrag, anlass, grund="Wenig Beteiligung, große Wirkung."):
    """Anlegen und einstimmig beschließen — alle stimmen ab, damit sofort ausgewertet wird."""
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": anlass, "antrag": antrag.pk, "beschreibung": grund},
    )
    beschluss = GremienBeschluss.objects.filter(anlass=anlass, antrag=antrag).order_by("-pk").first()
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": "dafuer", "begruendung": "Einverstanden."},
        )
    beschluss.refresh_from_db()
    return beschluss


def test_mein_gremium_fuehrt_den_integritaetsrat_nicht_mehr_ins_leere(client):
    """Bis heute landete das Aufsichtsorgan auf der öffentlichen Besetzungsliste."""
    m = rat(1)[0]
    client.force_login(m)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:integritaet")


def test_nur_der_integritaetsrat_kommt_in_den_bereich(client, ordnung):  # noqa: F811
    fremd = mitglied_anlegen("fremde")
    rolle_geben(fremd, Gremium.KOORDINATIONSRAT)
    client.force_login(fremd)
    assert client.get(reverse("gremien:integritaet")).status_code == 403
    client.force_login(rat(1)[0])
    assert client.get(reverse("gremien:integritaet")).status_code == 200


def test_die_hervorhebung_entsteht_nur_aus_einem_beschluss(client, ordnung):  # noqa: F811
    """§ 5 Abs 10 lit b — mit veröffentlichter Begründung und der Nummer des Beschlusses."""
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    assert antrag.hervorgehoben is False
    beschluss = beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    antrag.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == "dafuer"
    assert antrag.hervorgehoben is True
    assert beschluss.nummer in antrag.hervorhebung_begruendung
    assert "Wenig Beteiligung" in antrag.hervorhebung_begruendung
    assert any(e.ereignis["typ"] == "hervorhebung_beschlossen" for e in AuditEintrag.objects.all())
    # Und der Beschluss ist für jeden nachlesbar (§ 6 Abs 9)
    client.logout()
    inhalt = client.get(reverse("gremien:beschluss", args=[beschluss.nummer])).content.decode()
    assert antrag.titel in inhalt


def test_ein_dagegen_hebt_nichts_hervor(client, ordnung):  # noqa: F811
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.HERVORHEBUNG, "antrag": antrag.pk, "beschreibung": "Vorschlag."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": "dagegen", "begruendung": "Der Antrag läuft ohnehin gut."},
        )
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.ergebnis == "dagegen" and antrag.hervorgehoben is False


def test_ein_unterbesetzter_rat_hebt_nichts_hervor(client, ordnung):  # noqa: F811
    """§ 6 Abs 3 lit a: drei bis sieben Mitglieder. Zwei sind kein Integritätsrat.

    Die Abstimmung selbst bleibt gültig — der Beschluss steht, mit dem Vermerk, warum er ohne
    Wirkung blieb. Ihn stillschweigend nicht anzuwenden wäre der schlechtere Weg: Dann stünde
    ein Beschluss da, der beschlossen aussieht und nichts bewirkt hat."""
    leute = rat(2)
    antrag = antrag_anlegen(ordnung)
    beschluss = beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    antrag.refresh_from_db()
    assert beschluss.ergebnis == "dafuer"
    assert antrag.hervorgehoben is False
    assert "nicht satzungsgemäß besetzt" in beschluss.umsetzungsvermerk


def test_zwei_menschen_mit_drei_rollen_sind_kein_rat(client, ordnung):  # noqa: F811
    """Befund #38: Der Nenner zählte Rollenzeilen. Zwei Personen mit drei Zeilen galten als
    satzungsgemäß besetzt (§ 6 Abs 3 lit a: drei bis sieben) — und hoben Anträge hervor."""
    from gremien.models import _integritaetsrat_beschlussfaehig, standard_ende

    leute = rat(2)
    Rolle.objects.create(mitglied=leute[0], gremium=Gremium.INTEGRITAETSRAT, endet_am=standard_ende(), bestaetigt=True)
    assert Rolle.aktive(Gremium.INTEGRITAETSRAT).count() == 3
    assert Rolle.personen(Rolle.aktive(Gremium.INTEGRITAETSRAT)) == 2
    antrag = antrag_anlegen(ordnung)
    beschluss = beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    assert _integritaetsrat_beschlussfaehig(beschluss) is False
    assert beschluss.aktive_rollen() == 2 and beschluss.auswertung().noetig == 1
    antrag.refresh_from_db()
    assert antrag.hervorgehoben is False and "nicht satzungsgemäß besetzt" in beschluss.umsetzungsvermerk
    client.force_login(leute[0])
    assert client.get(reverse("gremien:integritaet")).context["aktive"] == 2


def test_die_hervorhebung_laesst_sich_wieder_aufheben(client, ordnung):  # noqa: F811
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG_AUFHEBEN, "Die Beteiligung ist gestiegen.")
    antrag.refresh_from_db()
    assert antrag.hervorgehoben is False and antrag.hervorhebung_begruendung == ""


def test_die_zurueckweisung_stoppt_den_antrag_und_merkt_sich_den_stand(client, ordnung):  # noqa: F811
    """§ 5 Abs 2 — und der Weg zurück bleibt offen, weil die Zurückweisung bekämpfbar ist."""
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    vorher = antrag.phase
    beschluss = beschluss_fassen(
        client, leute, antrag, Anlass.ZURUECKWEISUNG, "Der Antrag verlangt Gesetzwidriges."
    )
    antrag.refresh_from_db()
    assert antrag.phase == Phase.ZURUECKGEWIESEN.value
    assert beschluss.nummer in antrag.zurueckweisung_begruendung
    assert beschluss.zustand_vorher["phase"] == vorher
    assert any(e.ereignis["typ"] == "antrag_zurueckgewiesen" for e in AuditEintrag.objects.all())


def test_ein_zurueckgewiesener_antrag_wandert_nicht_weiter(client, ordnung):  # noqa: F811
    """Ohne dieses Tor öffnete die Entwurfsschleife ihm noch eine Endabstimmung."""
    from gremien.models import Entwurf, EntwurfsFassung

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    antrag.phase = Phase.BERATUNG.value
    antrag.save(update_fields=["phase"])
    entwurf = Entwurf.objects.create(antrag=antrag)
    EntwurfsFassung.objects.create(
        entwurf=entwurf, nummer=1, wortlaut="Fassung", verfasst_von=leute[0]
    )
    beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, "Gesetzwidrig.")
    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    # Mit echtem Zeitstempel, damit der Test ohne das Tor wirklich durchliefe und die Phase
    # änderte — sonst bewiese er nur, dass None nicht rechnet.
    from django.utils import timezone

    entwurf._endabstimmung_oeffnen(antrag, "Versuch", timezone.now())
    antrag.refresh_from_db()
    assert antrag.phase == Phase.ZURUECKGEWIESEN.value


def test_die_aufhebung_gibt_dem_antrag_seine_restfrist(client, ordnung):  # noqa: F811
    """Der Antrag darf durch das Verfahren, das ihn zu Unrecht stoppte, keine Zeit verlieren."""
    from datetime import timedelta

    from django.utils import timezone

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    beginn_vorher = antrag.phase_beginn
    zurueck = beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, "Gesetzwidrig.")
    # Zeitraffer: Die Zurückweisung liegt zwei Tage zurück.
    zurueck.zustand_vorher["zurueckgewiesen_am"] = (
        timezone.now() - timedelta(days=2)
    ).isoformat()
    zurueck.save(update_fields=["zustand_vorher"])
    beschluss_fassen(
        client, leute, antrag, Anlass.ZURUECKWEISUNG_AUFHEBEN, "Das Schiedsgericht gab der Beschwerde statt."
    )
    antrag.refresh_from_db()
    assert antrag.phase != Phase.ZURUECKGEWIESEN.value
    assert antrag.zurueckweisung_begruendung == ""
    assert antrag.phase_beginn > beginn_vorher + timedelta(days=1)  # um die Hemmung verschoben


def test_zweimal_derselbe_beschluss_geht_nicht(client, ordnung):  # noqa: F811
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    client.force_login(leute[0])
    for _ in range(2):
        client.post(
            reverse("gremien:integritaet_beschluss"),
            {"anlass": Anlass.HERVORHEBUNG, "antrag": antrag.pk, "beschreibung": "Grund."},
        )
    assert GremienBeschluss.objects.filter(anlass=Anlass.HERVORHEBUNG, antrag=antrag).count() == 1


def test_ohne_begruendung_entsteht_kein_beschluss(client, ordnung):  # noqa: F811
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.HERVORHEBUNG, "antrag": antrag.pk, "beschreibung": "  "},
    )
    assert GremienBeschluss.objects.filter(antrag=antrag).count() == 0


def test_ein_fremder_anlass_wird_abgewiesen(client, ordnung):  # noqa: F811
    """Nur Anlässe mit gebauter Wirkung — sonst entstünde ein Beschluss, der nichts tut."""
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.PRUEFUNG, "antrag": antrag.pk, "beschreibung": "Grund."},
    )
    assert GremienBeschluss.objects.filter(antrag=antrag).count() == 0


def test_die_besetzung_steht_oeffentlich(client, ordnung):  # noqa: F811
    """§ 6 Abs 9: Wer im Aufsichtsorgan sitzt, ist keine interne Information."""
    leute = rat()
    inhalt = client.get(reverse("gremien:uebersicht")).content.decode()
    assert leute[0].anzeigename in inhalt
    assert Rolle.aktive(Gremium.INTEGRITAETSRAT).count() == SATZUNG_MIN_INTEGRITAETSRAT


def test_eine_hervorhebung_ohne_beschluss_wird_zurueckgenommen(client, ordnung):  # noqa: F811
    """Auf der laufenden Instanz stand „Beschluss IR-2026-03 vom 12.08.2026" an einem Antrag —
    eine Nummer ohne Beschluss, ein Datum ohne Sitzung.

    Nachträglich einen Beschluss zu erfinden, damit die Zahl stimmt, wäre auf einer Plattform,
    deren Zweck Nachprüfbarkeit ist, das Schlechteste. Also fällt die Hervorhebung."""
    from verfahren.management.commands.demo_seed import (
        hervorhebungen_ohne_beschluss_zuruecknehmen,
    )

    antrag = antrag_anlegen(ordnung)
    antrag.hervorgehoben = True
    antrag.hervorhebung_begruendung = "Beschluss IR-2026-03 vom 12.08.2026."
    antrag.save(update_fields=["hervorgehoben", "hervorhebung_begruendung"])
    assert hervorhebungen_ohne_beschluss_zuruecknehmen() == 1
    antrag.refresh_from_db()
    assert antrag.hervorgehoben is False and antrag.hervorhebung_begruendung == ""
    assert any(
        e.ereignis["typ"] == "hervorhebung_ohne_beschluss_zurueckgenommen"
        for e in AuditEintrag.objects.all()
    )


def test_eine_beschlossene_hervorhebung_bleibt(client, ordnung):  # noqa: F811
    """Der Wächter räumt nur auf, was ohne Deckung dasteht."""
    from verfahren.management.commands.demo_seed import (
        hervorhebungen_ohne_beschluss_zuruecknehmen,
    )

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    assert hervorhebungen_ohne_beschluss_zuruecknehmen() == 0
    antrag.refresh_from_db()
    assert antrag.hervorgehoben is True


def test_die_aussetzung_haelt_das_verfahren_an_und_endet_von_selbst(client, ordnung):  # noqa: F811
    """§ 6 Abs 3 lit d: „unterbleibt der Antrag, endet die Aussetzung von selbst."

    Solange sie wirkt, ruht das Verfahren vollständig — es wird nicht abgestimmt, und die Frist
    rückt nicht näher. Danach läuft der Antrag mit genau der Restzeit weiter, die er hatte."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    antrag.phase = Phase.ABSTIMMUNG.value
    antrag.phase_beginn = timezone.now() - timedelta(days=2)
    antrag.save(update_fields=["phase", "phase_beginn"])
    assert antrag.stimme_zulaessig() is True

    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Begründeter Verdacht auf Manipulation.")
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    assert aussetzung.gegenstand == Aussetzung.Gegenstand.ABSTIMMUNG
    assert aussetzung.laeuft() is True
    antrag.refresh_from_db()
    assert antrag.stimme_zulaessig() is False  # die Abstimmung ruht

    # Die Frist rückt nicht näher: Der wirksame Beginn wandert mit der Uhr.
    spaeter = timezone.now() + timedelta(days=3)
    verstrichen = spaeter - antrag.wirksamer_phase_beginn(spaeter)
    assert timedelta(days=2) <= verstrichen < timedelta(days=2, hours=1)

    # Ohne Antrag ans Schiedsgericht endet sie nach sieben Tagen von selbst.
    danach = aussetzung.frist + timedelta(minutes=1)
    assert aussetzung.laeuft(danach) is False
    antrag.fortschreiben(danach)
    aussetzung.refresh_from_db()
    assert aussetzung.beendet_am is not None
    assert "von selbst geendet" in aussetzung.beendet_grund


def test_der_vermerk_ans_schiedsgericht_haelt_die_aussetzung_am_leben(client, ordnung):  # noqa: F811
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Verdacht auf Manipulation.")
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_schiedsgericht", args=[aussetzung.pk]),
        {"kennung": "PSG-2026-004"},
    )
    aussetzung.refresh_from_db()
    assert aussetzung.schiedsgericht_kennung == "PSG-2026-004"
    assert aussetzung.laeuft(timezone.now() + timedelta(days=30)) is True


def test_die_aussetzung_laesst_sich_aufheben(client, ordnung):  # noqa: F811
    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Verdacht.")
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG_AUFHEBEN, "Der Verdacht hat sich nicht bestätigt.")
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    assert aussetzung.laeuft() is False and "Aufgehoben durch Beschluss" in aussetzung.beendet_grund


def test_aussetzen_geht_nur_bei_laufender_abstimmung_oder_vollzug(client, ordnung):  # noqa: F811
    """Befund #31: § 6 Abs 3 lit d erlaubt nur, „den Vollzug eines Beschlusses oder eine
    laufende Abstimmung“ auszusetzen. Bis 0.45 bekam ein Antrag in der Unterstützung das Etikett
    „Vollzug“ — und seine Sammelfrist rückte um sieben Tage. Jetzt weist schon das Anlegen ab,
    und die Wirkung prüft noch einmal, falls die Phase inzwischen gewechselt hat."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_anlegen(ordnung)  # in der Unterstützung
    client.force_login(leute[0])
    daten = {"anlass": Anlass.AUSSETZUNG, "antrag": antrag.pk, "beschreibung": "Verdacht."}
    client.post(reverse("gremien:integritaet_beschluss"), daten)
    antrag.phase = Phase.BERATUNG.value
    antrag.save(update_fields=["phase"])
    client.post(reverse("gremien:integritaet_beschluss"), daten)
    assert not GremienBeschluss.objects.filter(anlass=Anlass.AUSSETZUNG).exists()
    assert not Aussetzung.objects.exists()

    # In der Abstimmung lässt sich der Beschluss anlegen — wechselt die Phase vor der Auswertung,
    # bleibt er ohne Wirkung, statt einen abgelehnten Antrag mit „Vollzug“ zu etikettieren.
    antrag.phase = Phase.ABSTIMMUNG.value
    antrag.phase_beginn = timezone.now() - timedelta(days=2)
    antrag.save(update_fields=["phase", "phase_beginn"])
    client.post(reverse("gremien:integritaet_beschluss"), daten)
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSSETZUNG, antrag=antrag)
    antrag.phase = Phase.ABGELEHNT.value
    antrag.save(update_fields=["phase"])
    for m in leute:
        client.force_login(m)
        client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Ja."})
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN
    assert "Ohne Wirkung" in beschluss.umsetzungsvermerk and "§ 6 Abs 3 lit d" in beschluss.umsetzungsvermerk
    assert not Aussetzung.objects.filter(antrag=antrag).exists()


def test_der_ausgesetzte_vollzug_wird_nicht_fortgeschrieben(client, ordnung):  # noqa: F811
    """Befund #31, Gegenprobe: Eine Aussetzung des Vollzugs hinderte das Umsetzungsregister
    bisher nicht — die Verwaltung konnte am selben Tag „umgesetzt“ eintragen."""
    from gremien.models import Aussetzung
    from verfahren.models import VollzugAusgesetzt, vollzug_fortschreiben

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    antrag.phase = Phase.ANGENOMMEN.value
    antrag.save(update_fields=["phase"])
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Die Vergabe ist zweifelhaft.")
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    assert aussetzung.gegenstand == Aussetzung.Gegenstand.VOLLZUG and aussetzung.laeuft()
    with pytest.raises(VollzugAusgesetzt):
        vollzug_fortschreiben(antrag, leute[0], "in_umsetzung", "Trotzdem.")
    assert antrag.vollzug.count() == 0
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG_AUFHEBEN, "Geklärt.")
    vollzug_fortschreiben(antrag, leute[0], "in_umsetzung", "Jetzt schon.")
    assert antrag.vollzug.count() == 1


def test_zwei_aussetzungen_zum_selben_antrag_gehen_nicht(client, ordnung):  # noqa: F811
    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Erster Verdacht.")
    zweiter = beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Zweiter Verdacht.")
    assert Aussetzung.objects.filter(antrag=antrag).count() == 1
    assert "läuft bereits eine Aussetzung" in zweiter.umsetzungsvermerk


def test_die_regelpruefung_friert_das_verzeichnis_ein(client, ordnung):  # noqa: F811
    """§ 2 Abs 6: Der Vermerk „geprüft am …" ist ohne die geprüfte Liste wertlos."""
    from django.urls import reverse

    from gremien.models import Regelpruefung
    from plattform_core.regelwerk import verzeichnis

    leute = rat()
    client.force_login(leute[0])
    client.post(reverse("gremien:integritaet_regelpruefung"))
    pruefung = Regelpruefung.objects.get()
    assert len(pruefung.stand) == len(verzeichnis())
    assert pruefung.geprueft_am is None  # erst der Beschluss macht sie fertig
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[pruefung.beschluss.pk]),
            {"option": "geprueft", "begruendung": "Alle Regeln offengelegt und nachrechenbar."},
        )
    pruefung.refresh_from_db()
    assert pruefung.ergebnis == "geprueft" and pruefung.geprueft_am is not None
    assert any(
        e.ereignis["typ"] == "regelpruefung_abgeschlossen" for e in AuditEintrag.objects.all()
    )


def test_zweimal_pruefen_im_selben_jahr_geht_nicht(client, ordnung):  # noqa: F811
    from django.urls import reverse

    from gremien.models import Regelpruefung

    leute = rat()
    client.force_login(leute[0])
    for _ in range(2):
        client.post(reverse("gremien:integritaet_regelpruefung"))
    assert Regelpruefung.objects.count() == 1


def test_jede_abgelaufene_aussetzung_endet_in_ihrer_eigenen_transaktion(client, ordnung, monkeypatch):  # noqa: F811
    """Eine Transaktion für alle Aussetzungen rollte bei einer einzigen werfenden alle anderen mit
    zurück. Je Aussetzung eine kurze Transaktion: Wirft die zweite, bleibt die erste beendet."""
    from datetime import timedelta

    from django.utils import timezone

    import gremien.models as gm
    from gremien.models import Aussetzung, aussetzungen_fortschreiben

    leute = rat()
    for grund in ("Erster Verdacht.", "Zweiter Verdacht."):
        beschluss_fassen(client, leute, antrag_in_abstimmung(ordnung), Anlass.AUSSETZUNG, grund)
    zweite, erste = Aussetzung.objects.order_by("pk")
    Aussetzung.objects.filter(pk=zweite.pk).update(beginn=timezone.now() - timedelta(days=20))
    Aussetzung.objects.filter(pk=erste.pk).update(beginn=timezone.now() - timedelta(days=10))  # neuer — zuerst
    echte = gm._aussetzung_beenden

    def wirft_bei_der_zweiten(aussetzung, jetzt):
        if aussetzung.pk == zweite.pk:
            raise RuntimeError("Ende gescheitert")
        return echte(aussetzung, jetzt)

    monkeypatch.setattr(gm, "_aussetzung_beenden", wirft_bei_der_zweiten)
    with pytest.raises(RuntimeError):
        aussetzungen_fortschreiben()
    erste.refresh_from_db()
    zweite.refresh_from_db()
    assert erste.beendet_am is not None and "von selbst geendet" in erste.beendet_grund
    assert zweite.beendet_am is None


def test_eine_aussetzung_nach_fristablauf_beginnt_zur_frist(ordnung):  # noqa: F811
    """Der Beschluss schließt durch Fristablauf, ausgewertet erst später: Die Aussetzung beginnt zur
    Frist — an ihrem Beginn hängen die sieben Tage des § 6 Abs 3 lit d."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import Aussetzung, GremienBeschluss, GremienStimme

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    frist = timezone.now() - timedelta(hours=5)
    b = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.AUSSETZUNG,
        antrag=antrag,
        gegenstand="Aussetzung",
        beschreibung="Verdacht.",
        optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
        angelegt_von=leute[0],
        frist=frist,
    )
    for m in leute[:2]:  # die dritte schweigt — erst die Frist schließt
        GremienStimme.objects.create(beschluss=b, mitglied=m, option="dafuer", begruendung="ja")
    GremienBeschluss.faellige_abschliessen()
    b.refresh_from_db()
    assert b.ergebnis == "dafuer" and b.entschieden_am == frist
    assert Aussetzung.objects.get(antrag=antrag).beginn == frist


# --- GP-005: Entschiedene und beendete Anträge lassen sich nicht mehr zurückweisen ------------

BEENDET = ['angenommen', 'abgelehnt', 'verfallen', 'zurueckgezogen']


@pytest.mark.parametrize('phase', BEENDET)
def test_fuer_einen_beendeten_antrag_entsteht_kein_zurueckweisungsbeschluss(client, ordnung, phase):  # noqa: F811
    """GP-005: Der Rat konnte angenommene, abgelehnte und verfallene Anträge zurückweisen — der
    Beschluss der Mitgliederversammlung verschwand aus Parlament und Umsetzungsregister."""
    from verfahren.models import Antrag

    leute = rat()
    antrag = antrag_anlegen(ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(phase=phase)
    client.force_login(leute[0])
    antwort = client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.ZURUECKWEISUNG, 'antrag': antrag.pk, 'beschreibung': 'Formmangel.'},
        follow=True,
    )
    assert not GremienBeschluss.objects.filter(antrag=antrag).exists()
    meldungen = [str(m) for m in antwort.context['messages']]
    assert any('bereits entschieden oder beendet' in m for m in meldungen), meldungen
    antrag.refresh_from_db()
    assert antrag.phase == phase


@pytest.mark.parametrize('phase', BEENDET)
def test_ein_dennoch_entschiedener_beschluss_laesst_den_beendeten_antrag_stehen(client, ordnung, phase):  # noqa: F811
    """GP-005: Wird das Verfahren entschieden, während der Rat noch abstimmt, bleibt die spätere
    Zurückweisung ohne Wirkung — mit Vermerk am Beschluss, ohne Eingriff in Phase und Schleife."""
    from verfahren.models import Antrag

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    client.force_login(leute[0])
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.ZURUECKWEISUNG, 'antrag': antrag.pk, 'beschreibung': 'Formmangel.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.ZURUECKWEISUNG, antrag=antrag)
    beginn = antrag.phase_beginn
    Antrag.objects.filter(pk=antrag.pk).update(phase=phase)  # das Verfahren endet, bevor der Rat entscheidet
    for m in leute:
        client.force_login(m)
        client.post(
            reverse('gremien:beschluss_stimme', args=[beschluss.pk]),
            {'option': 'dafuer', 'begruendung': 'Einverstanden.'},
        )
    beschluss.refresh_from_db()
    antrag.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == 'dafuer'
    assert antrag.phase == phase and antrag.phase_beginn == beginn
    assert antrag.zurueckweisung_begruendung == ''
    assert beschluss.zustand_vorher is None
    assert 'Ohne Wirkung' in beschluss.umsetzungsvermerk and '§ 5 Abs 2' in beschluss.umsetzungsvermerk
    assert not any(e.ereignis['typ'] == 'antrag_zurueckgewiesen' for e in AuditEintrag.objects.all())


def test_ein_laufendes_verfahren_laesst_sich_weiter_zurueckweisen(client, ordnung):  # noqa: F811
    """Gegenprobe: Bis zu welcher laufenden Phase zurückgewiesen werden darf, bleibt, wie es war."""
    leute = rat()
    for antrag in (antrag_anlegen(ordnung), antrag_in_abstimmung(ordnung)):
        beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, 'Gesetzwidrig.')
        antrag.refresh_from_db()
        assert antrag.phase == Phase.ZURUECKGEWIESEN.value


# --- GP-008: Die Aufhebung einer Zurückweisung hat einen Weg und stellt die Schleife wieder her --

UEBERNAHME = 'wurde als neue Antragsfassung übernommen'


def _aufhebungsformular(html, antrag):
    """Das Formular der Karte „Zurückgewiesen“ für diesen Antrag — als (Adresse, Felder) oder None."""
    import re

    for formular in re.findall(r'<form[^>]*>.*?</form>', html, flags=re.S):
        felder = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', formular))
        if felder.get('anlass') == 'zurueckweisung_aufheben' and felder.get('antrag') == str(antrag.pk):
            assert re.search(r'<textarea[^>]*name="beschreibung"[^>]*required', formular)
            adresse = re.search(r'action="([^"]+)"', formular).group(1)
            return adresse, {k: v for k, v in felder.items() if k != 'csrfmiddlewaretoken'}
    return None


def _schleife_bei_den_unterstuetzern(client, ordnung):  # noqa: F811
    """Antrag in der Beratung, der Vorschlag liegt den Unterstützern vor; dazu ein offener Beschluss
    des Rates zum selben Antrag, den die Zurückweisung mitschließt."""
    from gremien.test_werkstatt import einreichen, werkstatt_lage

    leute = rat()
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    client.force_login(leute[0])
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.HERVORHEBUNG, 'antrag': antrag.pk, 'beschreibung': 'Große Wirkung.'},
    )
    offen = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    return leute, antrag, entwurf, offen


def test_die_zurueckweisung_schliesst_andere_beschluesse_mit_vermerk_und_audit(client, ordnung):  # noqa: F811
    """GP-008: Mitgeschlossene Beschlüsse standen öffentlich als „zu wenige Stimmen oder Gleichstand“
    da und fehlten in der Audit-Kette."""
    leute, antrag, entwurf, offen = _schleife_bei_den_unterstuetzern(client, ordnung)
    zurueck = beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, 'Gesetzwidrig.')
    offen.refresh_from_db()
    assert offen.status == BeschlussStatus.OHNE_ERGEBNIS
    assert zurueck.nummer in offen.umsetzungsvermerk and 'zurückgewiesen' in offen.umsetzungsvermerk
    geschlossen = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'gremienbeschluss_geschlossen']
    assert [(e['beschluss'], e['grund'], e['durch_beschluss']) for e in geschlossen] == [
        (offen.pk, 'zurueckweisung', zurueck.pk)
    ]
    # Die öffentliche Einzelseite und die Liste des Rates nennen den wirklichen Grund.
    client.logout()
    einzel = client.get(reverse('gremien:beschluss', args=[offen.nummer])).content.decode()
    assert zurueck.nummer in einzel and 'Zu wenige Stimmen oder Gleichstand' not in einzel
    client.force_login(leute[0])
    bereich = client.get(reverse('gremien:integritaet')).content.decode()
    assert 'Ohne Ergebnis: zu wenige Stimmen oder Gleichstand' not in bereich


def test_die_aufhebung_ist_ueber_die_seite_anlegbar_und_stellt_die_schleife_wieder_her(client, ordnung):  # noqa: F811
    """GP-008 (GB-04): Die Karte versprach „hebt der Rat sie hier auf“ und bot nichts an. Nach einer
    Aufhebung blieb die Schleife stillgelegt: abgestimmt wurde über den Urtext, während die
    Antragsseite die Übernahme des Vorschlags behauptete."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import EntwurfsStatus
    from gremien.test_werkstatt import frist_verstreichen
    from verfahren import chat

    leute, antrag, entwurf, offen = _schleife_bei_den_unterstuetzern(client, ordnung)
    frist_vorher = entwurf.review_frist
    zurueck = beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, 'Gesetzwidrig.')
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.ANGENOMMEN and entwurf.review_frist is None  # die Schleife ruht
    antragsseite = reverse('verfahren:antrag', args=[antrag.pk])
    assert UEBERNAHME not in client.get(antragsseite).content.decode()
    # Zeitraffer: Die Zurückweisung liegt zwei Tage zurück.
    zurueck.zustand_vorher['zurueckgewiesen_am'] = (timezone.now() - timedelta(days=2)).isoformat()
    zurueck.save(update_fields=['zustand_vorher'])

    client.force_login(leute[0])
    bereich = client.get(reverse('gremien:integritaet')).content.decode()
    formular = _aufhebungsformular(bereich, antrag)
    assert formular is not None, 'die Karte „Zurückgewiesen“ bietet die Aufhebung an'
    adresse, felder = formular
    client.post(adresse, {**felder, 'beschreibung': 'Das Schiedsgericht gab der Beschwerde statt.'})
    aufhebung = GremienBeschluss.objects.get(anlass=Anlass.ZURUECKWEISUNG_AUFHEBEN, antrag=antrag)
    # Solange der Beschluss läuft, zeigt die Karte ihn statt eines zweiten Formulars.
    bereich = client.get(reverse('gremien:integritaet')).content.decode()
    assert _aufhebungsformular(bereich, antrag) is None and aufhebung.nummer in bereich
    for m in leute:
        client.force_login(m)
        client.post(
            reverse('gremien:beschluss_stimme', args=[aufhebung.pk]),
            {'option': 'dafuer', 'begruendung': 'Einverstanden.'},
        )

    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    assert antrag.phase == Phase.BERATUNG.value
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    verschoben = entwurf.review_frist - frist_vorher  # um die Dauer der Zurückweisung
    assert timedelta(days=2) <= verschoben < timedelta(days=2, minutes=1)
    assert chat.abstimmungschat(antrag) is not None
    assert UEBERNAHME not in client.get(antragsseite).content.decode()
    aufgehoben = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'zurueckweisung_aufgehoben'][-1]
    assert aufgehoben['entwurf_wiederhergestellt'] == 'unterstuetzer'
    # Und der Vorschlag kommt wirklich zur Abstimmung: Nach der Frist ist er die neue Antragsfassung.
    frist_verstreichen(entwurf)
    antrag.fortschreiben_bis_zum_stand()
    antrag.refresh_from_db()
    assert antrag.phase == Phase.ABSTIMMUNG.value and antrag.fassungen.count() == 2
    assert UEBERNAHME in client.get(antragsseite).content.decode()


def test_die_aufhebung_einer_frueheren_zurueckweisung_laesst_die_schleife_ruhen_und_sagt_es(client, ordnung):  # noqa: F811
    """Bestand: Eine Zurückweisung aus der Zeit vor GP-008 hat den Stand der Schleife nicht gesichert.
    Ihre Aufhebung stellt nichts her, was nicht überliefert ist — die Antragsseite behauptet dann aber
    keine Übernahme mehr."""
    leute, antrag, entwurf, offen = _schleife_bei_den_unterstuetzern(client, ordnung)
    zurueck = beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG, 'Gesetzwidrig.')
    zurueck.zustand_vorher.pop('entwurf', None)
    zurueck.save(update_fields=['zustand_vorher'])
    beschluss_fassen(client, leute, antrag, Anlass.ZURUECKWEISUNG_AUFHEBEN, 'Stattgegeben.')
    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    assert antrag.phase == Phase.BERATUNG.value and entwurf.status == 'angenommen'
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert UEBERNAHME not in seite and 'Die Entwurfsschleife ruht' in seite


# --- GP-012: Der Beendigungsgrund einer Rolle ist nicht öffentlich ---------------------------


def test_der_beendigungsgrund_einer_rolle_steht_auf_keiner_oeffentlichen_seite(client, ordnung):  # noqa: F811
    """GP-012: Im Audit ist der Grund geschwärzt — der Jahresbericht zeigte ihn im Klartext neben dem
    Namen, und /gremien/ versprach „mit Grund dokumentiert“. Den Grund sieht nur die Verwaltung."""
    from django.utils import timezone

    admin = mitglied_anlegen('admin')
    admin.ist_admin = True
    admin.save()
    leute = rat()
    rolle = Rolle.objects.get(mitglied=leute[0], gremium=Gremium.INTEGRITAETSRAT)
    client.force_login(admin)
    client.post(reverse('gremien:rollen_aktion'), {'aktion': 'beenden', 'rolle': rolle.pk, 'grund': 'Geheimwort-123'})
    rolle.refresh_from_db()
    assert rolle.beendet_grund == 'Geheimwort-123'
    assert 'Geheimwort-123' in client.get(reverse('gremien:rollen')).content.decode()
    client.logout()
    bericht = client.get(reverse('gremien:integritaet_bericht', args=[timezone.localdate().year])).content.decode()
    assert 'Geheimwort-123' not in bericht and 'vorzeitig beendet' in bericht
    uebersicht = client.get(reverse('gremien:uebersicht')).content.decode()
    assert 'Geheimwort-123' not in uebersicht
    assert 'mit Grund dokumentiert' not in uebersicht and 'der Grund ist nicht öffentlich' in uebersicht
    for pfad in ('/audit/', '/audit.json'):
        assert 'Geheimwort-123' not in client.get(pfad).content.decode()


# --- GP-033: Eine Regelprüfung ohne Ergebnis blockiert sich nicht selbst ----------------------


def test_eine_regelpruefung_ohne_ergebnis_laesst_sich_im_selben_jahr_wiederholen(client, ordnung):  # noqa: F811
    """GP-033: Lief die Frist ohne Stimmen ab, zeigte die Karte weiter „läuft“, der Knopf blieb verborgen
    und ein neuer Versuch wurde abgewiesen — die Pflicht nach § 2 Abs 6 war über die Oberfläche unerfüllbar."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import BeschlussStatus, GremienBeschluss, Regelpruefung

    leute = rat()
    client.force_login(leute[0])
    client.post(reverse('gremien:integritaet_regelpruefung'))
    erste = Regelpruefung.objects.get()
    GremienBeschluss.objects.filter(pk=erste.beschluss_id).update(frist=timezone.now() - timedelta(hours=1))
    seite = client.get(reverse('gremien:integritaet')).content.decode()
    erste.beschluss.refresh_from_db()
    assert erste.beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    assert 'läuft — der Rat stimmt ab' not in seite and 'ohne Ergebnis' in seite
    assert f'Prüfung {timezone.localdate().year} anlegen' in seite  # der Knopf ist wieder da
    bericht = client.get(reverse('gremien:integritaet_bericht', args=[timezone.localdate().year])).content.decode()
    assert erste.beschluss.nummer in bericht and 'ohne Ergebnis' in bericht
    client.post(reverse('gremien:integritaet_regelpruefung'))
    assert Regelpruefung.objects.count() == 2  # die zweite desselben Jahres — die erste bleibt stehen
    seite = client.get(reverse('gremien:integritaet')).content.decode()
    assert erste.beschluss.nummer in seite and 'läuft — der Rat stimmt ab' in seite
    client.post(reverse('gremien:integritaet_regelpruefung'))
    assert Regelpruefung.objects.count() == 2  # solange eine läuft, entsteht keine dritte
