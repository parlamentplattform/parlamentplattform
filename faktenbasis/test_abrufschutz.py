"""Zeit, Eigentümerschaft und gemeinsames Kontingent; ohne Netz/echte Wartezeit."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections

from faktenbasis import abrufschutz as schutz
from faktenbasis.models import AbrufSperre
from faktenbasis.ris import RisFehler
from parameter.models import Parameter

pytestmark = pytest.mark.django_db
JETZT = datetime(2026, 11, 2, 22, 30, tzinfo=UTC)


def grenze(wert):
    Parameter.objects.create(
        schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert=str(wert), beschreibung="Test", quelle="Test",
    )


def test_kein_zweiter_abruf_waehrend_reservierung_oder_nachlaufendem_abstand():
    code = schutz.reservieren(JETZT)
    with pytest.raises(RisFehler, match="abruf_belegt"):
        schutz.reservieren(JETZT + timedelta(seconds=1))
    assert schutz.freigeben(code, JETZT + timedelta(seconds=3)) == 1
    with pytest.raises(RisFehler, match="abruf_belegt"):
        schutz.reservieren(JETZT + timedelta(seconds=4))
    assert schutz.reservieren(JETZT + timedelta(seconds=5)) != code
    assert AbrufSperre.objects.get().anzahl == 2


def test_fremder_oder_veralteter_code_kann_neuen_besitzer_nicht_entsperren():
    alt = schutz.reservieren(JETZT)
    neu = schutz.reservieren(JETZT + timedelta(seconds=schutz.SPERRSEKUNDEN + 1))
    assert alt != neu
    assert schutz.freigeben(alt, JETZT) == 0
    assert AbrufSperre.objects.get().sperrcode == neu


def test_gemeinsames_stundenkontingent_zaehlt_auch_einen_abgebrochenen_versuch():
    grenze(1)
    code = schutz.reservieren(JETZT)
    schutz.freigeben(code, JETZT)
    with pytest.raises(RisFehler, match="abruf_kontingent"):
        schutz.reservieren(JETZT + timedelta(seconds=2))
    assert AbrufSperre.objects.get().anzahl == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_null_und_negative_grenze_sperren_weitere_abrufe(limit):
    grenze(limit)
    with pytest.raises(RisFehler, match="abruf_kontingent"):
        schutz.reservieren(JETZT)
    assert not AbrufSperre.objects.exists()


def test_stundenwechsel_setzt_zaehler_zurueck_aber_hebt_keine_laufende_sperre_auf():
    grenze(1)
    kurz_vor = JETZT.replace(minute=59, second=59)
    code = schutz.reservieren(kurz_vor)
    danach = kurz_vor + timedelta(seconds=1)
    with pytest.raises(RisFehler, match="abruf_belegt"):
        schutz.reservieren(danach)
    schutz.freigeben(code, danach)
    schutz.reservieren(danach + timedelta(seconds=2))
    assert AbrufSperre.objects.get().anzahl == 1


def test_prozessabbruch_blockiert_nicht_ueber_die_schutzfrist_hinaus():
    alt = schutz.reservieren(JETZT)
    neu = schutz.reservieren(JETZT + timedelta(seconds=schutz.SPERRSEKUNDEN))
    assert alt != neu and AbrufSperre.objects.get().anzahl == 2


@pytest.mark.django_db(transaction=True)
def test_kontextmanager_gibt_auch_nach_abruf_fehler_frei_ohne_db_lock_ueber_den_abruf(monkeypatch):
    monkeypatch.setattr(schutz, "_jetzt", lambda: JETZT)
    with pytest.raises(RuntimeError):
        with schutz.einzelabruf():
            assert not connection.in_atomic_block
            raise RuntimeError("Testabbruch")
    assert AbrufSperre.objects.get().sperrcode == ""


@pytest.mark.django_db(transaction=True)
def test_zwei_datenbankverbindungen_reservieren_nicht_parallel():
    AbrufSperre.objects.create(name=schutz.NAME)
    start = Barrier(2)
    def versuch():
        close_old_connections()
        try:
            start.wait(timeout=10)
            try:
                schutz.reservieren(JETZT)
                return "ok"
            except RisFehler as fehler:
                return fehler.code
        finally:
            connections["default"].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ergebnisse = list(pool.map(lambda _: versuch(), range(2)))
    assert ergebnisse.count("ok") <= 1
    assert set(ergebnisse) <= {"ok", "abruf_belegt", "abrufschutz"}
    assert AbrufSperre.objects.get().anzahl == ergebnisse.count("ok")
    if connection.vendor == "postgresql":
        assert ergebnisse.count("ok") == 1
