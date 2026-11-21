"""Gegenüberstellung zweier erhaltener Inhalte, ohne Import oder Änderung."""

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

import pytest
from django.urls import reverse

from faktenbasis.models import Norm, NormText, RisImport
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

STAND = date(2026, 11, 1)
ERFASST = datetime(2026, 11, 2, 15, tzinfo=UTC)


def text_anlegen(text, *, tage=0, parser=1, xml=None, **herkunft):
    daten = {"ebene": "Bund", "bundesland": "", "gesetzesnummer": "10001597", **herkunft}
    ris_id = daten.pop("ris_id", "NOR40262691")
    stand = STAND + timedelta(days=tage)
    erfasst = ERFASST + timedelta(days=tage)
    lauf = RisImport.objects.create(stand=stand, beendet_am=erfasst, erfolgreich=True, **daten)
    quelle = f"https://ris.bka.gv.at/Dokumente/Bundesnormen/{ris_id}/{ris_id}.html"
    norm = Norm.objects.create(
        ris_id=ris_id, stand=stand, kurztitel="Synthetischer Quellenstand",
        quelle=quelle, rohdaten={}, inhalt_hash=sha256(str(lauf.pk).encode()).hexdigest(), importlauf=lauf,
        **daten,
    )
    inhalt = xml if xml is not None else f"<Dokument>Prüfstand {tage}</Dokument>".encode()
    return NormText.objects.create(
        norm=norm, quelle=quelle.replace(".html", ".xml"), xml=inhalt, text=text,
        xml_hash=sha256(inhalt).hexdigest(), parser_fassung=parser, erfasst_am=erfasst,
    )


@pytest.mark.parametrize("gleich_xml,gleich_text", [(False, False), (True, False), (False, True), (True, True)])
def test_pruefsumme_und_gespeicherten_wortlaut_getrennt_ausweisen(client, gleich_xml, gleich_text):
    alt = text_anlegen("Archivierter Ausgangstext <script>Beispiel</script>")
    neu = text_anlegen(
        alt.text if gleich_text else "Archivierter Vergleichstext",
        tage=1, parser=2, xml=bytes(alt.xml) if gleich_xml else None,
    )
    ziel = reverse("faktenbasis:textvergleich", args=[alt.pk, neu.pk])
    vorher = AuditEintrag.objects.count()
    antwort = client.get(ziel)
    assert antwort.status_code == 200
    assert antwort.context["pruefsumme_gleich"] is gleich_xml
    assert antwort.context["wortlaut_gleich"] is gleich_text
    assert antwort.context["texte"] == (alt, neu)
    html = antwort.content.decode()
    assert alt.xml_hash in html and neu.xml_hash in html
    assert "&lt;script&gt;Beispiel&lt;/script&gt;" in html
    assert "<script>Beispiel</script>" not in html
    for t in (alt, neu):
        assert reverse("faktenbasis:textxml", args=[t.pk]) in html
        assert f'{reverse("faktenbasis:norm", args=[t.norm_id])}?text={t.pk}#dokumenttext-{t.pk}' in html
    assert client.post(ziel, {"text": "anderer Text"}).status_code == 405
    assert AuditEintrag.objects.count() == vorher and NormText.objects.count() == 2


@pytest.mark.parametrize("herkunft", [
    {"ris_id": "NOR40139563"},
    {"gesetzesnummer": "10001234"},
    {"ebene": "Land"},
    {"bundesland": "Oberösterreich"},
])
def test_fremde_dokumentidentitaet_ist_auswahl_und_direktzugriff_verwehrt(client, herkunft):
    alt = text_anlegen("Ein Text")
    fremd = text_anlegen("Fremder Text", tage=1, **herkunft)
    normseite = client.get(reverse("faktenbasis:norm", args=[alt.norm_id]))
    auswahl = reverse("faktenbasis:textvergleich", args=[alt.pk])
    assert auswahl not in normseite.content.decode()
    assert "kein zweiter Dokumenttext gespeichert" in client.get(auswahl).content.decode()
    assert client.get(reverse("faktenbasis:textvergleich", args=[alt.pk, fremd.pk])).status_code == 404
    assert client.get(reverse("faktenbasis:textvergleich", args=[alt.pk, alt.pk])).status_code == 404


def test_auswahl_ist_auf_dem_normstand_erreichbar_und_begrenzt(client, monkeypatch):
    alt = text_anlegen("Erster gespeicherter Text")
    mittel = text_anlegen("Mittlerer gespeicherter Text", tage=1)
    neu = text_anlegen("Jüngster gespeicherter Text", tage=2)
    monkeypatch.setattr("faktenbasis.views.zahl", lambda schluessel, standard: 1)
    auswahl = reverse("faktenbasis:textvergleich", args=[alt.pk])
    assert auswahl in client.get(reverse("faktenbasis:norm", args=[alt.norm_id])).content.decode()
    erste = client.get(auswahl).context["seite"]
    zweite = client.get(auswahl, {"seite": 2}).context["seite"]
    assert [t["pk"] for t in erste] == [neu.pk]
    assert [t["pk"] for t in zweite] == [mittel.pk]
