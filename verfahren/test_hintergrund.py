"""Der Fristen-Wächter im Hintergrundfaden (D-J1a, Bestandsaufnahme 28.9.2026, A2) und das
Fortschreiben bis zum Stand: kein Antrag bleibt liegen, kein Lauf läuft doppelt."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Mitglied
from plattform_core import Phase
from verfahren import hintergrund
from verfahren.models import Antrag, Hintergrundlauf, Verfahrensordnung, antrag_einbringen

pytestmark = pytest.mark.django_db


@pytest.fixture
def liegengeblieben():
    """Ein Beratungs-Antrag ohne Entwurfsfenster, dessen Beratung und Abstimmung längst vorbei sind."""
    call_command("demo_seed", verbosity=0)
    ordnung = Verfahrensordnung.objects.get(aktiv=True)
    antrag = antrag_einbringen(Mitglied.objects.get(username="demo1"), "Liegengeblieben", "Wortlaut", "Grund", ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(
        phase=Phase.BERATUNG.value, phase_beginn=timezone.now() - timedelta(days=120)
    )
    return Antrag.objects.get(pk=antrag.pk)


def test_antragsseite_zeigt_einen_liegengebliebenen_antrag_sofort_am_ergebnis(client, liegengeblieben):
    client.get(reverse("verfahren:antrag", args=[liegengeblieben.pk]))
    liegengeblieben.refresh_from_db()
    assert liegengeblieben.phase in (Phase.ABGELEHNT.value, Phase.ANGENOMMEN.value)


def test_fortschreiben_bis_zum_stand_zaehlt_die_uebergaenge(liegengeblieben):
    assert liegengeblieben.fortschreiben_bis_zum_stand() == 2  # Beratung → Abstimmung → Ergebnis
    assert liegengeblieben.fortschreiben_bis_zum_stand() == 0


def test_waechter_schreibt_fristen_fort_und_haelt_rechenschaft(liegengeblieben):
    ausgefuehrt = hintergrund.faellige_ausfuehren()
    assert "fristen" in ausgefuehrt
    liegengeblieben.refresh_from_db()
    assert liegengeblieben.phase in (Phase.ABGELEHNT.value, Phase.ANGENOMMEN.value)
    lauf = Hintergrundlauf.objects.get(name="fristen")
    assert lauf.zuletzt_begonnen and lauf.zuletzt_beendet and lauf.sperrcode == "" and lauf.gesperrt_bis is None
    assert lauf.zuletzt_stand["phasenwechsel"] >= 2 and lauf.fehler == ""


def test_waechter_laeuft_erst_nach_dem_takt_wieder(settings):
    settings.DDOE_WAECHTER_MINUTEN = 10
    jetzt = timezone.now()
    # Neben dem Wächter läuft die Warteschlange der Zukunftswerkstatt (Takt 1 min) — hier zählt nur der Wächter.
    assert "fristen" in hintergrund.faellige_ausfuehren(jetzt)
    assert "fristen" not in hintergrund.faellige_ausfuehren(jetzt + timedelta(minutes=5))
    assert "fristen" in hintergrund.faellige_ausfuehren(jetzt + timedelta(minutes=10))


def test_reservierter_lauf_wird_nicht_zugleich_ausgefuehrt():
    jetzt = timezone.now()
    Hintergrundlauf.objects.create(name="fristen", gesperrt_bis=jetzt + timedelta(minutes=5), sperrcode="x" * 32)
    assert "fristen" not in hintergrund.faellige_ausfuehren(jetzt)
    # Nach Ablauf der Reservierung (Prozessverlust) übernimmt der nächste Worker.
    assert "fristen" in hintergrund.faellige_ausfuehren(jetzt + timedelta(minutes=6))


def test_fehler_im_lauf_stehen_in_der_zeile_und_toeten_den_faden_nicht():
    def kaputt():
        raise RuntimeError("Datenbank weg")

    lauf = hintergrund.Lauf("probe", lambda: 1, kaputt)
    assert hintergrund.ausfuehren(lauf) is True
    zeile = Hintergrundlauf.objects.get(name="probe")
    assert zeile.fehler.startswith("RuntimeError") and zeile.sperrcode == "" and zeile.zuletzt_beendet



OPTIONEN = [{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}]


def test_ein_kaputter_antrag_haelt_die_uebrigen_und_die_nachlaeufe_nicht_an(liegengeblieben):
    """Warf das Fortschreiben eines Antrags (hier ein eingefrorener Schnappschuss, den die Ordnung
    nicht mehr annimmt), brach der ganze Lauf ab — bei jedem Takt wieder: Anträge mit größerer
    Kennung und alle Nachläufe blieben liegen. Jetzt trifft der Fehler nur diesen Antrag."""
    from gremien.models import GremienBeschluss, Gremium

    kaputt = liegengeblieben  # die kleinere Kennung — kommt im Lauf zuerst
    Antrag.objects.filter(pk=kaputt.pk).update(policy_snapshot={**kaputt.policy_snapshot, "feld_aus_der_zukunft": 1})
    demo1 = Mitglied.objects.get(username="demo1")
    spaeter = antrag_einbringen(demo1, "Später", "Wortlaut", "Grund", Verfahrensordnung.objects.get(aktiv=True))
    Antrag.objects.filter(pk=spaeter.pk).update(
        phase=Phase.BERATUNG.value, phase_beginn=timezone.now() - timedelta(days=120)
    )
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        gegenstand="fällig",
        optionen=OPTIONEN,
        angelegt_von=demo1,
        frist=timezone.now() - timedelta(days=1),
    )
    for _takt in range(2):
        Hintergrundlauf.objects.update(zuletzt_begonnen=None)
        assert "fristen" in hintergrund.faellige_ausfuehren()
    spaeter.refresh_from_db()
    beschluss.refresh_from_db()
    kaputt.refresh_from_db()
    lauf = Hintergrundlauf.objects.get(name="fristen")
    assert spaeter.phase in (Phase.ABGELEHNT.value, Phase.ANGENOMMEN.value)
    assert not beschluss.offen
    assert kaputt.phase == Phase.BERATUNG.value
    assert lauf.zuletzt_stand["fehler"] == 1 and lauf.fehler == ""


def test_ein_werfender_nachlauf_haelt_die_folgenden_nicht_an(monkeypatch):
    """Warf ein Nachlauf (Beschlüsse), liefen Aussetzungen, Parametertests und Stufe 2 der
    Vertrauensfrage nicht mehr. Jetzt steht der Fehler in der Zählung, die übrigen laufen."""
    import gremien.models as gm
    import mandatare.models as mm
    from verfahren.management.commands.verfahren_fortschreiben import alles_fortschreiben

    def wirft(*args, **kwargs):
        raise RuntimeError("Nachlauf gescheitert")

    gelaufen = []
    monkeypatch.setattr(gm.GremienBeschluss, "faellige_abschliessen", classmethod(wirft))
    monkeypatch.setattr(gm, "aussetzungen_fortschreiben", lambda jetzt=None: gelaufen.append("aussetzungen") or 0)
    monkeypatch.setattr(gm, "parametertests_fortschreiben", lambda jetzt=None: gelaufen.append("tests") or 0)
    monkeypatch.setattr(mm, "vertrauensfragen_fortschreiben", lambda jetzt=None: gelaufen.append("vf") or 0)
    stand = alles_fortschreiben()
    assert gelaufen == ["aussetzungen", "tests", "vf"]
    assert stand["fehler"] == 1 and stand["beschluesse"] == 0
