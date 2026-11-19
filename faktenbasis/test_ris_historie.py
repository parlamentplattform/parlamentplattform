import hashlib
import io
import json
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from faktenbasis.models import Norm, RisAenderungsseite
from faktenbasis.ris import RisFehler
from faktenbasis.ris_historie import importieren
from ki.models import KIAuftrag
from parameter.models import Parameter
from plattform_core.ris_historie import dokumente
from verfahren.models import AuditEintrag

TAG = date(2026, 11, 13)
KENNUNG = "NOR40213503"
URL = f"https://ogd.ris.bka.gv.at/eli/bgbl/1998/38/P27/{KENNUNG}"


def referenz(tag=TAG):
    return {"Data": {"Metadaten": {
        "Technisch": {"Applikation": "BrKons", "ID": KENNUNG},
        "Allgemein": {"Geaendert": tag.isoformat(), "DokumentUrl": URL},
        "Bundesrecht": {"BrKons": {"Gesetzesnummer": "20000673"}},
    }, "NurImArchiv": "synthetischer Originalinhalt"}}


def original(ref=None, *, seite=2, treffer=11, seitengroesse=10):
    return json.dumps({"OgdSearchResult": {"OgdDocumentResults": {
        "Hits": {"@pageNumber": str(seite), "@pageSize": str(seitengroesse), "#text": str(treffer)},
        "OgdDocumentReference": referenz() if ref is None else ref,
    }}}).encode()


@pytest.mark.parametrize("anzahl,ref", [(0, {}), (11, []), (True, []), (1, [None]), (2, []), (1, "")])
def test_ungueltige_referenzanzahl_und_form(anzahl, ref):
    assert dokumente(ref, TAG, anzahl) is None
    assert dokumente(referenz(), TAG.isoformat(), 1) is None


@pytest.mark.parametrize("gruppe,feld,wert", [
    ("Technisch", "Applikation", "LrKons"),
    ("Technisch", "ID", "NOR４０２１３５０３"),
    ("Allgemein", "Geaendert", "2026-11-12"),
    ("Allgemein", "DokumentUrl", []),
    ("BrKons", "Gesetzesnummer", "unbekannt"),
])
def test_fachlich_fremde_oder_mehrdeutige_dokumente(gruppe, feld, wert):
    ref = referenz()
    meta = ref["Data"]["Metadaten"]
    (meta["Bundesrecht"] if gruppe == "BrKons" else meta)[gruppe][feld] = wert
    assert dokumente(ref, TAG, 1) is None


@pytest.mark.parametrize("fall", ["falsche-seite", "falscher-tag", "falsche-groesse", "falscher-hash",
                                 "ausserhalb", "leer", "unvollstaendig", "doppelt", "fremder-host", "falsches-ziel"])
@pytest.mark.django_db
def test_abgewiesene_seite_hinterlaesst_keinen_teilbeleg(fall):
    ref = referenz()
    parameter = {"seite": 2, "treffer": 11, "seitengroesse": 10}
    tag, seite, hashwert = TAG, 2, None
    if fall == "falsche-seite":
        seite = 1
    elif fall == "falscher-tag":
        tag -= timedelta(days=1)
    elif fall == "falsche-groesse":
        parameter["seitengroesse"] = 20
    elif fall == "falscher-hash":
        hashwert = "0" * 64
    elif fall == "ausserhalb":
        parameter["treffer"] = 10
    elif fall == "leer":
        seite = parameter["seite"] = 1
        parameter["treffer"], ref = 0, []
    elif fall == "unvollstaendig":
        parameter["treffer"] = 12
    elif fall == "doppelt":
        parameter["treffer"], ref = 12, [ref, ref]
    elif fall == "fremder-host":
        ref["Data"]["Metadaten"]["Allgemein"]["DokumentUrl"] = URL.replace(".bka.gv.at", ".example.invalid")
    else:
        ref["Data"]["Metadaten"]["Allgemein"]["DokumentUrl"] = URL.replace(KENNUNG, "NOR00000001")
    vorher = AuditEintrag.objects.count()
    with pytest.raises(RisFehler):
        importieren(tag, seite, original(ref, **parameter), erwartete_pruefsumme=hashwert)
    assert not RisAenderungsseite.objects.exists()
    assert AuditEintrag.objects.count() == vorher


@pytest.mark.django_db
def test_cli_archiviert_bytes_idempotent_ohne_folgen_fuer_normen_oder_modellauftraege(tmp_path):
    belege = tmp_path / "geschichte.json"
    roh = original()
    hashwert = hashlib.sha256(roh).hexdigest()
    belege.write_bytes(roh)
    args = ["--tag", TAG.isoformat(), "--seite", "2", "--datei", str(belege), "--sha256", hashwert]
    protokoll = io.StringIO()
    for _ in range(2):
        call_command("ris_aenderungsseite", *args, stdout=protokoll)
    stand = RisAenderungsseite.objects.get()
    assert stand.tag == TAG and stand.seite == 2 and stand.treffer == 11
    assert stand.dokumente == [{"dokumentnummer": KENNUNG, "gesetzesnummer": "20000673", "quelle": URL}]
    assert bytes(stand.original) == roh and stand.original_sha256 == hashwert and stand.parser_fassung == 1
    assert hashwert in protokoll.getvalue()
    zweiter = importieren(TAG, 2, roh + b"\n")
    assert zweiter.pk != stand.pk and RisAenderungsseite.objects.count() == 2
    assert AuditEintrag.objects.filter(ereignis__typ="ris_aenderungsseite").count() == 2
    assert not Norm.objects.exists() and not KIAuftrag.objects.exists()
    with pytest.raises(ValidationError, match="bleibt erhalten"):
        stand.delete()
    with pytest.raises(CommandError, match="ließ sich nicht lesen"):
        call_command("ris_aenderungsseite", "--tag", TAG.isoformat(), "--seite", "2",
                     "--datei", str(tmp_path / "fehlt.json"))


@pytest.mark.django_db
def test_aenderungsseite_nur_lesend_und_neutral_paginierten_bestand_anzeigen(client):
    pfad = reverse("faktenbasis:aenderungen")
    assert "noch keine RIS-Änderungsseiten" in client.get(pfad).content.decode()
    gestern = TAG - timedelta(days=1)
    importieren(gestern, 2, original(referenz(gestern)))
    aelter = importieren(TAG, 2, original([referenz()]))
    aktuell = importieren(TAG, 2, original([referenz()]) + b"\n")
    Parameter.objects.update_or_create(schluessel="faktenbasis-seitengroesse", defaults={"wert": "1"})
    vorher = AuditEintrag.objects.count()
    with CaptureQueriesContext(connection) as anfragen:
        antwort = client.get(pfad)
    assert [stand.pk for stand in antwort.context["seite"]] == [aktuell.pk]
    assert all('"faktenbasis_risaenderungsseite"."original"' not in query["sql"] for query in anfragen)
    html = antwort.content.decode()
    assert KENNUNG in html and "1 Dokument auf dieser Seite, 11 Treffer laut RIS" in html
    assert aktuell.original_sha256 in html and "synthetischer Originalinhalt" not in html
    assert [stand.pk for stand in client.get(pfad, {"seite": 2}).context["seite"]] == [aelter.pk]
    assert client.post(pfad).status_code == 405
    assert AuditEintrag.objects.count() == vorher
