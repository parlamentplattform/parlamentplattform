"""Die Audit-Kette als Datenbank-Tatsache (F-22, ADR-005): keine Gabel, kein loser Zeitstempel.

Befund #9: Zwei gleichzeitige `anhaengen`-Aufrufe (zwei gunicorn-Worker auf PostgreSQL) lasen
denselben Kopf und hashten beide dagegen — die Kette gabelte sich still. Befund #75: Die
Spalte `zeit` lag neben dem Hash statt darunter."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from plattform_core import GENESIS, ereignis_hash, kette_pruefen
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def kette():
    return [(e.ereignis, e.hash) for e in AuditEintrag.objects.order_by("lfd")]


def test_jeder_eintrag_nennt_seinen_vorgaenger_und_die_kette_prueft_sich():
    AuditEintrag.anhaengen({"typ": "probe", "n": 1})
    AuditEintrag.anhaengen({"typ": "probe", "n": 2})
    erster, zweiter = AuditEintrag.objects.order_by("lfd")
    assert erster.vorgaenger == GENESIS and zweiter.vorgaenger == erster.hash
    assert kette_pruefen(kette()) == (True, None)


def test_zwei_eintraege_am_selben_kopf_sind_physisch_unmoeglich():
    """Die Eindeutigkeit von `vorgaenger` — nicht die Anwendung — verhindert die Gabel."""
    kopf = AuditEintrag.anhaengen({"typ": "probe"})
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEintrag.objects.create(
            zeit=timezone.now(),
            ereignis={"typ": "gabel"},
            vorgaenger=kopf.vorgaenger,
            hash=ereignis_hash(kopf.vorgaenger, {"typ": "gabel"}),
        )
    assert AuditEintrag.objects.count() == 1


def test_ein_ueberholter_kopf_wird_neu_gelesen(monkeypatch):
    """Das Wettrennen im Zeitraffer: Zwischen dem Lesen des Kopfes und dem Schreiben kommt ein
    zweiter Schreiber dazwischen. `anhaengen` bekommt den IntegrityError, liest den Kopf neu
    und hängt hinter dem Konkurrenten an — beide Einträge stehen, die Kette bleibt intakt."""
    AuditEintrag.anhaengen({"typ": "start"})
    echter_kopf = AuditEintrag._kopf.__func__
    aufrufe = []

    def ueberholt(cls):
        kopf = echter_kopf(cls)
        aufrufe.append(kopf)
        if len(aufrufe) == 1:
            konkurrent = {"typ": "konkurrent", "zeit": timezone.now().isoformat()}
            cls.objects.create(
                zeit=timezone.now(), ereignis=konkurrent, vorgaenger=kopf, hash=ereignis_hash(kopf, konkurrent)
            )
        return kopf

    monkeypatch.setattr(AuditEintrag, "_kopf", classmethod(ueberholt))
    with transaction.atomic():  # wie in `Antrag.fortschreiben`: eine äußere Transaktion
        eintrag = AuditEintrag.anhaengen({"typ": "nachzuegler"})
    assert len(aufrufe) == 2, "der zweite Versuch hat den Kopf neu gelesen"
    typen = list(AuditEintrag.objects.order_by("lfd").values_list("ereignis__typ", flat=True))
    assert typen == ["start", "konkurrent", "nachzuegler"]
    assert eintrag.vorgaenger == AuditEintrag.objects.get(ereignis__typ="konkurrent").hash
    assert kette_pruefen(kette()) == (True, None)


def test_nach_drei_ueberholungen_gibt_anhaengen_ehrlich_auf(monkeypatch):
    def immer_stale(cls):
        return GENESIS

    AuditEintrag.anhaengen({"typ": "start"})  # GENESIS ist damit vergeben
    monkeypatch.setattr(AuditEintrag, "_kopf", classmethod(immer_stale))
    with pytest.raises(IntegrityError, match="überholt"):
        AuditEintrag.anhaengen({"typ": "verloren"})
    assert AuditEintrag.objects.count() == 1


def test_der_zeitstempel_liegt_unter_dem_hash():
    """Befund #75: `zeit` allein ließ sich per Datenbankzugriff ändern, ohne dass die Kette es
    bemerkte. Jetzt steht der Zeitpunkt im versiegelten Ereignis; die Spalte zeigt denselben Wert."""
    eintrag = AuditEintrag.anhaengen({"typ": "stimme", "antrag": 1})
    assert eintrag.ereignis["zeit"] == eintrag.zeit.isoformat()
    assert kette_pruefen(kette()) == (True, None)
    manipuliert = dict(eintrag.ereignis)
    manipuliert["zeit"] = "2030-01-01T00:00:00+00:00"
    assert kette_pruefen([(manipuliert, eintrag.hash)]) == (False, 0)
