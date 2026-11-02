"""Monatsrhythmus, private Ablage, Fehlerfälle und konsistenter PostgreSQL-Export."""
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse

from verfahren import sicherung as s
from verfahren.models import Hintergrundlauf

JETZT = datetime(2026, 11, 2, 12, tzinfo=UTC)
pytestmark = pytest.mark.django_db


class GitHubProbe:
    def __init__(self):
        self.privat = True
        self.releases = []
        self.aufrufe = []
        self.assets = []
        self.fehler = False

    def api(self, pfad="", methode="GET", daten=None):
        self.aufrufe.append((pfad, methode, daten))
        if pfad == "":
            return {"private": self.privat, "size": 1}
        if pfad.startswith("/releases?"):
            return self.releases
        if methode == "POST":
            return {"id": 11, **daten}

    def hochladen(self, release, datei):
        if self.fehler:
            raise s.Sicherungsfehler("Upload unterbrochen.")
        self.assets.append((datei.name, datei.read_bytes()))


@pytest.fixture
def github(monkeypatch):
    g = GitHubProbe()
    monkeypatch.setenv("DDOE_SICHERUNG_TOKEN", "nur-ein-testtoken")
    monkeypatch.setattr(s, "GitHub", lambda *args: g)

    def export(datei):
        datei.write_bytes(b"PGDMP-Datenbankprobe")
        return {"audit": 50, "antraege": 7, "konten": 5}

    monkeypatch.setattr(s, "_export", export)
    return g


def release(tag="ddoe-sicherung-2026-10-01T021700Z", audit=45, **extra):
    return {"id": 1, "tag_name": tag, "body": f"audit={audit}", "draft": False, **extra}


def test_upload_nur_in_private_ablage_und_erst_danach_veroeffentlichen(github):
    stand = s.sichern(JETZT)
    assert stand["audit"] == 50 and len(stand["sha256"]) == 64
    assert len(github.assets) == 2
    assert github.assets[1][1].decode().startswith(stand["sha256"])
    posten = next(x for x in github.aufrufe if x[1] == "POST")
    assert posten[2]["draft"] is True and "art=monatlich" in posten[2]["body"]
    assert github.aufrufe[-1][1:] == ("PATCH", {"draft": False})


def test_oeffentliches_repository_erhaelt_keinen_export(github, monkeypatch):
    github.privat = False
    monkeypatch.setattr(s, "_export", lambda _: pytest.fail("Kein Export in ein öffentliches Ziel"))
    with pytest.raises(s.Sicherungsfehler, match="privat"):
        s.sichern(JETZT)
    assert not github.assets


def test_leeres_privates_repository_wird_vor_dem_ersten_release_initialisiert(github, monkeypatch):
    api = github.api

    def leeres_repository(pfad="", methode="GET", daten=None):
        if pfad == "":
            return {"private": True, "size": 0}
        if pfad.startswith("/branches?"):
            return []
        return api(pfad, methode, daten)

    monkeypatch.setattr(github, "api", leeres_repository)
    s.sichern(JETZT)
    initialisierung = next(i for i, aufruf in enumerate(github.aufrufe) if aufruf[1] == "PUT")
    veroeffentlichung = next(i for i, aufruf in enumerate(github.aufrufe) if aufruf[1] == "POST")
    assert initialisierung < veroeffentlichung
    assert github.aufrufe[initialisierung][0] == "/contents/README.md"
    assert len(github.assets) == 2


def test_fehlender_alter_auditzaehler_verhindert_upload(github):
    github.releases = [release(body=None)]
    with pytest.raises(s.Sicherungsfehler, match="nicht vergleichbar"):
        s.sichern(JETZT)
    assert not github.assets


def test_kleinere_sicherung_wird_nicht_hochgeladen_und_loescht_nichts(github):
    github.releases = [release("ddoe-sicherung-2026-10-01T0217Z", audit=51)]
    with pytest.raises(s.Sicherungsfehler, match="kleiner"):
        s.sichern(JETZT)
    assert not github.assets and not any(x[1] == "DELETE" for x in github.aufrufe)


def test_uploadfehler_veroeffentlicht_keine_halbe_sicherung_und_loescht_nichts(github):
    github.fehler = True
    with pytest.raises(s.Sicherungsfehler, match="unterbrochen"):
        s.sichern(JETZT)
    assert not any(x[1] in ("PATCH", "DELETE") for x in github.aufrufe)


def test_fertige_monatssicherung_wird_nach_prozessverlust_wiedererkannt(github, monkeypatch):
    tag = "ddoe-sicherung-2026-11-01T021700Z"
    github.releases = [release(tag, published_at="2026-11-01T02:17:00Z", assets=[
        {"name": tag + ende, "state": "uploaded"} for ende in (".dump", ".dump.sha256")])]
    monkeypatch.setattr(s, "_export", lambda _: pytest.fail("Diesen Monat bereits gesichert"))
    assert s.sichern(JETZT)["release"] == tag
    assert not github.assets


def test_monatssicherungen_bleiben_ein_jahr_und_fremde_releases_unberuehrt(github):
    github.releases = [
        release("ddoe-sicherung-2026-07-02T021700Z", body="art=monatlich audit=40"),
        release("ddoe-sicherung-2025-10-01T021700Z", id=2),
        release("andere-datei", id=3),
        release("ddoe-sicherung-2026-07-02T0217Z", id=4),
    ]
    s.sichern(JETZT)
    geloescht = [x[0] for x in github.aufrufe if x[1] == "DELETE"]
    assert "/releases/2" in geloescht and "/releases/1" not in geloescht and "/releases/3" not in geloescht
    assert "/releases/4" in geloescht  # ältere tägliche Sicherung: weiterhin 90 Tage


def test_fehlender_token_wird_klar_gemeldet(monkeypatch):
    monkeypatch.delenv("DDOE_SICHERUNG_TOKEN", raising=False)
    with pytest.raises(s.Sicherungsfehler, match="TOKEN fehlt"):
        s.sichern(JETZT)


def test_hintergrund_ist_pro_kalendermonat_faellig_und_respektiert_reservierung(github, monkeypatch):
    monkeypatch.setattr(s.timezone, "now", lambda: JETZT)
    s.eine_runde()
    assert len(github.assets) == 2
    s.eine_runde()
    assert len(github.assets) == 2
    zeile = Hintergrundlauf.objects.get(name=s.NAME)
    zeile.zuletzt_stand = {}
    zeile.gesperrt_bis = JETZT + timedelta(minutes=5)
    zeile.save()
    s.eine_runde()
    assert len(github.assets) == 2


def test_status_nennt_nur_erfolgsdatum_und_ist_beim_monatswechsel_rot(client, monkeypatch):
    monkeypatch.setattr(s.timezone, "now", lambda: JETZT)
    url = reverse("verfahren:sicherung_status")
    assert client.get(url).status_code == 503
    Hintergrundlauf.objects.create(name=s.NAME, zuletzt_stand={"erfolgreich_am": JETZT.isoformat(),
                                                            "token": "privat", "konten": 20})
    antwort = client.get(url)
    assert antwort.status_code == 200 and "no-cache" in antwort["Cache-Control"]
    assert set(antwort.json()) == {"status", "zuletzt_erfolgreich"}
    monkeypatch.setattr(s.timezone, "now", lambda: JETZT.replace(month=12))
    assert client.get(url).status_code == 503


def test_export_nutzt_denselben_snapshot_und_keine_zugangsdaten_in_argumenten(monkeypatch, tmp_path):
    abfragen = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            abfragen.append(sql)

        def fetchone(self):
            return ("snapshot-1",) if "pg_export_snapshot" in abfragen[-1] else (50, 7, 5)

    monkeypatch.setattr(s, "connection", SimpleNamespace(vendor="postgresql", cursor=Cursor, settings_dict={
        "HOST": "intern", "NAME": "db", "USER": "leser", "PASSWORD": "geheimes-passwort"}))
    monkeypatch.setattr(s.transaction, "atomic", nullcontext)
    monkeypatch.setattr(s, "_werkzeuge", lambda: ("pg_dump", "pg_restore", {}))
    prozesse = []

    def prozess(args, env):
        prozesse.append((args, env.copy()))
        return b"Objekt\n" * 20

    monkeypatch.setattr(s, "_prozess", prozess)
    assert s._export(tmp_path / "probe.dump") == {"audit": 50, "antraege": 7, "konten": 5}
    assert "REPEATABLE READ, READ ONLY" in abfragen[0]
    args, env = prozesse[0]
    assert "--snapshot=snapshot-1" in args and env["PGPASSWORD"] == "geheimes-passwort"
    assert "geheimes-passwort" not in " ".join(args)
    assert "--exclude-table-data=django_session" in args
    assert "--exclude-table-data=mitglieder_einmaltoken" in args


def test_fremde_oder_umgeleitete_uploadziele_sind_keine_api_basis():
    with pytest.raises(s.Sicherungsfehler):
        s.GitHub("test", "https://fremd.example/repo")
    assert s.KeineUmleitung().redirect_request(None, None, None, None, None, None) is None
