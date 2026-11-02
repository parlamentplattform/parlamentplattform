"""Öffentliche Nachlese und Export unterscheiden Formatfehler von gültig leer."""

import hashlib
import json

import pytest
from django.urls import reverse

from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import Zweck
from ki.warteschlange import abarbeiten, einreihen
from plattform_core.modellantwort import schema_hash
from verfahren.archiv import als_json
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def mit_antwort(settings, monkeypatch, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    person = mitglied_anlegen()
    def erzeugen(daten):
        roh = daten if isinstance(daten, str) else json.dumps(daten)
        monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(roh, "attrappe-format", 10, 20))
        antrag = antrag_einbringen(person, **ANTRAG, ordnung=ordnung)
        auftrag = einreihen(Zweck.RECHTSBEZUG, antrag, person)
        assert abarbeiten()["erledigt"] == 1
        auftrag.refresh_from_db()
        return antrag, auftrag.lauf, roh
    return erzeugen


def test_falscher_feldtyp_ist_keine_behauptung_das_modell_kenne_keine_norm(client, mit_antwort):
    a, lauf, roh = mit_antwort({"normen": "keine Liste", "unsicherheit": "extrem"})
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Modellantwort weicht" in html and "keine verlässliche Normenliste" in html
    assert "nicht angegeben" in html
    assert "keine Norm genannt" not in html and "leere Normenliste" not in html
    assert "Aktuelle Formprüfung" in html and "kein früherer Prüfnachweis" in html
    assert reverse("verfahren:antwortformat") in html
    export = json.loads(als_json(a))
    erhalten = export["rechtsbezug"]["laeufe"][0]
    assert erhalten["antwort"] == roh
    assert erhalten["antwortformat"]["antwort_sha256"] == hashlib.sha256(roh.encode()).hexdigest()
    assert erhalten["antwortformat"]["zeitbezug"] == "darstellung"
    lauf.refresh_from_db()
    assert lauf.antwort == roh and "antwortformat" not in lauf.kontext


def test_gueltig_leer_bestaetigt_keine_rechtliche_unbedenklichkeit(client, mit_antwort):
    a, _, _ = mit_antwort({"normen": [], "hinweis": "", "unsicherheit": "hoch"})
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "leere Normenliste" in html and "keine Bestätigung" in html
    assert "Modellantwort weicht" not in html


@pytest.mark.parametrize("normen,gueltig", [([], True), ("kein Array", False)])
def test_nachricht_verwechselt_ein_formproblem_nicht_mit_inhaltlicher_leere(mit_antwort, mailoutbox, normen, gueltig):
    from mitglieder.post import rechtsbezug_brief

    antrag, _, _ = mit_antwort({"normen": normen, "hinweis": "", "unsicherheit": "hoch"})
    mailoutbox.clear()
    assert rechtsbezug_brief(antrag.eingebracht_von, antrag)
    text = mailoutbox[-1].body
    assert "keine Norm genannt" not in text
    assert ("Modellantwort weicht" not in text) == gueltig
    assert ("leere Normenliste" in text) == gueltig
    assert ("keine verlässliche Normenliste" in text) != gueltig


def test_unicode_feld_und_html_werden_sicher_gezeigt(client, mit_antwort):
    a, _, _ = mit_antwort({"normen": [{"titel": "\ud800<script>Test</script>", "aenderung": "unbekannt"}]})
    antwort = client.get(reverse("verfahren:antrag", args=[a.pk]))
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert "&lt;script&gt;" in html and "<script>Test</script>" not in html
    assert "unklar" in html and "Modellantwort weicht" in html


def test_schema_ist_oeffentlich_und_nur_lesend_mit_nachrechenbarer_pruefsumme(client):
    url = reverse("verfahren:antwortformat")
    antwort = client.get(url)
    assert antwort.status_code == 200 and antwort["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in antwort["Content-Disposition"]
    kanonisch = json.dumps(antwort.json(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(kanonisch).hexdigest() == schema_hash()
    assert client.post(url, {}).status_code == 405
