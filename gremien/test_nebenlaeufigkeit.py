"""Gremienbeschlüsse unter Nebenläufigkeit (FB-I4, § 5 Abs 12, Grundregel 7).

Ein Beschluss wird aus mehreren Richtungen geschlossen: vom Fristen-Wächter, von jeder
Gremienseite, von der Stimmabgabe und von der Antragsseite. Zwei Abläufe dürfen ihn nicht
zweimal schließen — sonst stünde seine Wirkung zweimal im Verfahren und die Auswertung zweimal
in der Audit-Kette. Die Zeilensperre wirkt nur auf PostgreSQL (SQLite serialisiert ohnehin);
darum laufen diese Tests nur dort — die CI fährt sie im Job `pruefen_postgres`.
"""

import threading
import time
from datetime import timedelta

import pytest
from django.db import connection, connections
from django.utils import timezone

# Das Einmal-Token-Modell liegt in `mitglieder.auth_flows`, nicht in `models.py`; ohne diesen
# Import kennt der Flush der transaktionalen Tests die Tabelle nicht und scheitert am Fremdschlüssel.
import mitglieder.auth_flows  # noqa: F401
from gremien.models import GremienBeschluss, Gremium
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Zeilensperren wirken nur auf PostgreSQL"),
]

OPTIONEN = [{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}]


def _beschluss(name):
    wer = mitglied_anlegen(name)
    return GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        gegenstand="Probe",
        optionen=OPTIONEN,
        angelegt_von=wer,
        frist=timezone.now() - timedelta(minutes=1),
    )


def _audit(pk):
    return sum(
        1
        for e in AuditEintrag.objects.all()
        if e.ereignis.get("typ") == "gremienbeschluss_ausgewertet" and e.ereignis.get("beschluss") == pk
    )


def _waechter_haelt_die_zeile(monkeypatch, wirkungen=None):
    """Startet `faellige_abschliessen` in einem eigenen Faden und hält ihn in der Wirkung an,
    solange die Zeile gesperrt ist. Gibt den Faden zurück, sobald die Sperre sicher steht."""
    import gremien.models as gm

    gesperrt = threading.Event()
    echte = gm.wirkung_anwenden

    def langsam(beschluss, jetzt=None):
        if wirkungen is not None:
            wirkungen.append(threading.current_thread().name)
        if threading.current_thread().name == "waechter":
            gesperrt.set()
            time.sleep(1.0)
        return echte(beschluss, jetzt)

    monkeypatch.setattr(gm, "wirkung_anwenden", langsam)

    def waechter():
        try:
            GremienBeschluss.faellige_abschliessen()
        finally:
            connections.close_all()

    faden = threading.Thread(target=waechter, name="waechter")
    faden.start()
    assert gesperrt.wait(5)
    return faden


def test_waechter_und_direkter_aufruf_schliessen_einmal(monkeypatch):
    """Der Wächter hält die Zeile; ein Seitenaufruf hat den Beschluss noch als offen gelesen."""
    b = _beschluss("anlegerin_nl_a")
    wirkungen = []
    faden = _waechter_haelt_die_zeile(monkeypatch, wirkungen)
    frisch = GremienBeschluss.objects.get(pk=b.pk)  # wie beschluss_oeffentlich / Entwurf.fortschreiben
    assert frisch.offen
    assert frisch.abschliessen() is False
    faden.join(10)
    assert wirkungen == ["waechter"]
    assert _audit(b.pk) == 1
    assert not frisch.offen


def test_zwei_seitenaufrufe_gleichzeitig_schliessen_einmal(monkeypatch):
    """Ohne Wächter: zwei Aufrufe der öffentlichen Beschlussseite zur selben Zeit (zwei Worker)."""
    import gremien.models as gm

    b = _beschluss("anlegerin_nl_b")
    b.refresh_from_db()
    wirkungen = []
    echte = gm.wirkung_anwenden
    schranke = threading.Barrier(2)

    def langsam(beschluss, jetzt=None):
        wirkungen.append(threading.current_thread().name)
        time.sleep(0.5)
        return echte(beschluss, jetzt)

    monkeypatch.setattr(gm, "wirkung_anwenden", langsam)
    status = {}

    def seite(name):
        from django.test import Client

        try:
            schranke.wait(5)
            status[name] = Client().get(f"/gremien/beschluss/{b.nummer}/").status_code
        except Exception as e:  # noqa: BLE001 — der Test berichtet jeden Fehler des Fadens
            status[name] = f"{type(e).__name__}: {e}"
        finally:
            connections.close_all()

    faeden = [threading.Thread(target=seite, args=(f"s{i}",), name=f"s{i}") for i in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(20)
    assert status == {"s0": 200, "s1": 200}
    assert len(wirkungen) == 1
    assert _audit(b.pk) == 1


def test_eine_aussetzung_wird_nicht_als_ohne_wirkung_vermerkt(monkeypatch):
    """Der zweite Lauf schrieb „Ohne Wirkung: … läuft bereits eine Aussetzung“ in den Vermerk
    genau des Beschlusses, der die Aussetzung ausgelöst hat (§ 6 Abs 3 lit d)."""
    from gremien.models import Anlass, Aussetzung, GremienStimme
    from gremien.test_integritaet import antrag_in_abstimmung, rat
    from verfahren.models import Verfahrensordnung
    from verfahren.test_views_aktionen import REGELN

    ordnung = Verfahrensordnung.objects.create(policy_id="nl-test", version=1, regeln=REGELN, aktiv=True)
    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    b = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.AUSSETZUNG,
        antrag=antrag,
        gegenstand="Aussetzung",
        beschreibung="Verdacht.",
        optionen=OPTIONEN,
        angelegt_von=leute[0],
        frist=timezone.now() - timedelta(minutes=1),
    )
    for m in leute:
        GremienStimme.objects.create(beschluss=b, mitglied=m, option="dafuer", begruendung="ja")
    faden = _waechter_haelt_die_zeile(monkeypatch)
    GremienBeschluss.objects.get(pk=b.pk).abschliessen()
    faden.join(10)
    b.refresh_from_db()
    assert b.ergebnis == "dafuer"
    assert Aussetzung.objects.filter(antrag=antrag).count() == 1
    assert "Ohne Wirkung" not in b.umsetzungsvermerk
    assert _audit(b.pk) == 1


def test_waechter_und_antragsseite_verklemmen_sich_nicht(monkeypatch):
    """Eine Transaktion für alle fälligen Beschlüsse hielt den Audit-Eintrag des ersten bis zum
    Ende offen. Eine Antragsseite, die gleichzeitig den Antrag des zweiten fortschreibt, wartete
    am Audit-Kopf auf den Wächter, der Wächter an der Antragszeile auf die Seite — PostgreSQL
    brach eine der beiden mit „deadlock detected“ ab. Die Haken verzögern nur."""
    import gremien.models as gm
    from gremien.models import Anlass, GremienStimme
    from gremien.test_integritaet import antrag_anlegen, rat
    from plattform_core import Phase
    from verfahren.models import Antrag, Verfahrensordnung
    from verfahren.test_views_aktionen import REGELN

    ordnung = Verfahrensordnung.objects.create(policy_id="nl-test", version=1, regeln=REGELN, aktiv=True)
    leute = rat()
    x = antrag_anlegen(ordnung)
    Antrag.objects.filter(pk=x.pk).update(
        phase=Phase.BERATUNG.value, phase_beginn=timezone.now() - timedelta(days=30)
    )
    _beschluss("anlegerin_nl_d")  # innere Angelegenheit, neuer — wird zuerst geschlossen
    b2 = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.HERVORHEBUNG,
        antrag=x,
        gegenstand="Hervorhebung",
        beschreibung="Wichtig.",
        optionen=OPTIONEN,
        angelegt_von=leute[0],
        frist=timezone.now() - timedelta(minutes=1),
    )
    GremienBeschluss.objects.filter(pk=b2.pk).update(angelegt_am=timezone.now() - timedelta(hours=1))
    for m in leute:
        GremienStimme.objects.create(beschluss=b2, mitglied=m, option="dafuer", begruendung="ja")

    seite_hat_x = threading.Event()
    echte_bf = gm._integritaetsrat_beschlussfaehig

    def beschlussfaehig(beschluss):
        if threading.current_thread().name == "waechter":
            seite_hat_x.wait(5)  # gleich danach speichert die Hervorhebung den Antrag
        return echte_bf(beschluss)

    monkeypatch.setattr(gm, "_integritaetsrat_beschlussfaehig", beschlussfaehig)
    echtes_archiv = Antrag.chat_archivieren

    def archivieren(self, jetzt=None):
        n = echtes_archiv(self, jetzt)
        if threading.current_thread().name == "seite":
            seite_hat_x.set()
            time.sleep(0.5)  # der Wächter wartet jetzt auf die Zeile des Antrags
        return n

    monkeypatch.setattr(Antrag, "chat_archivieren", archivieren)
    fehler = {}

    def waechter():
        try:
            GremienBeschluss.faellige_abschliessen()
        except Exception as e:  # noqa: BLE001 — der Test berichtet jeden Fehler des Fadens
            fehler["waechter"] = f"{type(e).__name__}: {str(e).splitlines()[0]}"
        finally:
            connections.close_all()

    def seite():
        try:
            time.sleep(0.4)  # der erste Beschluss samt Audit-Eintrag ist geschrieben
            Antrag.objects.get(pk=x.pk).fortschreiben_bis_zum_stand()
        except Exception as e:  # noqa: BLE001
            fehler["seite"] = f"{type(e).__name__}: {str(e).splitlines()[0]}"
        finally:
            connections.close_all()

    faeden = [threading.Thread(target=waechter, name="waechter"), threading.Thread(target=seite, name="seite")]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(30)
    x.refresh_from_db()
    assert fehler == {}
    assert x.hervorgehoben
