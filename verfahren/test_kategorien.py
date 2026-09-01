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
    assert anna.kategorie_abos.count() == 1
    assert erneuerbar.pk in energie.nachfahren_ids()  # das Abo gilt für den ganzen Ast (F-46)

    client.post(reverse("verfahren:kategorie_abonnieren", args=[energie.slug]))  # Abo beenden
    assert anna.kategorie_abos.count() == 0


# --- Die Tiefen-Ansicht lebt jetzt als Suche im Feld (P2, Vorgabe 1.9. abends) ----


def test_feldsuche_zaehlt_laufende_je_ast_und_findet_schlagworte(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    erneuerbar = Kategorie.objects.get(slug="erneuerbare-energie")
    a = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    a.kategorien.add(erneuerbar)

    feld = (
        client.get(reverse("verfahren:parlament"), {"suche": "Energie"}).content.decode()
        .split('id="feld-favoriten"')[1].split("</section>")[0]
    )
    assert "laufendes Verfahren" in feld  # die Ast-Zählung wandert den Stamm hinauf
    feld = (
        client.get(reverse("verfahren:parlament"), {"suche": "Installateur"}).content.decode()
        .split('id="feld-favoriten"')[1].split("</section>")[0]
    )
    assert "Installateur" in feld  # Schlagwort-Suche wie in der alten Tiefen-Ansicht


def test_favorisieren_aus_der_suche_fuehrt_zurueck(client, ordnung):  # noqa: F811
    call_command("kategorien_laden")
    anna = mitglied_anlegen()
    client.force_login(anna)
    antwort = client.post(
        reverse("verfahren:kategorie_abonnieren", args=["saeule-lebensraum-infrastruktur"]),
        {"weiter": "/parlament/?suche=Infrastruktur"},
    )
    assert antwort.url == "/parlament/?suche=Infrastruktur"
    assert anna.kategorie_abos.count() == 1  # eine Säule favorisiert = ganzer Ast (F-46)
