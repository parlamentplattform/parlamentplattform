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
    assert 'id="zone-archiv"' in seite and "2 Beiträge" in seite
    assert "Das halte ich für tragfähig." not in seite, "Beiträge kommen erst auf Wunsch (Befund #42)"
    geoeffnet = client.get(reverse("verfahren:antrag", args=[antrag.pk]) + "?archiv=unterstuetzung").content.decode()
    assert "Das halte ich für tragfähig." in geoeffnet

    for art, typ in (("json", "application/json"), ("md", "text/markdown")):
        antwort = client.get(reverse("verfahren:archiv_export", args=[antrag.pk, art]))
        assert antwort.status_code == 200 and typ in antwort["Content-Type"]
        assert antwort["Content-Disposition"] == f'attachment; filename="antrag-{antrag.pk}-archiv.{art}"'


def test_phasenname_benennt_die_vorschlagsrunden(ordnung):  # noqa: F811
    assert archivkern.phasenname("vorschlag-r2") == "Vorschlagsberatung — Runde 2"
    assert archivkern.phasenname("beratung") == "Beratung"
    assert archivkern.phasenname("") == "ohne Phase"


def test_phasennamen_folgen_der_sprache(ordnung):  # noqa: F811
    """Die Blocküberschriften des Archivs stehen in der Sprache der Oberfläche."""
    from django.utils import translation

    with translation.override("en"):
        assert archivkern.phasenname("unterstuetzung") == "Support phase"
        assert archivkern.phasenname("beratung") == "Deliberation"
        assert archivkern.phasenname("vorschlag-r2") == "Proposal deliberation — round 2"


def test_abgeschlossene_phasen_laufen_nicht_mehr(ordnung):  # noqa: F811
    """FB-G7: „· läuft" gehört an die laufende Phase, nicht an einen Endzustand."""
    from plattform_core import Phase

    antrag = _antrag(ordnung)
    antrag.phase = Phase.ANGENOMMEN.value
    antrag.save(update_fields=["phase"])
    assert not any(b["laufend"] for b in archivkern.zeitleiste(antrag)), "angenommen läuft nicht"

    antrag.phase = Phase.BERATUNG.value
    antrag.save(update_fields=["phase"])
    laufend = [b["name"] for b in archivkern.zeitleiste(antrag) if b["laufend"]]
    assert laufend == ["Beratung"]


def test_der_export_kuerzt_die_audit_spur_nicht(ordnung):  # noqa: F811
    """FB-G7 verspricht einen vollständigen Export; Grundregel 7 verlangt, dass nichts
    verschwindet. Die Anzeige darf kürzen — der Export nie.

    Gefunden bei der Bestandsaufnahme zu S8: `archiv()` nutzte dieselbe gekürzte Spur wie die
    Seite, und wer mehr als 60 Ereignisse hatte, bekam sie ohne Hinweis nicht alle."""
    from verfahren.models import AuditEintrag

    antrag, _leute, _wurzel = _lage(ordnung)
    for n in range(70):
        AuditEintrag.anhaengen({"typ": "probe", "antrag": antrag.pk, "nr": n})

    vollstaendig = archivkern.audit_spur(antrag)
    assert len(vollstaendig) >= 70, "ohne Grenze kommt alles"
    assert len(archivkern.audit_spur(antrag, grenze=60)) == 60, "mit Grenze kürzt sie"

    import json

    daten = json.loads(archivkern.als_json(antrag))
    assert len(daten["audit"]) == len(vollstaendig), "der Export trägt jedes Ereignis"
    nummern = [e["lfd"] for e in daten["audit"]]
    assert nummern == sorted(nummern) and len(set(nummern)) == len(nummern)


# ── Archiv: Auswertung mit der Schwelle ihrer Zeit, Beiträge auf Wunsch (Befund #22, #42) ───


def _register(schluessel, wert):
    from parameter.models import Parameter

    Parameter.objects.update_or_create(
        schluessel=schluessel, defaults={"wert": str(wert), "beschreibung": "Test", "quelle": "Test"}
    )


def _abgeschlossene_runde(ordnung, ja=6, nein=4):  # noqa: F811
    """Eine archivierte Vorschlagsrunde 1 mit einem Systembeitrag, der ja:nein Reaktionen trägt."""
    from django.utils import timezone

    from verfahren.models import AuditEintrag, Kommentar, Reaktion

    antrag = _antrag(ordnung, mitglied_anlegen("stellerin"))
    passt = Kommentar.objects.create(
        antrag=antrag, mitglied=None, text=chatkern.passt_alles_text(), phase="vorschlag-r1", system=True,
        erstellt_am=timezone.now(), archiviert_am=timezone.now(),
    )
    for i in range(ja + nein):
        Reaktion.objects.create(
            kommentar=passt, mitglied=mitglied_anlegen(f"u{i}"), art="zustimmung" if i < ja else "ablehnung"
        )
    return antrag, AuditEintrag


RECHNUNG_ANGENOMMEN = (
    "Vorschlag des Expertenrats angenommen („Passt alles“ 6:4 = 60 % (Schwelle 50 %), "
    "an erster Stelle, Regel engagement-v1, Runde 1, § 5 Abs 12)."
)
RECHNUNG_ZURUECK = (
    "Der Abstimmungs-Chat gibt zurück: „Passt alles“ 4:6 = 40 % (Schwelle 30 %), "
    "an erster Stelle, Regel engagement-v1. 0 Kritik-Beiträge gehen als Wünsche an den Expertenrat."
)


def test_alte_vorschlagsrunde_rechnet_mit_der_schwelle_ihrer_entscheidung(ordnung):  # noqa: F811
    """Befund #22: `_auswertung` nahm für jede alte Runde den heutigen Registerwert. Runde 1 wurde
    mit 6:4 = 60 % bei Schwelle 50 % angenommen (so steht es im Audit); hebt die Verwaltung die
    Schwelle später auf 70 %, zeigte das Archiv „zurückgegeben“ — ein Widerspruch zur Audit-Spur
    derselben Seite. Jetzt gilt die Schwelle aus dem Ereignis, das die Runde beendet hat."""
    antrag, AuditEintrag = _abgeschlossene_runde(ordnung)
    AuditEintrag.anhaengen(
        {"typ": "phasenwechsel", "antrag": antrag.pk, "neue_phase": "abstimmung", "grund": RECHNUNG_ANGENOMMEN}
    )
    _register("vorschlag-annahme-prozent", 70)
    block = next(b for b in archivkern.zeitleiste(antrag) if b["phase"] == "vorschlag-r1")
    assert block["auswertung"]["angenommen"] is True
    assert block["auswertung"]["schwelle"] == 0.5 and block["auswertung"]["schwelle_quelle"] == "audit"
    assert block["auswertung"]["prozent"] == 60
    assert archivkern.schwelle_der_runde(antrag, 2) is None, "für Runde 2 ist nichts überliefert"


def test_zurueckgegebene_runde_nimmt_die_schwelle_aus_dem_rueckgabe_ereignis(ordnung):  # noqa: F811
    """`zurueck_an_gruppe_1` zählt die Runde hoch, bevor es das Ereignis anhängt — das Ereignis
    zur Rückgabe von Runde 1 trägt darum runde=2. Ein strukturiertes Feld `auswertung`
    (sobald der Kern es schreibt) wird bevorzugt gelesen."""
    antrag, AuditEintrag = _abgeschlossene_runde(ordnung, ja=4, nein=6)
    AuditEintrag.anhaengen(
        {
            "typ": "vorschlag_zurueckgegeben", "antrag": antrag.pk, "runde": 2, "grund": RECHNUNG_ZURUECK,
            "auswertung": {"schwelle": 0.3, "angenommen": True},
        }
    )
    _register("vorschlag-annahme-prozent", 50)
    assert archivkern.schwelle_der_runde(antrag, 1) == 0.3
    block = next(b for b in archivkern.zeitleiste(antrag) if b["phase"] == "vorschlag-r1")
    assert block["auswertung"]["angenommen"] is True and block["auswertung"]["schwelle"] == 0.3


def test_ohne_ueberlieferung_gilt_das_register_und_sagt_es(ordnung):  # noqa: F811
    antrag, _audit = _abgeschlossene_runde(ordnung)
    _register("vorschlag-annahme-prozent", 70)
    block = next(b for b in archivkern.zeitleiste(antrag) if b["phase"] == "vorschlag-r1")
    assert block["auswertung"]["schwelle"] == 0.7 and block["auswertung"]["schwelle_quelle"] == "register"


def test_archiv_zeigt_anzahl_und_laedt_beitraege_je_phase(client, ordnung):  # noqa: F811
    """Befund #42: Die Zeitleiste trug alle Beiträge aller Phasen bei jedem Aufruf. Jetzt trägt
    jeder Block seine Anzahl; die Beiträge kommen über ?archiv=<phase> (Link ohne JavaScript,
    hx-get mit) — der Export bleibt vollständig (Grundregel 7)."""
    antrag, _leute, _wurzel = _lage(ordnung)
    bloecke = {b["phase"]: b for b in archivkern.zeitleiste(antrag)}
    assert bloecke["unterstuetzung"]["anzahl"] == 2 and bloecke["unterstuetzung"]["beitraege"] == []
    assert bloecke["unterstuetzung"]["geladen"] is False
    geoeffnet = {b["phase"]: b for b in archivkern.zeitleiste(antrag, geoeffnet="unterstuetzung")}
    assert len(geoeffnet["unterstuetzung"]["beitraege"]) == 2 and geoeffnet["unterstuetzung"]["geladen"] is True
    assert geoeffnet["beratung"]["beitraege"] == [], "nur die angefragte Phase"
    alles = {b["phase"]: b for b in archivkern.zeitleiste(antrag, alles=True)}
    assert len(alles["unterstuetzung"]["beitraege"]) == 2 and len(alles["beratung"]["beitraege"]) == 1

    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    zone = seite.split('id="zone-archiv"', 1)[1]
    assert f'href="/antrag/{antrag.pk}/?archiv=unterstuetzung#archiv-unterstuetzung"' in zone
    assert 'hx-select="#archiv-unterstuetzung"' in zone
    assert "sie stehen auch oben im Chat" in zone, "die laufende Phase verweist auf den Faden"
    assert "Sehe ich auch so." not in zone
    daten = json.loads(archivkern.als_json(antrag))
    assert sum(len(b["beitraege"]) for b in daten["zeitleiste"]) == 3, "der Export trägt alles"
