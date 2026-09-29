"""Die Karte „Betroffene Gesetze“ in Zone 2 (erste Stufe von FB-H3): Zustände nicht angeschlossen /
in der Warteschlange / erledigt / gescheitert, Gast sieht die Karte, das Band nach dem Einbringen,
die Mail bei Fertigstellung — nur mit Einwilligung —, die öffentliche Warteschlange."""

import json

import pytest
from django.core import mail
from django.urls import reverse

from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
from ki.warteschlange import abarbeiten, einreihen
from mitglieder.models import Postauftrag
from mitglieder.postausgang import offene_zustellen
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

JSON_ANTWORT = json.dumps(
    {
        "normen": [
            {"titel": "Parteiengesetz 2012", "ebene": "Bund", "kennung": "BGBl. I Nr. 56/2012", "aenderung": "aendern", "begruendung": "Regelt die Rechenschaft."},
            {"titel": "Transparenz-Richtlinie", "ebene": "EU", "aenderung": "beruehrt"},
        ],
        "hinweis": "Bundeskompetenz nach Art. 10 B-VG.",
        "unsicherheit": "mittel",
    }
)


@pytest.fixture
def json_attrappe(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda self, auftrag, eingabe: Antwort(JSON_ANTWORT, "attrappe-1", 10, 20))


def _antrag(ordnung, einwilligung=True):  # noqa: F811
    m = mitglied_anlegen("anna")
    m.post_einwilligung = einwilligung
    m.save(update_fields=["post_einwilligung"])
    return antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)


def _seite(client, antrag, **query):
    url = reverse("verfahren:antrag", args=[antrag.pk])
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    return client.get(url).content.decode()


# --- Zustände der Karte -----------------------------------------------------------------------------


def test_gast_sieht_die_karte_ohne_anbieter_ehrlich_leer(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert "Betroffene Gesetze" in inhalt and "Vorschlag der Zukunftswerkstatt" in inhalt
    assert "Kein Anbieter angeschlossen — es wird nichts gerechnet." in inhalt
    assert "prüft, welche Gesetze" not in inhalt


def test_wartend_mit_platz_und_mailzusage_nur_fuer_den_antragsteller_mit_einwilligung(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)  # Gast
    assert "Die Zukunftswerkstatt prüft, welche Gesetze betroffen sind." in inhalt and "Platz 1" in inhalt
    assert "Sie bekommen eine E-Mail" not in inhalt
    client.force_login(mitglied_anlegen("bernd"))  # ein anderes Mitglied
    assert "Sie bekommen eine E-Mail" not in _seite(client, antrag)
    client.force_login(antrag.eingebracht_von)  # der Antragsteller, mit Einwilligung
    assert "Sie bekommen eine E-Mail, sobald das Ergebnis da ist." in _seite(client, antrag)


def test_ohne_einwilligung_verspricht_die_karte_keine_mail(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag = _antrag(ordnung, einwilligung=False)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    client.force_login(antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert "prüft, welche Gesetze" in inhalt and "Sie bekommen eine E-Mail" not in inhalt


def test_erledigt_zeigt_normen_mit_badges_kennzeichnung_und_beanstanden(client, json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    inhalt = _seite(client, antrag)
    assert "Parteiengesetz 2012" in inhalt and "BGBl. I Nr. 56/2012" in inhalt and "Transparenz-Richtlinie" in inhalt
    assert inhalt.count("nicht verifiziert") >= 2 and "zu ändern" in inhalt and "berührt" in inhalt
    assert "Bundeskompetenz nach Art. 10 B-VG." in inhalt and "mittel" in inhalt
    assert "attrappe-1 · rechtsbezug-v1" in inhalt
    assert "KI-Vorschlag — ohne RIS-Prüfung, keine Rechtsberatung" in inhalt
    assert "Modellrechnung — sie schlägt vor, sie entscheidet nie" in inhalt  # die Kopfkarte bleibt
    assert 'href="http' not in inhalt.split('id="rechtsbezug"')[1].split("</div>")[0]  # kein Link auf eine Norm
    client.force_login(mitglied_anlegen("bernd"))
    assert "/beanstanden/" in _seite(client, antrag)  # der Beanstanden-Knopf bleibt


def test_rohe_antwort_ohne_json_bleibt_lesbar(client, settings, ordnung, monkeypatch):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"  # die Attrappe antwortet mit Prosa, nicht mit JSON
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    inhalt = _seite(client, antrag)
    assert "Antwort ohne festes Format — der Wortlaut:" in inhalt and "Attrappen-Einschätzung" in inhalt
    assert "keine Norm genannt" in inhalt


def test_gescheitert_sagt_es(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag = _antrag(ordnung)
    a = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    KIAuftrag.objects.filter(pk=a.pk).update(status=Auftragsstatus.GESCHEITERT, versuche=6, fehler="HTTP 503")
    inhalt = _seite(client, antrag)
    assert "Lauf gescheitert — alle Versuche aufgebraucht." in inhalt and "HTTP 503" in inhalt


def test_altbestand_ohne_auftrag(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    inhalt = _seite(client, _antrag(ordnung))
    assert "Für diesen Antrag wurde keine Prüfung eingereiht." in inhalt


def test_textvektoren_zaehlen_nicht_als_stand_der_einschaetzung(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag = _antrag(ordnung)
    einreihen(Zweck.AEHNLICHKEIT, antrag, antrag.eingebracht_von)
    abarbeiten()
    inhalt = _seite(client, antrag)
    assert "noch kein Lauf" in inhalt and "attrappe-einbettung-1" not in inhalt


# --- Das Band nach dem Einbringen -------------------------------------------------------------------


def test_band_nach_dem_einbringen_verweist_auf_zone_2(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), ANTRAG, follow=True)
    inhalt = antwort.content.decode()
    assert "Einschätzung der Zukunftswerkstatt:" in inhalt and 'href="#zone-einschaetzung"' in inhalt
    assert "Die Zukunftswerkstatt prüft, welche Gesetze betroffen sind." in inhalt
    # Ohne ?neu=1 kein Band
    from verfahren.models import Antrag

    assert "Einschätzung der Zukunftswerkstatt:" not in _seite(client, Antrag.objects.get())


def test_band_verspricht_nur_betroffene_gesetze_und_einbringen_kuendigt_nichts_an(client, settings, ordnung):  # noqa: F811
    """Zone 2 hat keine Karte „ähnliche Anträge“ — das Band verspricht nur, was dort steht. Die
    Einbringen-Seite kündigt keine künftigen Karten an (Grundregel 1)."""
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(mitglied_anlegen("bernd"))
    einbringen = " ".join(client.get(reverse("verfahren:einbringen")).content.decode().split())
    assert "StaatsSimulation" not in einbringen
    inhalt = client.post(reverse("verfahren:einbringen"), ANTRAG, follow=True).content.decode()
    assert "betroffene Gesetze zu diesem Antrag →" in inhalt
    assert "ähnliche Anträge zu diesem Antrag" not in inhalt


# --- Die Mail bei Fertigstellung ---------------------------------------------------------------------


def test_mail_bei_fertigstellung_mit_normen_und_kennzeichnung(client, json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    auftrag = Postauftrag.objects.get(art="rechtsbezug")
    assert auftrag.antrag == antrag and auftrag.bezug == f"antrag:{antrag.pk}" and not auftrag.erledigt
    assert offene_zustellen() == 1
    brief = mail.outbox[-1]
    assert brief.subject == "Zukunftswerkstatt: betroffene Gesetze zu Ihrem Antrag"
    assert brief.to == [antrag.eingebracht_von.email]
    assert "Parteiengesetz 2012" in brief.body and "nicht verifiziert" in brief.body
    assert f"/antrag/{antrag.pk}/#rechtsbezug" in brief.body and "attrappe-1" in brief.body
    assert "Vorschlag eines KI-Modells" in brief.body and "/profil/#nachrichten" in brief.body
    # Genau einmal: ein zweiter Lauf legt keinen zweiten Auftrag an
    abarbeiten()
    assert Postauftrag.objects.filter(art="rechtsbezug").count() == 1


def test_keine_mail_ohne_einwilligung(json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung, einwilligung=False)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    assert KILauf.objects.filter(zweck=Zweck.RECHTSBEZUG, erfolgreich=True).exists()
    assert not Postauftrag.objects.filter(art="rechtsbezug").exists()
    assert mail.outbox == []


def test_keine_mail_an_testkonten(json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    m = antrag.eingebracht_von
    m.__class__.objects.filter(pk=m.pk).update(testkonto=True)
    einreihen(Zweck.RECHTSBEZUG, antrag, m)
    abarbeiten()
    assert not Postauftrag.objects.filter(art="rechtsbezug").exists()


def test_brief_ohne_ergebnis_geht_nicht(ordnung):  # noqa: F811
    from mitglieder.post import rechtsbezug_brief

    antrag = _antrag(ordnung)
    assert rechtsbezug_brief(antrag.eingebracht_von, antrag) is False and mail.outbox == []


# --- Öffentlichkeit ----------------------------------------------------------------------------------


def test_zukunftswerkstatt_zeigt_warteschlange_und_auftragsversionen(client, json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "Warteschlange" in inhalt and "offen: 1" in inhalt and "Heute gestartet: 0 von 20" in inhalt
    assert "rechtsbezug-v1" in inhalt and "Du bist die Zukunftswerkstatt" in inhalt
    assert "attrappe-einbettung-1" in inhalt
    abarbeiten()
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "erledigt: 1" in inhalt and "Heute gestartet: 1 von 20" in inhalt
