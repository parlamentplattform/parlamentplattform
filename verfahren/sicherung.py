"""Sicherung innerhalb des Render-Dienstes; Upload ausschließlich in ein privates Repository.

Die Datenbankadresse verlässt Render nicht. Sitzungen und Anmeldelinks fehlen im Dump.
Fehlertexte enthalten weder Zugangsdaten noch Datenbankinhalte. ADR-013.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from verfahren.models import Hintergrundlauf

NAME = "sicherung"
ZEITLIMIT = 600  # kürzer als die 15-Minuten-Reservierung
VERSUCH_MINUTEN = 15
TAG = re.compile(r"ddoe-sicherung-\d{4}-\d{2}-\d{2}T(?:\d{4}|\d{6})Z\Z")
log = logging.getLogger(__name__)


class Sicherungsfehler(RuntimeError):
    """Nur öffentliche, selbst formulierte Fehlertexte verwenden."""


class KeineUmleitung(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHub:
    def __init__(self, token, repository):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise Sicherungsfehler("Ungültiges Sicherungsrepository.")
        self.token = token
        self.repository = repository
        self.basis = f"https://api.github.com/repos/{repository}"

    def api(self, pfad="", methode="GET", daten=None):
        inhalt = json.dumps(daten).encode() if daten is not None else None
        req = Request(self.basis + pfad, data=inhalt, method=methode, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "User-Agent": "DDOE-Sicherung", "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with build_opener(KeineUmleitung).open(req, timeout=30) as antwort:
                roh = antwort.read(2_000_000)
                return json.loads(roh) if roh else None
        except (HTTPError, URLError, OSError, ValueError):
            raise Sicherungsfehler("GitHub-Zugriff fehlgeschlagen; Token und Repository prüfen.") from None

    def hochladen(self, release, datei):
        # Fester GitHub-Host statt einer unkontrollierten Antwort-URL; kein Redirect mit Token.
        pfad = f"/repos/{self.repository}/releases/{int(release['id'])}/assets?name={quote(datei.name)}"
        verbindung = http.client.HTTPSConnection("uploads.github.com", timeout=60)
        try:
            with datei.open("rb") as quelle:
                verbindung.request("POST", pfad, body=quelle, headers={
                    "Authorization": f"Bearer {self.token}", "User-Agent": "DDOE-Sicherung",
                    "Content-Type": "application/octet-stream", "Content-Length": str(datei.stat().st_size),
                })
            antwort = verbindung.getresponse()
            if antwort.status != 201:
                raise Sicherungsfehler("Sicherungsdatei konnte nicht hochgeladen werden.")
            asset = json.loads(antwort.read(1_000_000))
            if asset.get("size") != datei.stat().st_size or asset.get("state") != "uploaded":
                raise Sicherungsfehler("Hochgeladene Sicherungsdatei ist unvollständig.")
        except (OSError, ValueError, http.client.HTTPException):
            raise Sicherungsfehler("Sicherungsupload unterbrochen.") from None
        finally:
            verbindung.close()


def _prozess(argumente, env=None, timeout=ZEITLIMIT):
    try:
        return subprocess.run(argumente, env=env, capture_output=True, check=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        raise Sicherungsfehler("PostgreSQL-Sicherungswerkzeug fehlgeschlagen.") from None


def _werkzeuge():
    env = os.environ.copy()
    dump = shutil.which("pg_dump")
    if dump:
        version = _prozess([dump, "--version"]).decode()
        if re.search(r"\b17\.", version):
            return dump, str(Path(dump).with_name("pg_restore")), env
    # Die native Render-Laufzeit hat ältere Clients. Signierte PGDG-Pakete lokal entpacken.
    ziel = Path(tempfile.gettempdir()) / "ddoe-postgres-client"
    _prozess(["bash", str(settings.BASE_DIR / "tools/postgres_client.sh"), str(ziel)], timeout=180)
    libs = list((ziel / "root/usr/lib").glob("*-linux-gnu"))
    env["LD_LIBRARY_PATH"] = os.pathsep.join(str(p) for p in libs) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    basis = ziel / "root/usr/lib/postgresql/17/bin"
    return str(basis / "pg_dump"), str(basis / "pg_restore"), env


def _export(datei):
    if connection.vendor != "postgresql":
        raise Sicherungsfehler("Die Sicherung braucht PostgreSQL.")
    dump, restore, env = _werkzeuge()
    db = connection.settings_dict
    env.update(PGHOST=str(db["HOST"]), PGPORT=str(db.get("PORT") or 5432),
               PGDATABASE=str(db["NAME"]), PGUSER=str(db["USER"]), PGPASSWORD=str(db["PASSWORD"]),
               PGCONNECT_TIMEOUT="15")
    # Dump und Zähler lesen denselben konsistenten Stand, auch während jemand abstimmt.
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute("SELECT pg_export_snapshot()")
        snapshot = cursor.fetchone()[0]
        cursor.execute("SELECT (SELECT count(*) FROM verfahren_auditeintrag), "
                       "(SELECT count(*) FROM verfahren_antrag), (SELECT count(*) FROM mitglieder_mitglied)")
        audit, antraege, konten = cursor.fetchone()
        _prozess([dump, "--format=custom", "--compress=6", "--no-owner", "--no-privileges",
                  "--exclude-table-data=django_session", "--exclude-table-data=mitglieder_einmaltoken",
                  f"--snapshot={snapshot}", f"--file={datei}"], env)
    liste = _prozess([restore, "--list", str(datei)], env).decode()
    if len([z for z in liste.splitlines() if z and not z.startswith(";")]) < 10:
        raise Sicherungsfehler("Sicherung enthält zu wenige Datenbankobjekte.")
    return {"audit": audit, "antraege": antraege, "konten": konten}


def sichern(jetzt=None):
    jetzt = (jetzt or timezone.now()).astimezone(UTC)
    token = os.environ.get("DDOE_SICHERUNG_TOKEN", "").strip()
    if not token:
        raise Sicherungsfehler("DDOE_SICHERUNG_TOKEN fehlt im Render-Webdienst.")
    github = GitHub(token, os.environ.get("DDOE_SICHERUNG_REPOSITORY", "parlamentplattform/sicherung"))
    repo = github.api()
    if repo.get("private") is not True:
        raise Sicherungsfehler("Sicherungsrepository muss privat sein.")
    if repo.get("size") == 0 and not github.api("/branches?per_page=1"):
        github.api("/contents/README.md", "PUT", {
            "message": "Initialisiere das private Sicherungsrepository",
            "content": base64.b64encode(b"# DDoe Sicherung\n\nPrivate monatliche Datenbanksicherungen.\n").decode(),
        })
    releases = github.api("/releases?per_page=100")
    fertig = [r for r in releases if TAG.fullmatch(r.get("tag_name", "")) and not r.get("draft")]
    letzte = max(fertig, key=lambda r: r["tag_name"], default=None)
    if letzte and letzte["tag_name"][15:22] == jetzt.strftime("%Y-%m"):
        # Prozess kann nach erfolgreichem Upload, aber vor dem DB-Stempel beendet worden sein.
        namen = {a["name"] for a in letzte.get("assets", []) if a.get("state") == "uploaded"}
        tag = letzte["tag_name"]
        if {f"{tag}.dump", f"{tag}.dump.sha256"} <= namen:
            return {"erfolgreich_am": letzte["published_at"], "release": tag}
    tag = f"ddoe-sicherung-{jetzt:%Y-%m-%dT%H%M%SZ}"
    with tempfile.TemporaryDirectory(prefix="ddoe-sicherung-") as ordner:
        datei = Path(ordner) / f"{tag}.dump"
        zahlen = _export(datei)
        if letzte:
            vorher = re.search(r"\baudit=(\d+)\b", letzte.get("body") or "")
            if not vorher or zahlen["audit"] < int(vorher[1]):
                raise Sicherungsfehler("Audit-Zahl der Sicherung ist kleiner oder nicht vergleichbar.")
        with datei.open("rb") as quelle:
            # Python 3.11 und 3.12 werden unterstützt.
            pruefsumme = hashlib.file_digest(quelle, "sha256").hexdigest()
        sha = datei.with_suffix(".dump.sha256")
        sha.write_text(f"{pruefsumme}  {datei.name}\n", encoding="ascii")
        body = "art=monatlich " + " ".join(f"{k}={v}" for k, v in zahlen.items())
        release = github.api("/releases", "POST", {"tag_name": tag, "name": tag, "body": body, "draft": True})
        github.hochladen(release, datei)
        github.hochladen(release, sha)
        github.api(f"/releases/{release['id']}", "PATCH", {"draft": False})
        _aufraeumen(github, fertig, jetzt)
        return {"erfolgreich_am": jetzt.isoformat(), "release": tag, "sha256": pruefsumme, **zahlen}


def _aufraeumen(github, releases, jetzt):
    for r in releases:
        tag = r["tag_name"]
        zeittext = tag.removeprefix("ddoe-sicherung-")
        formatierung = "%Y-%m-%dT%H%MZ" if len(zeittext) == 16 else "%Y-%m-%dT%H%M%SZ"
        datum = datetime.strptime(zeittext, formatierung).replace(tzinfo=UTC)
        frist = 365 if datum.day == 1 or "art=monatlich" in (r.get("body") or "") else 90
        if jetzt - datum > timedelta(days=frist):
            github.api(f"/releases/{r['id']}", "DELETE")
            github.api(f"/git/refs/tags/{tag}", "DELETE")


def eine_runde():
    """Eigener Faden: ein Export hält weder Fristen-Wächter noch Postausgang auf."""
    from verfahren.hintergrund import Lauf, ausfuehren

    if not os.environ.get("DDOE_SICHERUNG_TOKEN"):
        return
    stand = Hintergrundlauf.objects.filter(name=NAME).values_list("zuletzt_stand", flat=True).first() or {}
    zeit = stand.get("erfolgreich_am")
    if zeit and datetime.fromisoformat(zeit.replace("Z", "+00:00")).strftime("%Y-%m") == timezone.now().strftime("%Y-%m"):
        return
    lauf = Lauf(NAME, lambda: VERSUCH_MINUTEN, sichern)
    if connection.vendor != "postgresql":
        ausfuehren(lauf)
        return
    # Zusätzliche prozessgebundene Sperre: Auch ein ungewöhnlich langer Upload
    # bleibt exklusiv, wenn die zeitliche Reservierung inzwischen abgelaufen wäre.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(74888, 1)")
        if not cursor.fetchone()[0]:
            return
        try:
            ausfuehren(lauf)
        finally:
            cursor.execute("SELECT pg_advisory_unlock(74888, 1)")


def starten(worker):
    from django.db import close_old_connections

    if not os.environ.get("DDOE_SICHERUNG_TOKEN"):
        return

    def hintergrund():
        warten = threading.Event()
        while worker.alive:
            try:
                eine_runde()
            except Exception:
                # Keine fremden Fehlertexte (etwa mit Verbindungsdaten) ins Protokoll übernehmen.
                log.error("Sicherungsfaden unterbrochen; neuer Versuch folgt.")
            finally:
                close_old_connections()
            warten.wait(60)
    threading.Thread(target=hintergrund, name="sicherung", daemon=True).start()


@never_cache
def status(request):
    zeile = Hintergrundlauf.objects.filter(name=NAME).first()
    stand = zeile.zuletzt_stand if zeile else {}
    zeit = stand.get("erfolgreich_am")
    ok = bool(zeit and datetime.fromisoformat(zeit.replace("Z", "+00:00")).strftime("%Y-%m")
              == timezone.now().strftime("%Y-%m"))
    return JsonResponse({"status": "ok" if ok else "keine_aktuelle_sicherung", "zuletzt_erfolgreich": zeit},
                        status=200 if ok else 503)
