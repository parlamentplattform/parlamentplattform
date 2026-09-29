"""„Neuer Antrag in Ihrer Region“ (Anweisung des Gründers 28.9.2026): Gemeinde-, Bezirks-, Landes- und
Bundesanträge treffen genau die Betroffenen — nie den Antragsteller, nie ohne Einwilligung, nie Testkonten;
der Nebenwohnsitz nur mit Stellgröße; ein Brief je Antrag und Konto, mit Link und Abbestell-Hinweis."""

import json

import pytest
from django.core import mail
from django.urls import reverse

from mitglieder.models import Gemeinde, Identitaetsstufe, Mitglied, Mitgliedsstatus, Postauftrag
from mitglieder.post import region_benachrichtigen, region_empfaenger
from mitglieder.postausgang import beauftragen, offene_zustellen, zustellen
from parameter.models import Parameter
from verfahren.models import AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def gemeinde(kennziffer, name, bezirk, bundesland):
    return Gemeinde.objects.create(kennziffer=kennziffer, name=name, bezirk=bezirk, bundesland=bundesland)


@pytest.fixture
def orte():
    return {
        "eferding": gemeinde("40501", "Eferding", "Eferding", "oberoesterreich"),
        "hartkirchen": gemeinde("40504", "Hartkirchen", "Eferding", "oberoesterreich"),
        "wels": gemeinde("40301", "Wels", "Wels(Stadt)", "oberoesterreich"),
        "graz": gemeinde("60101", "Graz", "Graz(Stadt)", "steiermark"),
        # gleicher Name in einem anderen Bezirk: ein Gemeinde-Antrag trifft nur die richtige Gemeinde
        "eferding2": gemeinde("70999", "Eferding", "Testbezirk", "tirol"),
    }


def mitglied(name, wohnsitz, einwilligung=True, **extra):
    m = Mitglied.objects.create(
        username=name,
        email=f"{name}@example.org",
        is_active=True,
        identitaetsstufe=Identitaetsstufe.GEPRUEFT,
        gemeinde=wohnsitz.name,
        bundesland=wohnsitz.bundesland,
        wohnsitz=wohnsitz,
        post_einwilligung=einwilligung,
    )
    for feld, wert in extra.items():
        setattr(m, feld, wert)
    m.set_unusable_password()
    m.save()
    return m


@pytest.fixture
def konten(orte):
    k = {
        "steller": mitglied("steller", orte["eferding"]),
        "a": mitglied("a", orte["eferding"]),
        "b": mitglied("b", orte["hartkirchen"]),
        "c": mitglied("c", orte["wels"]),
        "d": mitglied("d", orte["graz"]),
        "ohne": mitglied("ohne", orte["eferding"], einwilligung=False),
        "test": mitglied("test", orte["eferding"], testkonto=True),
        "weg": mitglied("weg", orte["eferding"], status=Mitgliedsstatus.AUSGETRETEN, is_active=False),
        "inaktiv": mitglied("inaktiv", orte["eferding"], is_active=False),
        "neben": mitglied("neben", orte["graz"], nebenwohnsitz=orte["eferding"]),
        "ungeprueft": mitglied("ungeprueft", orte["eferding"], identitaetsstufe=Identitaetsstufe.UNGEPRUEFT),
        "pausiert": mitglied("pausiert", orte["eferding"], status=Mitgliedsstatus.PAUSIERT),
        "namensvetter": mitglied("namensvetter", orte["eferding2"]),
        "altbestand": mitglied("altbestand", orte["eferding"]),
    }
    # Altbestand ohne Verweis ins Verzeichnis: nur der Gemeindename ist gesetzt
    Mitglied.objects.filter(pk=k["altbestand"].pk).update(wohnsitz=None)
    return k


def antrag_auf(konten, ordnung, ebene, gebiet):  # noqa: F811
    return antrag_einbringen(konten["steller"], **ANTRAG, ordnung=ordnung, ebene=ebene, gebiet=gebiet)


def namen(antrag):
    return sorted(region_empfaenger(antrag).values_list("username", flat=True))


def schalter(schluessel, wert):
    Parameter.objects.update_or_create(schluessel=schluessel, defaults={"wert": wert, "beschreibung": "Test", "quelle": "Test"})


def test_gemeindeantrag_trifft_genau_die_gemeinde(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "gemeinde", "Eferding")
    assert namen(antrag) == ["a", "pausiert", "ungeprueft"]


def test_gemeindeantrag_ohne_verweis_faellt_auf_den_namen_zurueck(konten, ordnung, orte):  # noqa: F811
    # Der Antragsteller wohnt inzwischen woanders: Die Gemeinde ist nur noch über den Namen bestimmbar,
    # und der Altbestand ohne Verweis zählt über sein Namensfeld mit.
    Mitglied.objects.filter(pk=konten["steller"].pk).update(wohnsitz=orte["graz"], gemeinde="Graz")
    konten["steller"].refresh_from_db()
    antrag = antrag_auf(konten, ordnung, "gemeinde", "Eferding")
    assert namen(antrag) == ["a", "altbestand", "namensvetter", "pausiert", "ungeprueft"]


def test_bezirksantrag_trifft_den_bezirk(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "bezirk", "Eferding")
    assert namen(antrag) == ["a", "b", "pausiert", "ungeprueft"]


def test_landesantrag_trifft_das_bundesland_auch_im_altbestand(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "land", "Oberösterreich")
    assert namen(antrag) == ["a", "altbestand", "b", "c", "pausiert", "ungeprueft"]
    assert namen(antrag_auf(konten, ordnung, "land", "Unbekanntes Land")) == []


def test_bundesantrag_trifft_alle_mit_einwilligung_nur_bei_schalter_1(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "bund", "")
    assert namen(antrag) == ["a", "altbestand", "b", "c", "d", "namensvetter", "neben", "pausiert", "ungeprueft"]
    schalter("post-neuer-antrag-bund", "0")
    assert namen(antrag) == []


def test_nebenwohnsitz_zaehlt_nur_mit_stellgroesse(konten, ordnung):  # noqa: F811
    for ebene, gebiet in (("gemeinde", "Eferding"), ("bezirk", "Eferding"), ("land", "Oberösterreich")):
        assert "neben" not in namen(antrag_auf(konten, ordnung, ebene, gebiet))
    schalter("region-nebenwohnsitz-zaehlt", "1")
    for ebene, gebiet in (("gemeinde", "Eferding"), ("bezirk", "Eferding"), ("land", "Oberösterreich")):
        assert "neben" in namen(antrag_auf(konten, ordnung, ebene, gebiet)), ebene
    assert namen(antrag_auf(konten, ordnung, "gemeinde", "Graz")) == ["d", "neben"]  # Hauptwohnsitz zählt, nie doppelt


def test_benachrichtigen_legt_je_konto_einen_auftrag_an_und_auditiert_ohne_personenbezug(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "bezirk", "Eferding")
    assert region_benachrichtigen(antrag) == 4
    assert region_benachrichtigen(antrag) == 0  # zweiter Aufruf: No-op
    auftraege = Postauftrag.objects.filter(art="neuer_antrag", antrag=antrag)
    assert auftraege.count() == 4 and set(auftraege.values_list("bezug", flat=True)) == {f"antrag:{antrag.pk}"}
    assert not auftraege.filter(mitglied__in=[konten["steller"], konten["ohne"], konten["test"], konten["weg"]]).exists()
    eintraege = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == "post_neuer_antrag"]
    assert [(e["antrag"], e["empfaenger"]) for e in eintraege] == [(antrag.pk, 4), (antrag.pk, 0)]
    assert "example.org" not in json.dumps(eintraege) and "mitglied" not in json.dumps(eintraege)
    assert mail.outbox == []  # Zustellung im Hintergrundlauf


def test_zustellen_verschickt_genau_einen_brief_mit_link_und_abbestellhinweis(konten, ordnung, settings):  # noqa: F811
    settings.DDOE_BASIS_URL = "https://parlament.ddoe.at/"
    antrag = antrag_auf(konten, ordnung, "gemeinde", "Eferding")
    assert beauftragen(konten["a"], "neuer_antrag", antrag=antrag)
    a = Postauftrag.objects.get(mitglied=konten["a"])
    assert zustellen(a.pk)
    assert not zustellen(a.pk)
    assert len(mail.outbox) == 1
    brief = mail.outbox[0]
    assert brief.to == ["a@example.org"] and brief.subject == "Neuer Antrag in Ihrer Region — ParlamentPlattform"
    text = brief.body
    assert ANTRAG["titel"] in text and "Gemeinde Eferding" in text
    assert f"Eingebracht von: Mitglied {konten['steller'].pk}" in text  # Anzeigename, nie die Adresse
    assert f"https://parlament.ddoe.at/antrag/{antrag.pk}/" in text
    assert "weil Ihr Wohnsitz in diesem Gebiet liegt" in text and "/profil/#nachrichten" in text
    assert ANTRAG["wortlaut"] not in text and "steller@example.org" not in text and "<" not in text
    assert "502117" in text  # Fußzeile aus mail.py
    a.refresh_from_db()
    assert a.erledigt and a.versandt_am is not None
    audit = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == "post"]
    assert audit[-1]["art"] == "neuer_antrag" and audit[-1]["mitglied"] == konten["a"].pk


def test_bundesantrag_hat_eigenen_betreff_und_grund(konten, ordnung):  # noqa: F811
    antrag = antrag_auf(konten, ordnung, "bund", "")
    beauftragen(konten["d"], "neuer_antrag", antrag=antrag)
    assert offene_zustellen() == 1
    brief = mail.outbox[0]
    assert brief.subject == "Neuer Antrag für ganz Österreich — ParlamentPlattform"
    assert "Gilt für: ganz Österreich" in brief.body and "weil der Antrag ganz Österreich betrifft" in brief.body


def test_einbringen_ueber_die_oberflaeche_beauftragt_die_region(client, konten, ordnung):  # noqa: F811
    client.force_login(konten["steller"])
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde"})
    assert antwort.status_code == 302
    antrag = konten["steller"].antraege.get()
    assert antrag.ebene == "gemeinde" and antrag.gebiet == "Eferding"
    empfaenger = set(Postauftrag.objects.filter(antrag=antrag).values_list("mitglied__username", flat=True))
    assert empfaenger == {"a", "pausiert", "ungeprueft"}
    assert mail.outbox == []
    assert offene_zustellen() == 3
    assert {n.to[0] for n in mail.outbox} == {"a@example.org", "pausiert@example.org", "ungeprueft@example.org"}
    assert all(f"/antrag/{antrag.pk}/" in n.body for n in mail.outbox)


def test_einbringen_ohne_betroffene_bleibt_stumm(client, orte, ordnung):  # noqa: F811
    steller = mitglied("allein", orte["graz"])
    client.force_login(steller)
    assert client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde"}).status_code == 302
    assert not Postauftrag.objects.exists() and mail.outbox == []
