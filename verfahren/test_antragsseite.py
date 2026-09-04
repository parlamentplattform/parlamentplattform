"""S5 — die Antragsseite in drei Zonen (FB-F1, FB-F2, FB-F4): Kopf, Reiterleiste, Zone „Text"
mit Handlungskarte und lesbaren Regeln, Zone „Einschätzung" mit Kopfkarte und Beanstanden,
Zone „Chat"; bei Personenwahlen entfällt die Einschätzung."""

import pytest
from django.urls import reverse

from verfahren.models import Antrag, AuditEintrag, Beanstandung, Kategorie, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _seite(client, antrag):
    return client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()


def test_drei_zonen_mit_reiterleiste(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    inhalt = _seite(client, antrag)
    assert 'x-data="zonen"' in inhalt and 'class="zonenleiste"' in inhalt
    for zone in ("zone-text", "zone-einschaetzung", "zone-chat"):
        assert f'href="#{zone}"' in inhalt, zone
        assert f'id="{zone}"' in inhalt or zone == "zone-einschaetzung"
    assert inhalt.count('class="zreiter"') == 3
    # Ohne JavaScript sind die Reiter gewöhnliche Ankerlinks und alle Zonen stehen da
    assert 'class="zone z-text"' in inhalt and 'class="zone z-chat"' in inhalt
    assert "oninput" not in inhalt and "onclick" not in inhalt


def test_zone_text_zeigt_wortlaut_handlung_und_lesbare_regeln(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    client.force_login(anna)
    inhalt = _seite(client, antrag)
    assert ANTRAG["wortlaut"] in inhalt and 'class="text-lang"' in inhalt
    assert 'class="karte handlung"' in inhalt and "Diesen Antrag unterstützen" in inhalt
    # Die eingefrorenen Regeln stehen lesbar, das JSON nur noch unter „Rohdaten“ (FB-F1)
    assert "Eingefrorene Regeln (§ 5 Abs 5)" in inhalt
    assert "Unterstützungsschwelle" in inhalt and "Mindestbeteiligung" in inhalt and "5 %" in inhalt
    assert "Ja mehr als Nein" in inhalt
    assert 'class="klappe roh"' in inhalt and "Rohdaten" in inhalt
    kopf = inhalt.split('class="zonen"')[0]
    assert "policy_snapshot" not in kopf and "unterstuetzung_schwelle" not in kopf


def test_zone_einschaetzung_zeigt_kennzeichnung_und_leerzustand(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    inhalt = _seite(client, antrag)
    assert "Modellrechnung — sie schlägt vor, sie entscheidet nie" in inhalt
    assert "kein Anbieter angeschlossen" in inhalt  # ohne Schlüssel wird nichts gerechnet
    assert "Was hier stehen wird:" in inhalt and inhalt.count('class="skelett-karte"') == 5
    for karte in ("Berührte Gesetze", "Aufwand, Last und Dauer", "Ausschreibung"):
        assert karte in inhalt, karte
    assert "/beanstanden/" not in inhalt  # Gäste beanstanden nicht
    client.force_login(anna)
    angemeldet = _seite(client, antrag)
    assert f'action="/antrag/{antrag.pk}/beanstanden/"' in angemeldet and 'class="beanstanden"' in angemeldet


def test_beanstandung_ist_oeffentlich_und_auditiert(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    client.force_login(bernd)
    vorher = AuditEintrag.objects.count()
    antwort = client.post(
        reverse("verfahren:beanstanden", args=[antrag.pk]),
        {"text": "Die Zahl der betroffenen Normen stimmt nicht.", "weiter": f"/antrag/{antrag.pk}/"},
    )
    assert antwort.status_code == 302 and antwort.url == f"/antrag/{antrag.pk}/"
    beanstandung = Beanstandung.objects.get()
    assert beanstandung.mitglied == bernd and beanstandung.lauf is None
    assert AuditEintrag.objects.count() == vorher + 1
    assert AuditEintrag.objects.order_by("-lfd").first().ereignis["art"] == "einschaetzung_beanstandet"
    client.logout()
    inhalt = _seite(client, antrag)  # öffentlich sichtbar, mit Namen
    assert "Die Zahl der betroffenen Normen stimmt nicht." in inhalt and bernd.anzeigename in inhalt
    # Leerer Text wird abgewiesen
    client.force_login(bernd)
    client.post(reverse("verfahren:beanstanden", args=[antrag.pk]), {"text": "   "})
    assert Beanstandung.objects.count() == 1
    assert client.get(reverse("verfahren:beanstanden", args=[antrag.pk])).status_code == 405


def test_personenwahl_ohne_einschaetzungszone(client, ordnung):  # noqa: F811
    """FB-F4: Über Menschen rechnet keine Maschine — der Reiter entfällt."""
    from verfahren.models import Antragsart

    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, "Listenreihung Gemeinderat", "Wortlaut.", "", ordnung, art=Antragsart.MANDAT)
    inhalt = _seite(client, antrag)
    assert 'href="#zone-einschaetzung"' not in inhalt and inhalt.count('class="zreiter"') == 2
    assert "Modellrechnung" not in inhalt
    assert "Mandats-Kandidatur" in inhalt and 'class="avatar-initiale"' not in inhalt  # noch keine Bewerbung


def test_kopf_traegt_chips_stern_und_hervorhebung(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    energie = Kategorie.objects.create(slug="energie", name="Energie")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung, ebene="gemeinde", gebiet="Wels")
    antrag.kategorien.add(energie)
    Antrag.objects.filter(pk=antrag.pk).update(hervorgehoben=True, hervorhebung_begruendung="Beschluss IR-1.")
    inhalt = _seite(client, antrag)
    assert 'class="a-chips"' in inhalt and "Gemeinde · Wels" in inhalt
    assert 'href="/parlament/?fach=energie#feld-favoriten"' in inhalt
    assert 'class="stern aus gast"' in inhalt  # der Stern steht auch für Gäste (FB-C4)
    assert 'class="band-gold"' in inhalt and "Beschluss IR-1." in inhalt


def test_alle_fassungen_nur_wenn_es_mehrere_gibt(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    assert "Alle Fassungen" not in _seite(client, antrag)
    antrag.fassungen.create(nummer=2, wortlaut="Zweite Fassung des Wortlauts.", begruendung="")
    inhalt = _seite(client, antrag)
    assert "Alle Fassungen (2)" in inhalt and "Zweite Fassung des Wortlauts." in inhalt
