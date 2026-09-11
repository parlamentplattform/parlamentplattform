"""Der Koordinationsrat (FB-I5, § 6 Abs 2), die weiteren Räte und der Lesezugang (FB-I1),
Protokoll und Jahresbericht (FB-I6).

Der Rat entscheidet als Rat: Kein Knopf im Bereich wirkt unmittelbar, jeder legt einen Beschluss
an. Die Wirkungen — Austausch, Vorschlag an die Mitgliederversammlung, Antrag beim Integritätsrat
— hängen am Anlass des Beschlusses, nicht an der Person, die ihn anlegte.
"""

import itertools
import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import (
    SATZUNG_UEBERLASTUNG_TAGE,
    Anlass,
    BeschlussStatus,
    GremienBeschluss,
    Gremium,
    Rolle,
    Ueberlastungsmeldung,
)
from gremien.test_werkstatt import mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from verfahren.models import Antrag, AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG

pytestmark = pytest.mark.django_db

_ZAEHLER = itertools.count()


def korat(anzahl=3):
    leute = [mitglied_anlegen(f"kr{next(_ZAEHLER)}") for _ in range(anzahl)]
    for m in leute:
        rolle_geben(m, Gremium.KOORDINATIONSRAT)
    return leute


def abstimmen(client, leute, beschluss, option="dafuer"):
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": option, "begruendung": "Weil."},
        )
    beschluss.refresh_from_db()
    return beschluss


def test_der_bereich_hat_vier_karten(client):
    leute = korat()
    client.force_login(leute[0])
    seite = client.get(reverse("gremien:koordination")).content.decode()
    for marke in ('id="aufgaben"', 'id="posteingang"', 'id="beschluesse"', 'id="parameter"'):
        assert marke in seite
    assert "Test anordnen" in seite and "Beschluss anlegen" in seite


def test_ein_interner_beschluss_mit_umsetzungsvermerk(client):
    leute = korat()
    client.force_login(leute[0])
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "intern", "gegenstand": "Monatliche Sitzung", "beschreibung": "Jeden ersten Montag."},
    )
    beschluss = GremienBeschluss.objects.get(gremium=Gremium.KOORDINATIONSRAT)
    assert beschluss.anlass == Anlass.INTERN and beschluss.nummer.startswith("KR-")
    # Vor der Entscheidung gibt es keinen Umsetzungsvermerk
    client.post(
        reverse("gremien:beschluss_umsetzung", args=[beschluss.pk]),
        {"umsetzungsvermerk": "Zu früh."},
    )
    beschluss.refresh_from_db()
    assert beschluss.umsetzungsvermerk == ""
    abstimmen(client, leute, beschluss)
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN
    frist = (timezone.localdate() + timedelta(days=14)).isoformat()
    client.force_login(leute[1])
    client.post(
        reverse("gremien:beschluss_umsetzung", args=[beschluss.pk]),
        {"umsetzungsvermerk": "Einladung geht per Mail.", "umsetzung_durch": leute[2].pk, "umsetzung_frist": frist},
    )
    beschluss.refresh_from_db()
    assert beschluss.umsetzungsvermerk == "Einladung geht per Mail."
    assert beschluss.umsetzung_durch == leute[2] and beschluss.umsetzung_frist.isoformat() == frist
    assert any(e.ereignis["typ"] == "umsetzungsvermerk" for e in AuditEintrag.objects.all())
    # Öffentlich beim Beschluss
    client.logout()
    assert "Einladung geht per Mail." in client.get(reverse("gremien:beschluss", args=[beschluss.nummer])).content.decode()


def test_der_umsetzungsvermerk_geht_nur_an_ratsmitglieder(client):
    leute = korat()
    client.force_login(leute[0])
    client.post(reverse("gremien:koordination_beschluss"), {"anlass": "intern", "gegenstand": "X", "beschreibung": "Y"})
    beschluss = abstimmen(client, leute, GremienBeschluss.objects.get())
    fremd = mitglied_anlegen("fremd")
    client.force_login(leute[0])
    client.post(
        reverse("gremien:beschluss_umsetzung", args=[beschluss.pk]),
        {"umsetzungsvermerk": "Vermerk.", "umsetzung_durch": fremd.pk},
    )
    beschluss.refresh_from_db()
    assert beschluss.umsetzungsvermerk == "" and beschluss.umsetzung_durch is None


def test_wer_keine_rolle_hat_legt_keinen_beschluss_an(client):
    korat()
    fremd = mitglied_anlegen("fremd")
    client.force_login(fremd)
    antwort = client.post(reverse("gremien:koordination_beschluss"), {"anlass": "intern", "gegenstand": "X", "beschreibung": "Y"})
    assert antwort.status_code == 403 and not GremienBeschluss.objects.exists()


def test_hervorhebung_wird_beim_integritaetsrat_beantragt(client, ordnung):  # noqa: F811
    """FB-D4: Der Koordinationsrat beantragt, der Integritätsrat beschließt — zwei Räte, vier Augen."""
    leute = korat()
    antrag = antrag_einbringen(mitglied_anlegen("stellerin"), **ANTRAG, ordnung=ordnung)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "hervorhebung_anregen", "antrag": antrag.pk, "beschreibung": "Wenig Beteiligung, große Wirkung."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG_ANREGEN)
    abstimmen(client, leute, beschluss)
    antrag.refresh_from_db()
    assert antrag.hervorgehoben is False, "der Koordinationsrat hebt nie selbst hervor"
    beim_ir = GremienBeschluss.objects.get(gremium=Gremium.INTEGRITAETSRAT, anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    assert beim_ir.status == BeschlussStatus.OFFEN and beschluss.nummer in beim_ir.beschreibung
    assert beim_ir.nummer in beschluss.umsetzungsvermerk


def test_ueberlastungsmeldung_ist_sofort_oeffentlich_und_bekommt_einen_vorschlag(client, ordnung):  # noqa: F811
    """§ 6 Abs 10: unverzüglich veröffentlichen; der Vorschlag geht binnen 30 Tagen an die MV."""
    from verfahren.models import Verfahrensordnung

    assert Verfahrensordnung.objects.filter(aktiv=True).exists()
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    client.post(
        reverse("gremien:ueberlastung_melden"),
        {"stelle": "Gemeinderatsfraktion Musterstadt", "begruendung": "Drei Beschlüsse, ein Mensch."},
    )
    meldung = Ueberlastungsmeldung.objects.get()
    assert (meldung.frist - meldung.gemeldet_am).days == SATZUNG_UEBERLASTUNG_TAGE
    client.logout()
    assert "Drei Beschlüsse, ein Mensch." in client.get(reverse("verfahren:umsetzung")).content.decode()
    leute = korat()
    client.force_login(leute[0])
    seite = client.get(reverse("gremien:koordination")).content.decode()
    assert "Gemeinderatsfraktion Musterstadt" in seite and "30-Tage-Frist" in seite
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "ueberlastung", "meldung": meldung.pk, "beschreibung": "Beschluss 2 wird um ein Jahr gestreckt."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.UEBERLASTUNG)
    abstimmen(client, leute, beschluss)
    meldung.refresh_from_db()
    assert meldung.erledigt_am is not None and meldung.antrag_an_mv is not None
    mv = meldung.antrag_an_mv
    assert mv.aktueller_text().wortlaut == "Beschluss 2 wird um ein Jahr gestreckt."
    assert "Überlastungsmeldung" in mv.titel and mv.phase == "unterstuetzung"


def test_nur_berichtspflichtige_stellen_melden(client):
    fremd = mitglied_anlegen("fremd")
    client.force_login(fremd)
    client.post(reverse("gremien:ueberlastung_melden"), {"stelle": "Ich", "begruendung": "Viel."})
    assert not Ueberlastungsmeldung.objects.exists()
    rat = mitglied_anlegen("berichte")
    rolle_geben(rat, Gremium.BERICHTSWESENRAT)
    client.force_login(rat)
    client.post(reverse("gremien:ueberlastung_melden"), {"stelle": "Berichtswesenrat", "begruendung": "Viel."})
    assert Ueberlastungsmeldung.objects.count() == 1


def test_mein_gremium_waehlt_bei_mehreren_rollen(client):
    beide = mitglied_anlegen("beide")
    rolle_geben(beide, Gremium.KOORDINATIONSRAT)
    client.force_login(beide)
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:koordination")
    rolle_geben(beide, Gremium.ENTWICKLUNGSRAT)
    antwort = client.get(reverse("gremien:mein"))
    assert antwort.status_code == 200
    seite = antwort.content.decode()
    assert "Koordinationsrat" in seite and "Technischer Entwicklungsrat" in seite
    assert reverse("gremien:rat", args=["entwicklungsrat"]) in seite


def test_die_weiteren_raete_haben_einen_bereich_mit_beschluessen(client):
    rat = mitglied_anlegen("technik")
    rolle_geben(rat, Gremium.ENTWICKLUNGSRAT)
    client.force_login(rat)
    seite = client.get(reverse("gremien:rat", args=["entwicklungsrat"])).content.decode()
    assert "Technischer Entwicklungsrat" in seite and "Regelverzeichnis" in seite
    client.post(
        reverse("gremien:rat_beschluss", args=["entwicklungsrat"]),
        {"gegenstand": "Wartungsfenster", "beschreibung": "Sonntag früh."},
    )
    beschluss = GremienBeschluss.objects.get(gremium=Gremium.ENTWICKLUNGSRAT)
    assert beschluss.nummer.startswith("TE-")
    assert client.get(reverse("gremien:rat", args=["expertenrat1"])).status_code == 404
    fremd = mitglied_anlegen("fremd")
    client.force_login(fremd)
    assert client.get(reverse("gremien:rat", args=["entwicklungsrat"])).status_code == 403


def test_wer_eine_rolle_hatte_liest_weiter_mit_band(client):
    """FB-I1: Lesezugang für abgelaufene Rollen — schreiben nicht."""
    vormals = mitglied_anlegen("vormals")
    rolle = rolle_geben(vormals, Gremium.KOORDINATIONSRAT)
    rolle.endet_am = timezone.localdate() - timedelta(days=1)
    rolle.save()
    client.force_login(vormals)
    antwort = client.get(reverse("gremien:koordination"))
    assert antwort.status_code == 200
    assert "Ihre Rolle endete am" in antwort.content.decode()
    client.post(reverse("gremien:koordination_beschluss"), {"anlass": "intern", "gegenstand": "X", "beschreibung": "Y"})
    assert not GremienBeschluss.objects.exists()
    nie = mitglied_anlegen("nie")
    client.force_login(nie)
    assert client.get(reverse("gremien:koordination")).status_code == 403


def test_das_protokoll_ist_oeffentlich_und_vollstaendig(client):
    leute = korat()
    client.force_login(leute[0])
    client.post(reverse("gremien:koordination_beschluss"), {"anlass": "intern", "gegenstand": "Sitzung", "beschreibung": "Montag."})
    beschluss = abstimmen(client, leute, GremienBeschluss.objects.get())
    client.logout()
    jahr = timezone.localdate().year
    antwort = client.get(reverse("gremien:protokoll", args=["koordinationsrat", jahr]))
    daten = json.loads(antwort.content)
    assert daten["gremium"] == "koordinationsrat" and len(daten["beschluesse"]) == 1
    eintrag = daten["beschluesse"][0]
    assert eintrag["nummer"] == beschluss.nummer and len(eintrag["stimmen"]) == 3
    assert eintrag["stimmen"][0]["begruendung"] == "Weil."
    assert client.get(reverse("gremien:protokoll", args=["nirgendsrat", jahr])).status_code == 404


def test_der_jahresbericht_des_integritaetsrats_ist_oeffentlich(client, ordnung):  # noqa: F811
    from gremien.test_integritaet import beschluss_fassen, rat

    leute = rat()
    antrag = antrag_einbringen(mitglied_anlegen("stellerin"), **ANTRAG, ordnung=ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    client.logout()
    jahr = timezone.localdate().year
    seite = client.get(reverse("gremien:integritaet_bericht", args=[jahr])).content.decode()
    assert "Bericht des Integritätsrats" in seite and antrag.titel in seite
    assert "Hervorhebung eines Antrags" in seite
    for m in leute:
        assert m.anzeigename in seite


def test_unvereinbare_rollen_werden_nicht_vergeben(client):
    """§ 6 Abs 3 lit a — geprüft bei der Vergabe, nicht erst beim Losen."""
    from gremien.models import standard_ende

    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    wer = mitglied_anlegen("doppelt")
    rolle_geben(wer, Gremium.KOORDINATIONSRAT)
    client.force_login(admin)
    client.post(
        reverse("gremien:rollen_aktion"),
        {"aktion": "berufen", "mitglied": wer.pk, "gremium": "integritaetsrat", "endet_am": standard_ende().isoformat()},
    )
    assert not Rolle.objects.filter(mitglied=wer, gremium=Gremium.INTEGRITAETSRAT).exists()
    aufsicht = mitglied_anlegen("aufsicht")
    rolle_geben(aufsicht, Gremium.INTEGRITAETSRAT)
    client.post(
        reverse("gremien:rollen_aktion"),
        {"aktion": "berufen", "mitglied": aufsicht.pk, "gremium": "expertenrat1", "endet_am": standard_ende().isoformat()},
    )
    assert not Rolle.objects.filter(mitglied=aufsicht, gremium=Gremium.EXPERTENRAT_1).exists()


def test_austausch_lost_die_gruppe_neu(client, ordnung):  # noqa: F811
    """Stattgeben beendet nur die für DIESEN Antrag gelosten Rollen — und lost eine neue Runde."""
    from gremien.models import Auslosung, Entwurf, Pruefung
    from gremien.test_auslosung import antrag_in_beratung, fachliste_fuellen

    fachliste_fuellen(12)
    antrag = antrag_in_beratung(ordnung)
    anderer = antrag_in_beratung(ordnung)
    erste = Auslosung.objects.get(antrag=antrag)
    entwurf = Entwurf.objects.create(antrag=antrag, vollzugsbezug=True)
    entwurf.fassungen.create(nummer=1, wortlaut="Text.", verfasst_von=Rolle.objects.filter(antrag=antrag).first().mitglied)
    entwurf.einreichen()
    pruefung = Pruefung.objects.create(
        entwurf=entwurf, runde=1, ergebnis=Pruefung.Ergebnis.AUSTAUSCH, begruendung="Zweifel.", durch=None
    )
    leute = korat()
    client.force_login(leute[0])
    client.post(
        reverse("gremien:koordination_beschluss"),
        {"anlass": "austausch", "pruefung": pruefung.pk, "beschreibung": "Die Zweifel wiegen schwer."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH)
    abstimmen(client, leute, beschluss)
    pruefung.refresh_from_db()
    assert pruefung.korat_entscheid == "stattgegeben"
    alte = Rolle.objects.filter(auslosung=erste, gremium=Gremium.EXPERTENRAT_1)
    assert alte.exists() and all(not r.aktiv for r in alte)
    assert all(r.aktiv for r in Rolle.objects.filter(antrag=anderer)), "fremde Verfahren bleiben unberührt"
    zweite = Auslosung.objects.get(antrag=antrag, runde=2)
    assert Rolle.objects.filter(auslosung=zweite, gremium=Gremium.EXPERTENRAT_1).count() == 3
    assert not ({p["schluessel"] for p in erste.plaetze} & {p["schluessel"] for p in zweite.plaetze})
    assert Antrag.objects.get(pk=antrag.pk).phase == "beratung"
