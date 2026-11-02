"""Aktueller Wartestatus, historische Herkunft und vollständige öffentliche Exporte."""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from gremien.models import EntwurfsFassung
from ki.models import KIAuftrag, KILauf, Zweck
from ki.nachlese import antrag_export, lauf_export, textstand
from ki.rechtsbezug import rechtsbezug_lage
from ki.test_kontext import vorschlag
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from parameter.models import Parameter
from verfahren.archiv import als_json, als_markdown
from verfahren.models import Antragsart, AntragsFassung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def erfolg(antrag):
    auftrag = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    assert auftrag_ausfuehren(auftrag.pk) == "erledigt"
    auftrag.refresh_from_db()
    return auftrag


def test_neuer_vorschlag_wartet_sichtbar_trotz_altem_ergebnis(a, client):  # noqa: F811
    alt = erfolg(a)
    neu = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=vorschlag(a))
    lage = rechtsbezug_lage(a)
    assert lage["zustand"] == "wartet" and lage["ergebnis"] is None
    assert lage["auftrag"].pk == neu.pk
    assert lage["historie"][0]["lauf"].pk == alt.lauf_id
    assert lage["historie"][0]["frueher"]
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Vorschlag des Expertenrats · Fassung 1" in html
    assert "Frühere Einschätzungen und Fehlversuche" in html and alt.kontext["sha256"] in html


def test_neuer_vorschlag_ohne_anbieter_verdeckt_alte_ergebnisse_nicht(a, settings):  # noqa: F811
    erfolg(a)
    einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=vorschlag(a))
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    lage = rechtsbezug_lage(a)
    assert lage["zustand"] == "nicht_angeschlossen" and lage["ergebnis"] is None
    assert lage["historie"].paginator.count == 1


def test_ergebnis_des_vorschlags_ist_nicht_mit_antrag_fassung1_verwechselt(a):  # noqa: F811
    alt = erfolg(a)
    neu = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=vorschlag(a))
    assert auftrag_ausfuehren(neu.pk) == "erledigt"
    lage = rechtsbezug_lage(a)
    assert lage["zustand"] == "erledigt"
    assert lage["ergebnis"]["textstand"]["quellenart"] == "vorschlag"
    assert not lage["ergebnis"]["frueher"]
    assert lage["historie"][0]["lauf"].pk == alt.lauf_id
    assert lage["historie"][0]["textstand"]["quellenart"] == "antrag"


def test_historie_ist_blaetterbar_export_bleibt_vollstaendig_ohne_n_plus_eins(a):  # noqa: F811
    erfolg(a)
    for nummer in (2, 3, 4):
        AntragsFassung.objects.create(antrag=a, nummer=nummer, wortlaut=f"Öffentlicher Text {nummer}")
        erfolg(a)
    Parameter.objects.create(
        schluessel="ki-einschaetzungen-je-seite", wert="1", beschreibung="Test", quelle="Test",
    )
    with CaptureQueriesContext(connection) as abfragen:
        erste = rechtsbezug_lage(a)
    assert len(erste["historie"]) == 1 and erste["historie"].paginator.count == 3
    assert len([q for q in abfragen if 'FROM "verfahren_antragsfassung"' in q["sql"]]) == 1
    assert rechtsbezug_lage(a, seite=2)["historie"][0]["fassung"] == 2
    assert len(antrag_export(a)["laeufe"]) == 4


def test_oeffentlicher_export_enthaelt_keine_internen_gremien_eingaben(a, client):  # noqa: F811
    oeffentlich = erfolg(a)
    intern = KILauf.objects.create(
        antrag=a, zweck=Zweck.EINSCHAETZUNG, angefordert_von=a.eingebracht_von,
        eingabe="NICHT_OEFFENTLICHER_ARBEITSSTAND", antwort="INTERNER_ENTWURF", anbieter="attrappe", modell="m",
    )
    daten = json.loads(als_json(a))
    assert daten["rechtsbezug"]["laeufe"][0]["kontext"]["text"] == oeffentlich.kontext
    assert "NICHT_OEFFENTLICHER_ARBEITSSTAND" not in als_json(a) + als_markdown(a)
    assert oeffentlich.kontext["sha256"] in als_markdown(a)
    with pytest.raises(ValueError):
        lauf_export(intern)
    html = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "NICHT_OEFFENTLICHER_ARBEITSSTAND" not in html
    assert oeffentlich.kontext["sha256"] in html


def test_alte_laeufe_werden_beim_lesen_nicht_nachtraeglich_beschriftet(a):  # noqa: F811
    alt = KILauf.objects.create(
        antrag=a, zweck=Zweck.RECHTSBEZUG, angefordert_von=a.eingebracht_von,
        eingabe="Alter öffentlicher Antragstext", antwort="Frühere Antwort", anbieter="a", modell="m",
    )
    assert not textstand(alt)["festgehalten"]
    assert rechtsbezug_lage(a)["ergebnis"]["lauf"].pk == alt.pk
    antrag_export(a)
    alt.refresh_from_db()
    assert alt.kontext == {} and alt.eingabe == "Alter öffentlicher Antragstext"


def test_unfertige_arbeitsfassung_darf_nicht_in_oeffentliche_warteschlange(a):  # noqa: F811
    f = vorschlag(a)
    arbeit = EntwurfsFassung.objects.create(
        entwurf=f.entwurf, nummer=2, wortlaut="Nicht eingereichter Arbeitsstand", verfasst_von=a.eingebracht_von,
    )
    with pytest.raises(ValueError, match="eingereichte"):
        einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=arbeit)
    assert not KIAuftrag.objects.exists()


def test_frueher_eingereihte_fassung_bleibt_nach_neuer_veroeffentlichung_idempotent(a):  # noqa: F811
    f = vorschlag(a)
    alt = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=f)
    f.entwurf.eingereichte_fassung = 99
    f.entwurf.save(update_fields=["eingereichte_fassung"])
    assert einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=f).pk == alt.pk


@pytest.mark.parametrize("art", [Antragsart.MANDAT, Antragsart.VERTRAUENSFRAGE])
def test_keine_einschaetzung_ueber_personen(a, art):  # noqa: F811
    a.art = art
    with pytest.raises(ValueError, match="Personen"):
        einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert not KIAuftrag.objects.exists()


def test_fehlende_legacyfassung_ruft_keinen_anbieter_mit_aktuellem_text_auf(a):  # noqa: F811
    auftrag = KIAuftrag.objects.create(
        zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von, fassung_nummer=999,
    )
    assert auftrag_ausfuehren(auftrag.pk) == "verschoben"
    auftrag.refresh_from_db()
    assert auftrag.lauf_id is None and not KILauf.objects.exists()


def test_persoenlicher_export_traegt_die_eigenen_kontextfelder(a):  # noqa: F811
    from mitglieder.profil import daten_export

    auftrag = erfolg(a)
    daten = daten_export(a.eingebracht_von)
    assert daten["ki_auftraege"][0]["kontext"] == auftrag.kontext
    assert daten["ki_auftraege"][0]["quellenart"] == "antrag"
    assert daten["ki_laeufe"][0]["kontext"]["text"] == auftrag.kontext
