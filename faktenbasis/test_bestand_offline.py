"""Echte lokale Webdownloads mit demselben Offlinewerkzeug nachrechnen."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from django.urls import reverse

from faktenbasis.models import Norm, NormText, PersonalAggregat, PersonalRessorttabelle
from faktenbasis.test_bestandsnachweis import bestand  # noqa: F401
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from tools.faktenbestand_pruefen import lesen, pruefen
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]
SKRIPT = Path(__file__).resolve().parents[1] / "tools/faktenbestand_pruefen.py"


def test_tatsaechlicher_gebundener_download_laesst_sich_ohne_plattform_nachrechnen(bestand, client, tmp_path):  # noqa: F811
    modelle = (Norm, NormText, PersonalAggregat, PersonalRessorttabelle, AuditEintrag)
    vorher = [list(m.objects.values()) for m in modelle]
    erster = client.get(reverse("faktenbasis:bestand_json"))
    hashwert = erster.json()["sha256"]
    gebunden = client.get(reverse("faktenbasis:bestand_json"), {"sha256": hashwert})
    assert gebunden.status_code == 200
    p = tmp_path / "bestand.json"
    p.write_bytes(gebunden.content)
    assert pruefen(lesen(p), hashwert)["schnappschuesse"] == 4
    r = subprocess.run([sys.executable, "-I", "-S", str(SKRIPT), str(p), "--sha256", hashwert],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False, cwd=tmp_path)
    assert r.returncode == 0 and not r.stderr and json.loads(r.stdout)["sha256"] == hashwert
    assert [list(m.objects.values()) for m in modelle] == vorher
