"""Neue automatische Aufträge ersetzen den alten Rechtsbezug, ohne alte Jobs zu verdoppeln."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import hashlib
import json

import pytest
from django.db import connection, transaction
from django.urls import reverse

from ki import folgenkontext, warteschlange
from ki.models import KIAuftrag, KILauf, Zweck
from ki.test_folgenauftraege import attrappe  # noqa: F401
from ki.test_kontext import antrag, vorschlag  # noqa: F401
from ki.warteschlange import einreihen, rechtspruefung_einreihen, rechtspruefung_ohne_hemmung
from parameter.models import Parameter
from plattform_core.rechtsfolgen import schema_als_dict, schema_sha256
from verfahren.models import Antrag
from verfahren.test_views_aktionen import ANTRAG, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_standardweg_erstellt_einen_kombinierten_auftrag_und_nicht_zwei(antrag):
    m = antrag.eingebracht_von
    j = rechtspruefung_einreihen(antrag, m)
    assert j.zweck == Zweck.RECHTSFOLGEN and j.folgenkontext["hoechstzeichen"] == 30000
    assert rechtspruefung_einreihen(antrag, m).pk == j.pk and KIAuftrag.objects.count() == 1
    assert not KILauf.objects.exists()


@pytest.mark.parametrize("quelle", ["antrag", "vorschlag"])
def test_alter_wartender_auftrag_bekommt_weder_neue_grundlagen_noch_zweiten_zweck(antrag, quelle, monkeypatch):
    v = vorschlag(antrag) if quelle == "vorschlag" else None
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von, vorschlagsfassung=v)
    vorher = copy.deepcopy(KIAuftrag.objects.values().get(pk=alt.pk))
    monkeypatch.setattr(folgenkontext, "mit_grundlagen", lambda *a, **k: pytest.fail("Alte Quellen nicht nachladen"))
    j = rechtspruefung_einreihen(antrag, antrag.eingebracht_von, vorschlagsfassung=v)
    assert j.pk == alt.pk and KIAuftrag.objects.values().get(pk=alt.pk) == vorher
    assert KIAuftrag.objects.count() == 1 and not j.folgenkontext


def test_web_einbringen_reiht_folgen_statt_rechtsbezug_ein_und_bleibt_ohne_modellaufruf(client, antrag):
    m = antrag.eingebracht_von
    client.force_login(m)
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "titel": "Anderer öffentlicher Antrag", "trotzdem": "1"})
    assert antwort.status_code == 302
    neu = Antrag.objects.latest("pk")
    assert neu.pk != antrag.pk
    zwecke = list(KIAuftrag.objects.filter(antrag=neu).values_list("zweck", flat=True))
    assert zwecke == [Zweck.RECHTSFOLGEN] and not KILauf.objects.exists()


def test_vorschlagseinreichung_beauftragt_genau_die_eingereichte_fassung(antrag):
    a = antrag
    a.phase = "beratung"
    a.save(update_fields=["phase"])
    v = vorschlag(a)
    assert v.entwurf.einreichen()
    job = KIAuftrag.objects.get(antrag=a)
    assert job.zweck == Zweck.RECHTSFOLGEN and job.vorschlagsfassung_id == v.pk
    assert job.folgenkontext["text"]["fassung_id"] == v.pk
    assert v.entwurf.einreichen() and KIAuftrag.objects.filter(antrag=a).count() == 1


def test_kleine_offene_grenze_hemmt_keinen_antrag_und_keine_aeussere_transaktion(antrag):
    Parameter.objects.update_or_create(schluessel="rechtsfolgen-eingabezeichen", defaults={"wert": "1"})
    with transaction.atomic():
        j = rechtspruefung_ohne_hemmung(antrag, antrag.eingebracht_von)
        assert j.status == "gescheitert" and Antrag.objects.filter(pk=antrag.pk).exists()
    assert not KILauf.objects.exists()


def test_auftragsdatenbankfehler_vergiftet_nicht_das_aeussere_verfahren(antrag, monkeypatch):
    def kaputt(*a, **k):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM absichtlich_fehlende_auftragstesttabelle")
    monkeypatch.setattr(warteschlange, "einreihen", kaputt)
    with transaction.atomic():
        assert rechtspruefung_ohne_hemmung(antrag, antrag.eingebracht_von) is None
        assert Antrag.objects.filter(pk=antrag.pk).exists()


def test_oeffentliches_folgenschema_ist_eigenstaendig_und_exakt_nachrechenbar(client):
    r = client.get(reverse("verfahren:rechtsfolgenformat"))
    assert r.status_code == 200 and r["X-Content-Type-Options"] == "nosniff"
    assert r["Content-Disposition"] == 'attachment; filename="rechtsfolgen-schema-v2.json"'
    d = r.json()
    assert d == schema_als_dict()
    kanon = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert hashlib.sha256(kanon.encode()).hexdigest() == schema_sha256()
    deltas = d["properties"]["personal"]["items"]["properties"]
    assert all(deltas[k] == {"type": "null"} for k in ("beamte_delta_min", "beamte_delta_max", "vb_delta_min", "vb_delta_max"))
    assert r.json() != client.get(reverse("verfahren:antwortformat")).json()
