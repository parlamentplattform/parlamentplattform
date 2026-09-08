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
    antrag = antrag_anlegen(ordnung)
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
    antrag = antrag_anlegen(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, "Verdacht.")
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG_AUFHEBEN, "Der Verdacht hat sich nicht bestätigt.")
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    assert aussetzung.laeuft() is False and "Aufgehoben durch Beschluss" in aussetzung.beendet_grund


def test_zwei_aussetzungen_zum_selben_antrag_gehen_nicht(client, ordnung):  # noqa: F811
    from gremien.models import Aussetzung

    leute = rat()
    antrag = antrag_anlegen(ordnung)
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
