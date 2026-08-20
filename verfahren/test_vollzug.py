"""Das Umsetzungsregister (F-55, § 6 Abs 10): öffentlich, append-only, auditiert."""

import json

import pytest
from django.urls import reverse

from verfahren.models import (
    Antrag,
    AuditEintrag,
    Vollzugseintrag,
    antrag_einbringen,
    stimme_abgeben,
    vollzug_fortschreiben,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def angenommenen_antrag(ordnung):  # noqa: F811
    """Ein Antrag, der den ganzen Weg gegangen ist und angenommen wurde."""
    from datetime import timedelta

    from django.utils import timezone

    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    for person, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        stimme_abgeben(antrag, person, wahl)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    assert antrag.phase == "angenommen"
    return antrag, leute


def admin_anlegen():
    m = mitglied_anlegen("admina")
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    return m


def test_register_zeigt_angenommene_mit_stand_offen(client, ordnung):  # noqa: F811
    antrag, _leute = angenommenen_antrag(ordnung)
    antwort = client.get(reverse("verfahren:umsetzung"))
    assert antwort.status_code == 200  # öffentlich, ohne Anmeldung (§ 6 Abs 10)
    inhalt = antwort.content.decode()
    assert antrag.titel in inhalt
    assert "offen" in inhalt  # ohne Eintrag gilt der Stand als offen
    assert antwort.context["zeilen"][0]["status"] == "offen"


def test_fortschreiben_nur_fuer_admins_und_nur_angenommene(client, ordnung):  # noqa: F811
    antrag, leute = angenommenen_antrag(ordnung)
    url = reverse("verfahren:vollzug", args=[antrag.pk])

    client.force_login(leute[0])  # normales Mitglied
    assert client.post(url, {"status": "in_umsetzung"}).status_code == 403
    assert Vollzugseintrag.objects.count() == 0

    chefin = admin_anlegen()
    client.force_login(chefin)
    antwort = client.post(url, {"status": "in_umsetzung", "vermerk": "Arbeitsgruppe eingesetzt."})
    assert antwort.status_code == 302
    eintrag = Vollzugseintrag.objects.get()
    assert (eintrag.status, eintrag.vermerk, eintrag.durch) == (
        "in_umsetzung",
        "Arbeitsgruppe eingesetzt.",
        chefin,
    )
    assert AuditEintrag.objects.filter(ereignis__typ="vollzug").exists()  # auditiert (F-22)

    laufend = antrag_einbringen(leute[0], "Zweiter Antrag", "Wortlaut.", "", ordnung)
    client.post(reverse("verfahren:vollzug", args=[laufend.pk]), {"status": "offen"})
    assert laufend.vollzug.count() == 0  # nur angenommene Anträge (§ 6 Abs 10)


def test_historie_ist_append_only_und_juengster_eintrag_zaehlt(client, ordnung):  # noqa: F811
    antrag, leute = angenommenen_antrag(ordnung)
    chefin = admin_anlegen()
    vollzug_fortschreiben(antrag, chefin, "in_umsetzung", "Los geht es.")
    vollzug_fortschreiben(antrag, chefin, "blockiert", "Warten auf Kostenvoranschlag.")
    vollzug_fortschreiben(antrag, chefin, "umgesetzt", "Anlage montiert.")
    assert antrag.vollzug.count() == 3  # nichts überschrieben
    assert antrag.vollzugsstand().status == "umgesetzt"

    antwort = client.get(reverse("verfahren:antrag", args=[antrag.pk]))
    inhalt = antwort.content.decode()
    assert "Warten auf Kostenvoranschlag." in inhalt  # volle Geschichte auf der Ergebnisseite
    assert "Anlage montiert." in inhalt


def test_filter_und_json_export(client, ordnung):  # noqa: F811
    antrag, _leute = angenommenen_antrag(ordnung)
    vollzug_fortschreiben(antrag, admin_anlegen(), "blockiert", "Budget offen.")

    gefiltert = client.get(reverse("verfahren:umsetzung"), {"status": "umgesetzt"})
    assert gefiltert.context["zeilen"] == []  # Filter greift
    gefiltert = client.get(reverse("verfahren:umsetzung"), {"status": "blockiert"})
    assert len(gefiltert.context["zeilen"]) == 1

    daten = json.loads(client.get(reverse("verfahren:umsetzung_json")).content)
    assert daten["register"][0]["status"] == "blockiert"
    assert daten["register"][0]["historie"][0]["vermerk"] == "Budget offen."  # F-23: exportierbar


def test_formular_erscheint_nur_fuer_admins(client, ordnung):  # noqa: F811
    antrag, leute = angenommenen_antrag(ordnung)
    client.force_login(leute[0])
    assert (
        "Stand fortschreiben"
        not in client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    )
    client.force_login(admin_anlegen())
    assert "Stand fortschreiben" in client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
