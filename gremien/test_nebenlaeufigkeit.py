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


# --- Wächter und Antragsseite am selben Antrag (GP-004) ---------------------------------------
#
# Die Sperrreihenfolge, die diese beiden Tests festhalten — überall dieselbe, darum kein Kreis:
#
#   1. die Zeile des ANTRAGS   (`Antrag.fortschreiben`; `GremienBeschluss.abschliessen` bei einem
#                               Beschluss zu einem Antrag — seit 96fff65 vor allem anderen)
#   2. die Zeile des BESCHLUSSES (`abschliessen`; aus der Fortschreibung des Antrags heraus über
#                               `zur_frist_abschliessen` mit `skip_locked`, also ohne je zu warten)
#   3. der Kopf der Audit-Kette (jeder Eintrag; frei erst mit dem Ende der Transaktion)
#
# Antrag vor Beschluss, weil die Wirkung eines Beschlusses den Antrag schreibt und der Beschluss auf
# dem Stand des Antrags zu seiner Frist wirken muss: `abschliessen` schreibt den Antrag deshalb
# zuerst fort und braucht dafür dessen Zeile. Sperrte der Wächter wie früher vorab die Zeile des
# Beschlusses, hielte er den Beschluss und wartete auf den Antrag, während eine Gremienseite oder die
# letzte Stimme (ebenfalls `abschliessen`) den Antrag hält und auf den Beschluss wartet — ein Kreis.
# `faellige_abschliessen` sperrt die Zeile eines Beschlusses zu einem Antrag darum nicht mehr vorab.
#
# Wer auf die Zeile des Antrags WARTET, hält nichts: Sie ist die erste Sperre jeder der beiden
# Seiten, und der Wächter schließt jeden Beschluss in einer eigenen Transaktion (der Audit-Eintrag
# des vorigen ist dann schon festgeschrieben). Wer sie HÄLT, braucht danach nur noch Beschluss und
# Audit-Kopf — und die hält kein Wartender. Beide Richtungen sind unten hergestellt.
#
# Die Haken warten nicht auf Verdacht eine feste Zeit: Wer die Sperre hält, geht erst weiter, wenn
# die Gegenseite nachweislich an einer Sperre steht (`pg_locks`). Jeder Test verlangt am Ende, dass
# das beobachtet wurde — läuft ein Haken stattdessen in seine Zeitgrenze, ist der Test rot und
# besteht nicht durch bloßen Zeitablauf.


def _wartet_jemand_auf_eine_sperre(grenze=10.0):
    """Ob eine ANDERE Datenbankverbindung auf eine Sperre wartet — gefragt wird höchstens `grenze` Sekunden.

    Gelesen wird `pg_locks`, nicht `pg_stat_activity`: Dessen Momentaufnahme bleibt innerhalb einer
    Transaktion stehen, und der Aufrufer steckt mitten in einer. `pg_locks` liest die Sperrtabelle bei
    jeder Abfrage neu. Die Abfrage läuft auf der Verbindung des aufrufenden Fadens und sperrt nichts."""
    ende = time.monotonic() + grenze
    while time.monotonic() < ende:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted AND pid <> pg_backend_pid()")
            if cursor.fetchone()[0]:
                return True
        time.sleep(0.05)
    return False


def _antrag_mit_faelligem_beschluss():
    """Die Lage beider Tests: ein Antrag, dessen Beratung seit einer Stunde um ist und den noch niemand
    fortgeschrieben hat, und zwei fällige Beschlüsse — einer ohne Antrag (jünger angelegt, der Wächter
    schließt ihn zuerst und schreibt dabei ins Audit) und die beschlossene Hervorhebung des Antrags.

    Die Frist der Hervorhebung liegt NACH dem Beratungsende: Wer den Antrag fortschreibt, wendet zuerst
    den Übergang in die Abstimmung an (Phase, Chat-Archiv, Audit-Eintrag) und schließt dann den Beschluss.
    Rückgabe: der Antrag, der Beschluss ohne Antrag, der Beschluss zum Antrag."""
    from gremien.models import Anlass, GremienStimme
    from gremien.test_integritaet import antrag_anlegen, rat
    from plattform_core import Phase
    from verfahren.models import Antrag, Verfahrensordnung
    from verfahren.test_views_aktionen import REGELN

    ordnung = Verfahrensordnung.objects.create(policy_id="nl-test", version=1, regeln=REGELN, aktiv=True)
    leute = rat()
    antrag = antrag_anlegen(ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(
        phase=Phase.BERATUNG.value,
        phase_beginn=timezone.now() - timedelta(days=REGELN["beratung_tage"], hours=1),
    )
    ohne_antrag = _beschluss("anlegerin_nl_d")  # innere Angelegenheit, jünger — wird zuerst geschlossen
    zum_antrag = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.HERVORHEBUNG,
        antrag=antrag,
        gegenstand="Hervorhebung",
        beschreibung="Wichtig.",
        optionen=OPTIONEN,
        angelegt_von=leute[0],
        frist=timezone.now() - timedelta(minutes=1),
    )
    GremienBeschluss.objects.filter(pk=zum_antrag.pk).update(angelegt_am=timezone.now() - timedelta(hours=1))
    for m in leute:
        GremienStimme.objects.create(beschluss=zum_antrag, mitglied=m, option="dafuer", begruendung="ja")
    return antrag, ohne_antrag, zum_antrag


def _faeden_laufen_lassen(ablaeufe):
    """Startet je Eintrag einen Faden unter seinem Namen. Rückgabe: die Fehler je Faden und die Namen
    der Fäden, die nach einer Minute noch laufen (eine Verklemmung, die PostgreSQL nicht selbst auflöst)."""
    fehler = {}

    def lauf(name, ablauf):
        try:
            ablauf()
        except Exception as e:  # noqa: BLE001 — der Test berichtet jeden Fehler des Fadens
            fehler[name] = f"{type(e).__name__}: {(str(e).splitlines() or [''])[0]}"
        finally:
            connections.close_all()

    faeden = [threading.Thread(target=lauf, args=(name, ablauf), name=name) for name, ablauf in ablaeufe.items()]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(60)
    return fehler, [faden.name for faden in faeden if faden.is_alive()]


def _beide_haben_einmal_gewirkt(antrag, ohne_antrag, zum_antrag):
    """Das Ergebnis, gleich wer zuerst kam: Der Antrag steht in der Abstimmung und ist hervorgehoben,
    und jeder Schritt steht genau einmal in der Audit-Kette."""
    from plattform_core import Phase

    antrag.refresh_from_db()
    assert antrag.phase == Phase.ABSTIMMUNG.value
    assert antrag.hervorgehoben
    assert _audit(ohne_antrag.pk) == 1 and _audit(zum_antrag.pk) == 1
    wechsel = [
        e.ereignis
        for e in AuditEintrag.objects.all()
        if e.ereignis.get("typ") == "phasenwechsel" and e.ereignis.get("antrag") == antrag.pk
    ]
    assert [w["neue_phase"] for w in wechsel] == [Phase.ABSTIMMUNG.value]


def test_waechter_und_antragsseite_verklemmen_sich_nicht(monkeypatch):
    """Die Antragsseite hält die Zeile des Antrags, der Wächter wartet darauf.

    Eine Transaktion für alle fälligen Beschlüsse hielt den Audit-Eintrag des ersten bis zum Ende offen.
    Eine Antragsseite, die gleichzeitig den Antrag des zweiten fortschreibt, wartete am Audit-Kopf auf
    den Wächter, der Wächter an der Antragszeile auf die Seite — PostgreSQL brach eine der beiden mit
    „deadlock detected“ ab.

    Hergestellt wird genau diese Lage, im Ablauf seit 96fff65 (der Wächter sperrt bei einem Beschluss
    zu einem Antrag zuerst den Antrag): Die Seite sperrt den Antrag, wendet den Übergang in die
    Abstimmung an und hält vor ihrem Audit-Eintrag an, bis der Wächter den ersten Beschluss samt
    Audit-Eintrag geschlossen hat und beim zweiten an der Antragszeile wartet. Erst dann schreibt sie
    ins Audit. Hielte der Wächter dabei noch den Audit-Kopf (eine Transaktion für alles), wäre das der
    Kreis; so wartet er mit leeren Händen, die Seite wird fertig, und danach schließt der Wächter (oder
    die Seite in ihrem nächsten Schritt) den Beschluss auf dem fortgeschriebenen Stand."""
    from verfahren.models import Antrag

    antrag, ohne_antrag, zum_antrag = _antrag_mit_faelligem_beschluss()
    seite_haelt_den_antrag = threading.Event()
    waechter_beim_zweiten = threading.Event()
    beobachtet = {}

    echtes_abschliessen = GremienBeschluss.abschliessen

    def abschliessen(self, *args, **kwargs):
        if threading.current_thread().name == "waechter" and self.pk == zum_antrag.pk:
            # Der erste Beschluss ist geschlossen und festgeschrieben. Als Nächstes sperrt
            # `abschliessen` die Zeile des Antrags — die hält die Seite.
            waechter_beim_zweiten.set()
        return echtes_abschliessen(self, *args, **kwargs)

    monkeypatch.setattr(GremienBeschluss, "abschliessen", abschliessen)
    echtes_archiv = Antrag.chat_archivieren

    def archivieren(self, jetzt=None):
        n = echtes_archiv(self, jetzt)
        if threading.current_thread().name == "seite" and "waechter_wartet" not in beobachtet:
            # Mitten im Übergang: Die Zeile des Antrags ist gesperrt, der Audit-Eintrag folgt gleich.
            seite_haelt_den_antrag.set()
            beobachtet["waechter_wartet"] = waechter_beim_zweiten.wait(10) and _wartet_jemand_auf_eine_sperre()
        return n

    monkeypatch.setattr(Antrag, "chat_archivieren", archivieren)

    def waechter():
        assert seite_haelt_den_antrag.wait(10), "die Seite hat den Antrag nicht fortgeschrieben"
        GremienBeschluss.faellige_abschliessen()

    def seite():
        Antrag.objects.get(pk=antrag.pk).fortschreiben_bis_zum_stand()

    fehler, haengen = _faeden_laufen_lassen({"waechter": waechter, "seite": seite})
    assert fehler == {}
    assert haengen == []
    assert beobachtet == {"waechter_wartet": True}, "die Lage kam nicht zustande — der Test bewiese nichts"
    _beide_haben_einmal_gewirkt(antrag, ohne_antrag, zum_antrag)


def test_antragsseite_wartet_auf_den_waechter_und_verklemmt_sich_nicht(monkeypatch):
    """Die Gegenrichtung, der gewöhnliche Ablauf seit 96fff65: Der Wächter hält die Zeile des Antrags,
    die Antragsseite wartet darauf.

    Der Wächter schließt den Beschluss zum Antrag: Er sperrt den Antrag, schreibt ihn fort (Übergang in
    die Abstimmung samt Audit-Eintrag), sperrt den Beschluss und steht in dessen Wirkung — er hält jetzt
    Antrag, Beschluss und Audit-Kopf. Dort hält er an, bis die Antragsseite nachweislich an der Zeile
    des Antrags wartet. Sie hält dabei nichts (die Zeile des Antrags ist ihre erste Sperre), der Wächter
    braucht also nichts von ihr und wird fertig; danach findet die Seite nichts mehr zu tun."""
    import gremien.models as gm
    from verfahren.models import Antrag

    antrag, ohne_antrag, zum_antrag = _antrag_mit_faelligem_beschluss()
    waechter_haelt_alles = threading.Event()
    seite_beginnt = threading.Event()
    beobachtet = {}

    echte_beschlussfaehigkeit = gm._integritaetsrat_beschlussfaehig

    def beschlussfaehig(beschluss):
        if threading.current_thread().name == "waechter" and "seite_wartet" not in beobachtet:
            # In der Wirkung der Hervorhebung: Antrag und Beschluss sind gesperrt, der Übergang in die
            # Abstimmung steht mit seinem Audit-Eintrag in dieser noch offenen Transaktion.
            waechter_haelt_alles.set()
            beobachtet["seite_wartet"] = seite_beginnt.wait(10) and _wartet_jemand_auf_eine_sperre()
        return echte_beschlussfaehigkeit(beschluss)

    monkeypatch.setattr(gm, "_integritaetsrat_beschlussfaehig", beschlussfaehig)

    def waechter():
        GremienBeschluss.faellige_abschliessen()

    def seite():
        assert waechter_haelt_alles.wait(10), "der Wächter hat die Wirkung des Beschlusses nicht erreicht"
        seite_beginnt.set()
        Antrag.objects.get(pk=antrag.pk).fortschreiben_bis_zum_stand()

    fehler, haengen = _faeden_laufen_lassen({"waechter": waechter, "seite": seite})
    assert fehler == {}
    assert haengen == []
    assert beobachtet == {"seite_wartet": True}, "die Lage kam nicht zustande — der Test bewiese nichts"
    _beide_haben_einmal_gewirkt(antrag, ohne_antrag, zum_antrag)
