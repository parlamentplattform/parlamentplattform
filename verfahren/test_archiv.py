"""S7 — das Archiv eines Antrags (FB-G7): Zeitleiste, Auswertung, Export als JSON und Markdown."""

import json

import pytest
from django.urls import reverse

from verfahren import archiv as archivkern
from verfahren import chat as chatkern
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _antrag(ordnung, autor=None):  # noqa: F811
    return antrag_einbringen(autor or mitglied_anlegen("autor"), **ANTRAG, ordnung=ordnung)


def _lage(ordnung):  # noqa: F811
    """Ein Antrag mit Chat in der Unterstützungsphase, dann hochgestuft in die Beratung."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _antrag(ordnung, leute[0])
    wurzel = chatkern.beitrag_schreiben(antrag, leute[0], "Das halte ich für tragfähig.")
    chatkern.beitrag_schreiben(antrag, leute[1], "Sehe ich auch so.", wurzel)
    for m in leute[1:]:
        antrag.unterstuetzungen.create(mitglied=m)
    antrag.fortschreiben()
    antrag.refresh_from_db()
    chatkern.beitrag_schreiben(antrag, leute[2], "Jetzt in der Beratung.")
    return antrag, leute, wurzel


def test_zeitleiste_zeigt_die_phasen_mit_ihren_beitraegen(ordnung):  # noqa: F811
    antrag, _leute, _wurzel = _lage(ordnung)
    bloecke = {b["phase"]: b for b in archivkern.zeitleiste(antrag)}
    assert "unterstuetzung" in bloecke and "beratung" in bloecke
    assert bloecke["unterstuetzung"]["anzahl"] == 2, "die geräumten Beiträge leben im Archiv weiter"
    assert bloecke["beratung"]["anzahl"] == 1 and bloecke["beratung"]["laufend"] is True
    assert bloecke["unterstuetzung"]["auswertung"] is None, "nur Vorschlagsrunden werden ausgewertet"


def test_export_json_traegt_fassung_und_antwortbezug(ordnung):  # noqa: F811
    """FB-G7 Abnahme: Export-JSON enthält die Fassung 1 und alle Beiträge mit `antwort_auf`."""
    antrag, _leute, wurzel = _lage(ordnung)
    daten = json.loads(archivkern.als_json(antrag))
    assert daten["antrag"]["id"] == antrag.pk and daten["antrag"]["titel"] == ANTRAG["titel"]
    assert daten["fassungen"][0]["nummer"] == 1 and daten["fassungen"][0]["wortlaut"] == ANTRAG["wortlaut"]
    beitraege = [b for block in daten["zeitleiste"] for b in block["beitraege"]]
    assert len(beitraege) == 3
    antwort = next(b for b in beitraege if b["antwort_auf"])
    assert antwort["antwort_auf"] == wurzel.pk
    assert all("verfasser" in b and "@" not in b["verfasser"] for b in beitraege), "keine Kontaktdaten"


def test_export_markdown_ist_lesbar(ordnung):  # noqa: F811
    antrag, _leute, _wurzel = _lage(ordnung)
    text = archivkern.als_markdown(antrag)
    assert text.startswith(f"# {ANTRAG['titel']}")
    assert "## Unterstützungsphase" in text and "## Beratung" in text
    assert "Das halte ich für tragfähig." in text
    assert "## Fassung 1" in text


def test_entfernter_beitrag_traegt_seinen_vermerk_statt_des_textes(ordnung):  # noqa: F811
    """Grundregel 7: Auch im Archiv wird nichts gelöscht — der Text weicht dem Vermerk."""
    antrag, leute, wurzel = _lage(ordnung)
    wurzel.geloescht = True
    wurzel.save(update_fields=["geloescht"])
    daten = json.loads(archivkern.als_json(antrag))
    beitraege = [b for block in daten["zeitleiste"] for b in block["beitraege"]]
    entfernt = next(b for b in beitraege if b["id"] == wurzel.pk)
    assert entfernt["text"] == "[vom Verfasser entfernt]"
    assert "Das halte ich für tragfähig." not in archivkern.als_markdown(antrag)


def test_audit_spur_nennt_nur_diesen_antrag(ordnung):  # noqa: F811
    antrag, _leute, _wurzel = _lage(ordnung)
    zweiter = _antrag(ordnung, mitglied_anlegen("andere"))
    spur = archivkern.audit_spur(antrag)
    assert spur and all(len(e["hash"]) == 12 for e in spur)
    assert any(e["typ"] == "phasenwechsel" for e in spur)
    assert archivkern.audit_spur(zweiter) != spur


def test_archiv_ist_oeffentlich_und_laedt_als_datei(client, ordnung):  # noqa: F811
    antrag, _leute, _wurzel = _lage(ordnung)
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert 'id="zone-archiv"' in seite and "Das halte ich für tragfähig." in seite

    for art, typ in (("json", "application/json"), ("md", "text/markdown")):
        antwort = client.get(reverse("verfahren:archiv_export", args=[antrag.pk, art]))
        assert antwort.status_code == 200 and typ in antwort["Content-Type"]
        assert antwort["Content-Disposition"] == f'attachment; filename="antrag-{antrag.pk}-archiv.{art}"'


def test_phasenname_benennt_die_vorschlagsrunden(ordnung):  # noqa: F811
    assert archivkern.phasenname("vorschlag-r2") == "Vorschlagsberatung — Runde 2"
    assert archivkern.phasenname("beratung") == "Beratung"
    assert archivkern.phasenname("") == "ohne Phase"
