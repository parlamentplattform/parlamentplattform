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


def test_die_karte_nennt_die_gepruefte_fassung_und_sagt_wenn_sie_aelter_ist(client, json_attrappe, ordnung):  # noqa: F811
    """§ 6 Abs 11 lit b „Kontextstand“: Nach einer neuen Fassung steht nicht still das Ergebnis zur alten da."""
    from ki.rechtsbezug import rechtsbezug_fuer
    from verfahren.models import AntragsFassung

    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    assert rechtsbezug_fuer(antrag)["fassung"] == 1 and not rechtsbezug_fuer(antrag)["frueher"]
    karte = _seite(client, antrag).split('id="rechtsbezug"')[1].split('class="kennzeichnung"')[0]
    assert "zu Fassung 1" in karte and "zu einer früheren Fassung" not in karte
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Völlig anderer Text über Tierschutz.")
    karte = _seite(client, antrag).split('id="rechtsbezug"')[1].split('class="kennzeichnung"')[0]
    assert "Parteiengesetz 2012" in karte and "zu Fassung 1" in karte and "zu einer früheren Fassung" in karte


def test_rechtsbezug_ist_keine_einschaetzung_der_kopfkarte(client, json_attrappe, ordnung):  # noqa: F811
    """Der Rechtsbezug hat seine eigene Karte; Kopfkarte „Stand“/„Lauf“ und das Skelett „Was hier
    stehen wird“ gehören der Einschätzung — solange keine vorliegt, bleibt das Skelett stehen."""
    from ki.models import lauf_ausfuehren
    from verfahren.views import _einschaetzung

    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    assert _einschaetzung(antrag)["lauf"] is None
    inhalt = _seite(client, antrag)
    assert "Parteiengesetz 2012" in inhalt  # die eigene Karte „Betroffene Gesetze“
    assert "noch kein Lauf" in inhalt and "Was hier stehen wird" in inhalt
    lauf = lauf_ausfuehren(Zweck.EINSCHAETZUNG, "Auftrag", "Text.", antrag.eingebracht_von, antrag=antrag)
    assert _einschaetzung(antrag)["lauf"] == lauf


def test_gremien_fenster_zeigt_den_rechtsbezug_nicht_als_einschaetzung(client, json_attrappe, ordnung):  # noqa: F811
    from gremien.test_werkstatt import fenster_oeffnen, werkstatt_lage

    antrag, _, er = werkstatt_lage(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    fenster_oeffnen(client, antrag, er[0])
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "Zu diesem Antrag liegt keine Einschätzung vor." in inhalt
    assert "&quot;normen&quot;" not in inhalt and '"normen"' not in inhalt


def test_beanstandung_trifft_nie_den_textvektor_lauf(client, json_attrappe, ordnung):  # noqa: F811
    """§ 6 Abs 11 lit b: Beanstandet wird ein Lauf, den ein Mensch liest — nach „Trotzdem einbringen“
    rechnet die Warteschlange Rechtsbezug und Textvektor; der jüngere Vektor-Lauf ist nie das Ziel."""
    from verfahren.models import Antrag, AuditEintrag, Beanstandung

    client.force_login(mitglied_anlegen("anna"))
    assert client.post(reverse("verfahren:einbringen"), {**ANTRAG, "trotzdem": "1"}).status_code == 302
    antrag = Antrag.objects.get()
    abarbeiten()
    zwecke = list(KILauf.objects.filter(antrag=antrag).order_by("erstellt_am", "pk").values_list("zweck", flat=True))
    assert zwecke == [Zweck.RECHTSBEZUG, Zweck.AEHNLICHKEIT]  # der Vektor-Lauf ist der jüngste
    client.post(reverse("verfahren:beanstanden", args=[antrag.pk]), {"text": "Die Norm stimmt nicht."})
    b = Beanstandung.objects.get(antrag=antrag)
    assert b.lauf.zweck == Zweck.RECHTSBEZUG
    audit = AuditEintrag.objects.filter(ereignis__art="einschaetzung_beanstandet").get()
    assert audit.ereignis["lauf"] == b.lauf_id


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
