"""Kategorienbaum (F-45), Abos mit Ast-Wirkung (F-46) und automatische Zuordnung (F-47)."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from verfahren.models import Antrag, Kategorie, antrag_einbringen, kategorien_zuordnen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def test_kategorien_laden_ist_idempotent_und_deaktiviert_statt_zu_loeschen():
    call_command("kategorien_laden")
    anzahl = Kategorie.objects.count()
    assert anzahl >= 100  # Baum: Haupt-, Unter- und Detailkategorien
    assert Kategorie.objects.filter(eltern=None).count() >= 20  # Hauptkategorien
    call_command("kategorien_laden")  # zweiter Lauf ändert nichts
    assert Kategorie.objects.count() == anzahl

    # Verschwindet ein Slug aus der Datei, wird er deaktiviert, nie gelöscht.
    Kategorie.objects.create(slug="altbereich", name="Alt", reihenfolge=999)
    call_command("kategorien_laden")
    assert Kategorie.objects.get(slug="altbereich").aktiv is False


def test_zuordnung_findet_die_tiefste_passende_ebene(ordnung):  # noqa: F811
    """Michaels Beispiel: eine Norm für Rohrmaße gehört zu
    Wirtschaft › Bauwirtschaft › Installateur — nicht bloß zu „Wirtschaft“."""
    call_command("kategorien_laden")
    antrag = antrag_einbringen(
        mitglied_anlegen(),
        "Aussetzung der Norm für Rohrmaße",
        "Die Norm über zulässige Rohrmaße wird ausgesetzt; Installateure dürfen bewährte Maße verwenden.",
        "",
        ordnung,
    )
    pfade = [k.pfad for k in kategorien_zuordnen(antrag)]
    assert "Wirtschaft & Unternehmen › Bauwirtschaft & Baugewerbe › Installateur & Gebäudetechnik" in pfade
    assert all("›" in p or p.count("›") == 0 for p in pfade)
    # Der Elternknoten wird nicht zusätzlich vergeben — der Baum impliziert ihn.
    assert "Wirtschaft & Unternehmen" not in pfade


def test_einbringen_ordnet_automatisch_zu_ohne_nutzereingabe(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    client.force_login(mitglied_anlegen())
    client.post(
        reverse("verfahren:einbringen"),
        {
            "titel": "Photovoltaik auf allen Schuldächern",
            "wortlaut": "Auf den Dächern aller Schulen werden Photovoltaikanlagen errichtet.",
            "begruendung": "",
        },
    )
    antrag = Antrag.objects.get()
    slugs = {k.slug for k in antrag.kategorien.all()}
    assert "erneuerbare-energie" in slugs  # KI hat zugeordnet, niemand hat etwas angekreuzt
    audit_typen = [
        e.ereignis["typ"]
        for e in __import__("verfahren.models", fromlist=["AuditEintrag"]).AuditEintrag.objects.all()
    ]
    assert "kategorien_zugeordnet" in audit_typen  # nachvollziehbar protokolliert


def test_abo_eines_astes_umfasst_unterkategorien(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    energie = Kategorie.objects.get(slug="energie")
    erneuerbar = Kategorie.objects.get(slug="erneuerbare-energie")
    assert erneuerbar.eltern_id == energie.pk

    autorin, anna = mitglied_anlegen("autorin"), mitglied_anlegen()
    antrag = antrag_einbringen(autorin, **ANTRAG, ordnung=ordnung)
    antrag.kategorien.add(erneuerbar)  # Antrag hängt am KIND-Knoten

    client.force_login(anna)
    client.post(reverse("verfahren:kategorie_abonnieren", args=[energie.slug]))  # Abo am ELTERN-Knoten
    antwort = client.get(reverse("verfahren:index"))
    assert antrag in list(antwort.context["themen_neu"])  # Ast-Wirkung

    client.post(reverse("verfahren:kategorie_abonnieren", args=[energie.slug]))  # Abo beenden
    assert anna.kategorie_abos.count() == 0


def test_kategorienbaum_zaehlt_laufende_je_ast(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    erneuerbar = Kategorie.objects.get(slug="erneuerbare-energie")
    a = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    a.kategorien.add(erneuerbar)
    antwort = client.get(reverse("verfahren:kategorien"))
    energie_knoten = next(k for k in antwort.context["baum"] if k["k"].slug == "energie")
    assert energie_knoten["laufend"] == 1  # Zählung schließt Unterkategorien ein
