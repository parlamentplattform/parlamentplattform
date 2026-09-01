"""Kategorienbaum (F-45: eine Wurzel, vier Säulen), Abos mit Ast-Wirkung (F-46),
automatische Zuordnung (F-47) und die Fokus-Ansicht mit Suche."""

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
    assert anzahl >= 300  # Wurzel, Säulen, Bereiche, Haupt-, Unter- und Detailkategorien
    call_command("kategorien_laden")  # zweiter Lauf ändert nichts
    assert Kategorie.objects.count() == anzahl

    # Verschwindet ein Slug aus der Datei, wird er deaktiviert, nie gelöscht.
    Kategorie.objects.create(slug="altbereich", name="Alt", reihenfolge=999)
    call_command("kategorien_laden")
    assert Kategorie.objects.get(slug="altbereich").aktiv is False


def test_baum_fuehrt_auf_eine_wurzel_zurueck():
    """Michaels Leitbild: wenige Säulen, die alles abbilden — und am Ende führt
    alles auf „Das gesellschaftliche Zusammenleben“ zurück."""
    call_command("kategorien_laden")
    wurzeln = Kategorie.objects.filter(eltern=None, aktiv=True)
    assert wurzeln.count() == 1
    wurzel = wurzeln.get()
    assert wurzel.name == "Das gesellschaftliche Zusammenleben"
    assert wurzel.kinder.count() == 4  # die vier Säulen
    assert sum(s.kinder.count() for s in wurzel.kinder.all()) == 12  # zwölf Bereiche

    # Jede Kategorie hängt an der Wurzel — keine Waisen, keine zweite Wurzel.
    for k in Kategorie.objects.filter(aktiv=True).exclude(pk=wurzel.pk):
        assert k.pfad.startswith("Das gesellschaftliche Zusammenleben › ")

    # Slugs der Version 1 sind stabil geblieben (Favoriten überleben den Umbau).
    for slug in ("energie", "umwelt-klima", "installateur", "wirtschaft-unternehmen"):
        assert Kategorie.objects.filter(slug=slug, aktiv=True).exists()


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
    zugeordnet = kategorien_zuordnen(antrag)
    kurz = [k.pfad_kurz for k in zugeordnet]
    assert "Wirtschaft & Unternehmen › Bauwirtschaft & Baugewerbe › Installateur & Gebäudetechnik" in kurz
    # Der volle Pfad läuft bis zur Wurzel; Wurzel/Säulen selbst werden nie zugeordnet.
    assert all(k.pfad.startswith("Das gesellschaftliche Zusammenleben") for k in zugeordnet)
    assert all(k.tiefe >= 3 for k in zugeordnet)


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
    antwort = client.get(reverse("verfahren:parlament"))
    assert antrag in list(antwort.context["themen_neu"])  # Ast-Wirkung

    client.post(reverse("verfahren:kategorie_abonnieren", args=[energie.slug]))  # Abo beenden
    assert anna.kategorie_abos.count() == 0


# --- Fokus-Ansicht (F-45): Brotkrume, Hineinklicken, Suche ------------------------


def test_fokus_ansicht_zaehlt_laufende_je_ast_ueber_alle_ebenen(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    erneuerbar = Kategorie.objects.get(slug="erneuerbare-energie")
    a = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    a.kategorien.add(erneuerbar)

    # Die Zählung wandert den ganzen Stamm hinauf — bis in Säule und Wurzel.
    antwort = client.get(reverse("verfahren:kategorie", args=["energie"]))
    assert antwort.context["laufend_gesamt"] == 1
    antwort = client.get(reverse("verfahren:kategorien"))  # Wurzel
    assert antwort.context["laufend_gesamt"] >= 1
    assert antwort.context["ist_wurzel"] is True
    assert len(antwort.context["kinder"]) == 4  # die vier Säulen als Karten


def test_fokus_ansicht_zeigt_stamm_und_unterbereiche(client):
    call_command("kategorien_laden")
    antwort = client.get(reverse("verfahren:kategorie", args=["installateur"]))
    stamm = [k.slug for k in antwort.context["stamm"]]
    assert stamm[0] == "gesellschaftliches-zusammenleben"  # Brotkrume beginnt an der Wurzel
    assert "wirtschaft-unternehmen" in stamm
    inhalt = antwort.content.decode()
    assert "Das gesellschaftliche Zusammenleben" in inhalt  # Stamm ist verlinkt sichtbar
    assert "Installateur" in inhalt


def test_suche_findet_kategorie_ueber_name_und_schlagwort(client):
    call_command("kategorien_laden")
    antwort = client.get(reverse("verfahren:kategorien"), {"q": "Installateur"})
    treffer = [t["k"].slug for t in antwort.context["treffer"]]
    assert "installateur" in treffer
    antwort = client.get(reverse("verfahren:kategorien"), {"q": "gibtesnicht123"})
    assert antwort.context["treffer"] == []
    assert "Nichts gefunden" in antwort.content.decode()


def test_favorisieren_aus_der_fokus_ansicht_fuehrt_zurueck(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    anna = mitglied_anlegen()
    client.force_login(anna)
    antwort = client.post(
        reverse("verfahren:kategorie_abonnieren", args=["saeule-lebensraum-infrastruktur"]),
        {"weiter": "/kategorien/saeule-lebensraum-infrastruktur/"},
    )
    assert antwort.url == "/kategorien/saeule-lebensraum-infrastruktur/"
    assert anna.kategorie_abos.count() == 1  # eine Säule favorisiert = ganzer Ast (F-46)
