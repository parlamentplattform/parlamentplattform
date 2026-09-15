"""Die Vertrauensfrage im Bereich des Integritätsrats und in den Rollen (S10c, § 7 Abs 10).

lit b: Die Software weist beim Einbringen nie ab — sie schreibt den Sperrhinweis; der Rat stellt die
Sperre binnen drei Tagen durch veröffentlichten Beschluss fest, sonst gilt der Antrag als eröffnet.
lit f letzter Unterabsatz: Rollen einer Person, die die Vertrauensfrage verloren hat, ruhen — lesen ja,
schreiben und abstimmen nein. lit f Z 3 Satz 2: Die Wahl in ein Organ gilt als Bestätigung."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import JA_NEIN, Anlass, BeschlussStatus, GremienBeschluss, Gremium, Rolle
from gremien.test_integritaet import rat
from mandatare.models import RUHENSGRUND, Mandat, Vertrauensfrage
from verfahren.models import AuditEintrag
from verfahren.test_vertrauensfrage import (  # noqa: F401
    _verloren,
    altmandat,
    einbringen,
    mitglied_anlegen,
    ordnung,
    tage,
)

pytestmark = pytest.mark.django_db

KARTE = "Vertrauensfragen mit Sperrhinweis"
KNOPF = "Feststellungsbeschluss anlegen"
ABGELAUFEN = "Frist abgelaufen — Antrag läuft"


def audit(typ):
    return [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == typ]


def frisches_mandat(name="neu"):
    """Ein Mandat in der Schonfrist (lit g erster Fall) — jede Vertrauensfrage dazu trägt den Hinweis."""
    return Mandat.objects.create(
        mitglied=mitglied_anlegen(name), bezeichnung="Gemeinderat", ebene="gemeinde", angetreten=timezone.localdate()
    )


def mit_hinweis(ordnung, jetzt=None, name="neu"):  # noqa: F811
    antrag = einbringen(mitglied_anlegen(f"steller-{name}"), frisches_mandat(name), ordnung, jetzt=jetzt)
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert vf.sperrhinweis
    return antrag, vf


def feststellen(client, leute, antrag, grund=None):
    """Der Weg über die Oberfläche: Knopf der Karte, dann stimmt der ganze Rat dafür."""
    client.force_login(leute[0])
    daten = {"anlass": Anlass.VERTRAUENSFRAGE_SPERRE, "antrag": antrag.pk}
    daten["beschreibung"] = grund if grund is not None else antrag.vertrauensfrage.sperrhinweis
    client.post(reverse("gremien:integritaet_beschluss"), daten)
    beschluss = GremienBeschluss.objects.filter(anlass=Anlass.VERTRAUENSFRAGE_SPERRE, antrag=antrag).first()
    if beschluss is None:
        return None
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": "dafuer", "begruendung": "Die Schonfrist läuft."},
        )
    beschluss.refresh_from_db()
    antrag.refresh_from_db()
    return beschluss


# ── Die Karte ──────────────────────────────────────────────────────────────────────────────


def test_die_karte_zeigt_nur_laufende_vertrauensfragen_mit_hinweis_und_ohne_beschluss(client, ordnung, altmandat):  # noqa: F811
    leute = rat(3)
    mit_hinweis_antrag, _vf = mit_hinweis(ordnung, name="a")
    ohne_hinweis = einbringen(mitglied_anlegen("ohne"), altmandat, ordnung)  # außerhalb der Schonfrist
    assert ohne_hinweis.vertrauensfrage.sperrhinweis == ""
    festgestellt, _vf2 = mit_hinweis(ordnung, name="b")
    assert feststellen(client, leute, festgestellt) is not None
    assert festgestellt.phase == "zurueckgewiesen"

    client.force_login(leute[0])
    inhalt = client.get(reverse("gremien:integritaet")).content.decode()
    assert KARTE in inhalt
    assert mit_hinweis_antrag.titel in inhalt and KNOPF in inhalt
    assert "Schonfrist" in inhalt  # der Hinweistext steht auf der Karte und im vorbefüllten Formular
    assert f'name="antrag" value="{mit_hinweis_antrag.pk}"' in inhalt
    assert f'name="antrag" value="{ohne_hinweis.pk}"' not in inhalt
    assert f'name="antrag" value="{festgestellt.pk}"' not in inhalt
    assert festgestellt.titel in inhalt  # steht unter „Zurückgewiesen“ mit der Beschlussnummer
    # Das allgemeine Formular bietet die Feststellung nicht als Knopf an — sie gehört zur Karte.
    assert inhalt.count('value="vertrauensfrage_sperre"') == 1


def test_ohne_hinweis_bleibt_die_karte_leer(client, ordnung):  # noqa: F811
    client.force_login(rat(1)[0])
    inhalt = client.get(reverse("gremien:integritaet")).content.decode()
    assert "Keine Vertrauensfrage mit Sperrhinweis." in inhalt and KNOPF not in inhalt


# ── Der Feststellungsbeschluss ─────────────────────────────────────────────────────────────


def test_der_beschluss_binnen_drei_tagen_setzt_den_antrag_auf_nicht_eroeffnet(client, ordnung):  # noqa: F811
    leute = rat(3)
    antrag, vf = mit_hinweis(ordnung)
    antrag.unterstuetzungen.create(mitglied=leute[1])

    beschluss = feststellen(client, leute, antrag)

    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == "dafuer"
    assert beschluss.frist <= vf.sperrfrist_ende  # schließt spätestens mit der Sperrfrist
    assert beschluss.beschreibung == vf.sperrhinweis  # vorbefüllt mit dem Hinweistext
    assert beschluss.gegenstand.startswith("Sperre einer Vertrauensfrage feststellen: Vertrauensfrage:")
    vf.refresh_from_db()
    assert antrag.phase == "zurueckgewiesen" and vf.sperre_beschluss == beschluss and vf.nicht_eroeffnet
    assert beschluss.nummer in antrag.zurueckweisung_begruendung and "nicht eröffnet" in antrag.zurueckweisung_begruendung
    assert antrag.unterstuetzungen.count() == 1  # bleibt gespeichert, zählt nicht mehr (Grundregel 7)
    assert audit("vertrauensfrage_nicht_eroeffnet")[0]["beschluss"] == beschluss.pk
    angelegt = audit("gremienbeschluss_angelegt")[-1]
    assert angelegt["anlass"] == "vertrauensfrage_sperre" and angelegt["antrag"] == antrag.pk
    assert not Vertrauensfrage.offene_mit_sperrhinweis().exists()


def test_nach_der_frist_bietet_die_karte_keinen_beschluss_mehr_an_und_die_wirkung_bleibt_aus(client, ordnung):  # noqa: F811
    leute = rat(3)
    antrag, vf = mit_hinweis(ordnung, jetzt=timezone.now() - tage(4))
    assert vf.sperrfrist_ende < timezone.now()

    client.force_login(leute[0])
    inhalt = client.get(reverse("gremien:integritaet")).content.decode()
    assert antrag.titel in inhalt and ABGELAUFEN in inhalt and KNOPF not in inhalt

    # Wer den POST trotzdem schickt, bekommt keinen Beschluss — die Frist ist beim Anlegen geprüft.
    assert feststellen(client, leute, antrag) is None
    antwort = client.get(reverse("gremien:integritaet")).content.decode()
    assert "Frist von drei Tagen nach Einbringung ist verstrichen" in antwort
    antrag.refresh_from_db()
    assert antrag.phase == "unterstuetzung"

    # Und ein Beschluss, der es dennoch bis zur Auswertung schafft, bleibt ohne Wirkung (Fundament).
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.VERTRAUENSFRAGE_SPERRE,
        gegenstand="Sperre feststellen",
        beschreibung=vf.sperrhinweis,
        optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
        frist=timezone.now() + tage(2),
        antrag=antrag,
        angelegt_von=leute[0],
    )
    for m in leute:
        client.force_login(m)
        client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Ja."})
    beschluss.refresh_from_db()
    antrag.refresh_from_db()
    vf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and "verstrichen" in beschluss.umsetzungsvermerk
    assert antrag.phase == "unterstuetzung" and vf.sperre_beschluss is None


def test_die_feststellung_gibt_es_nur_zu_einer_vertrauensfrage(client, ordnung):  # noqa: F811
    from gremien.test_integritaet import antrag_anlegen

    leute = rat(3)
    sache = antrag_anlegen(ordnung)
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.VERTRAUENSFRAGE_SPERRE, "antrag": sache.pk, "beschreibung": "Versuch."},
    )
    assert not GremienBeschluss.objects.filter(anlass=Anlass.VERTRAUENSFRAGE_SPERRE).exists()
    assert "nur zu einer laufenden Vertrauensfrage" in client.get(reverse("gremien:integritaet")).content.decode()


def test_ein_zweiter_feststellungsbeschluss_laeuft_nicht_parallel(client, ordnung):  # noqa: F811
    leute = rat(3)
    antrag, vf = mit_hinweis(ordnung)
    client.force_login(leute[0])
    for _ in range(2):
        client.post(
            reverse("gremien:integritaet_beschluss"),
            {"anlass": Anlass.VERTRAUENSFRAGE_SPERRE, "antrag": antrag.pk, "beschreibung": vf.sperrhinweis},
        )
    assert GremienBeschluss.objects.filter(anlass=Anlass.VERTRAUENSFRAGE_SPERRE, antrag=antrag).count() == 1
    inhalt = client.get(reverse("gremien:integritaet")).content.decode()
    assert "Feststellungsbeschluss läuft:" in inhalt and KNOPF not in inhalt  # der laufende wird verlinkt


# ── Ruhende Rollen ─────────────────────────────────────────────────────────────────────────


def ruhen_lassen(mitglied):
    rolle = Rolle.objects.get(mitglied=mitglied)
    rolle.ruht_seit = timezone.now() - timedelta(hours=1)
    rolle.ruht_grund = RUHENSGRUND
    rolle.save(update_fields=["ruht_seit", "ruht_grund"])
    return rolle


def test_eine_ruhende_rolle_liest_den_bereich_mit_band_und_schreibt_nicht(client, ordnung):  # noqa: F811
    leute = rat(3)
    ruhend = ruhen_lassen(leute[0])
    antrag, vf = mit_hinweis(ordnung)

    client.force_login(leute[0])
    antwort = client.get(reverse("gremien:integritaet"))
    inhalt = antwort.content.decode()
    assert antwort.status_code == 200
    assert "Ihre Rolle ruht seit" in inhalt and "Anfechtungsfrist läuft" in inhalt
    assert KNOPF not in inhalt  # lesen ja, anlegen nein

    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.VERTRAUENSFRAGE_SPERRE, "antrag": antrag.pk, "beschreibung": vf.sperrhinweis},
    )
    assert not GremienBeschluss.objects.filter(anlass=Anlass.VERTRAUENSFRAGE_SPERRE).exists()

    # Auch die Stimme in einem Beschluss der anderen zählt nicht — und der Nenner kennt sie nicht.
    client.force_login(leute[1])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.HERVORHEBUNG, "antrag": antrag.pk, "beschreibung": "Test."},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    client.force_login(leute[0])
    client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Ja."})
    assert beschluss.stimmen.count() == 0 and beschluss.aktive_rollen() == 2
    assert Rolle.hat(leute[0], Gremium.INTEGRITAETSRAT) is False and ruhend.ruht

    # „Mein Gremium“ führt weiter in den Bereich — mit Band statt ins Leere.
    assert client.get(reverse("gremien:mein")).url == reverse("gremien:integritaet")


def test_die_rollenverwaltung_und_die_besetzung_zeigen_das_ruhen_mit_grund(client, ordnung):  # noqa: F811
    leute = rat(2)
    ruhen_lassen(leute[0])
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    client.force_login(admin)
    inhalt = client.get(reverse("gremien:rollen")).content.decode()
    assert "ruht seit" in inhalt and "Anfechtungsfrist läuft" in inhalt
    client.logout()
    oeffentlich = client.get(reverse("gremien:uebersicht")).content.decode()
    assert "ruht seit" in oeffentlich and oeffentlich.count(">ruht<") == 1


# ── Bestätigung durch Wahl (lit f Z 3 Satz 2) ──────────────────────────────────────────────


def test_die_berufung_in_ein_organ_gilt_als_bestaetigung(client, ordnung, altmandat):  # noqa: F811
    _verloren(ordnung, altmandat)
    altmandat.refresh_from_db()
    assert altmandat.kandidatursperre and altmandat.bestaetigt_am is None
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    client.force_login(admin)

    antwort = client.post(
        reverse("gremien:rollen_aktion"),
        {
            "aktion": "berufen",
            "mitglied": altmandat.mitglied_id,
            "gremium": Gremium.BERICHTSWESENRAT,
            "endet_am": (timezone.localdate() + tage(365)).isoformat(),
        },
        follow=True,
    )

    assert Rolle.aktive(Gremium.BERICHTSWESENRAT).filter(mitglied=altmandat.mitglied).exists()
    altmandat.refresh_from_db()
    assert altmandat.bestaetigt_am == timezone.localdate() and not altmandat.kandidatursperre
    eintrag = audit("vertrauen_bestaetigt")[-1]
    assert eintrag["mandat"] == altmandat.pk and eintrag["grund"] == "wahl"
    assert "gilt zugleich als Bestätigung" in antwort.content.decode()
    # Die übrigen Wirkungen bleiben (lit f Z 3 letzter Satz).
    assert altmandat.vertrauen_entzogen_am is not None


def test_eine_berufung_ohne_vertrauensfrage_bestaetigt_nichts(client, ordnung):  # noqa: F811
    person = mitglied_anlegen("ruhig")
    mandat = Mandat.objects.create(mitglied=person, bezeichnung="Gemeinderätin", ebene="gemeinde")
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    client.force_login(admin)
    client.post(
        reverse("gremien:rollen_aktion"),
        {
            "aktion": "berufen",
            "mitglied": person.pk,
            "gremium": Gremium.BERICHTSWESENRAT,
            "endet_am": (timezone.localdate() + tage(365)).isoformat(),
        },
    )
    mandat.refresh_from_db()
    assert mandat.bestaetigt_am is None and audit("vertrauen_bestaetigt") == []


def test_ein_durch_fristablauf_geschlossener_beschluss_wirkt_zum_fristzeitpunkt(client, ordnung):  # noqa: F811
    """Der Beschluss schließt mit der Sperrfrist (frist = sperrfrist_ende). Ausgewertet wird lazy —
    beim nächsten Aufruf oder Lauf von `verfahren_fortschreiben`, also nach der Frist. Maßgeblich ist
    der Fristzeitpunkt, nicht der zufällige Aufrufzeitpunkt (Befund #33) — sonst bliebe jede
    Feststellung, bei der nicht alle Ratsmitglieder vor Ablauf gestimmt haben, ohne Wirkung."""
    leute = rat(3)
    antrag, vf = mit_hinweis(ordnung, jetzt=timezone.now() - tage(2))
    client.force_login(leute[0])
    client.post(
        reverse("gremien:integritaet_beschluss"),
        {"anlass": Anlass.VERTRAUENSFRAGE_SPERRE, "antrag": antrag.pk, "beschreibung": vf.sperrhinweis},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.VERTRAUENSFRAGE_SPERRE, antrag=antrag)
    assert beschluss.frist == vf.sperrfrist_ende
    for m in leute[:2]:  # zwei von drei stimmen — der dritte schweigt, die Frist schließt
        client.force_login(m)
        client.post(reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Ja."})

    GremienBeschluss.faellige_abschliessen(vf.sperrfrist_ende + timedelta(hours=5))

    beschluss.refresh_from_db()
    antrag.refresh_from_db()
    vf.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == "dafuer"
    assert antrag.phase == "zurueckgewiesen" and vf.sperre_beschluss == beschluss
    assert antrag.phase_beginn == vf.sperrfrist_ende  # Fristzeitpunkt, nicht Aufrufzeitpunkt


def test_eine_stimme_nach_der_frist_schliesst_den_beschluss_statt_einzufliessen(client, ordnung):  # noqa: F811
    """Wirkt die Feststellung zum Fristzeitpunkt, darf keine Stimme aus der Zeit danach in sie
    einfließen: Ein Beschluss, dessen Frist um ist, schließt beim Versuch, noch abzustimmen."""
    leute = rat(3)
    antrag, vf = mit_hinweis(ordnung, jetzt=timezone.now() - tage(4))  # Sperrfrist (3 Tage) ist um
    client.force_login(leute[0])
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.VERTRAUENSFRAGE_SPERRE,
        antrag=antrag,
        gegenstand="Sperre nach § 7 Abs 10 lit g",
        optionen=JA_NEIN,
        frist=vf.sperrfrist_ende,
        angelegt_von=leute[0],
    )
    antwort = client.post(
        reverse("gremien:beschluss_stimme", args=[beschluss.pk]), {"option": "dafuer", "begruendung": "Ja."}, follow=True
    )
    beschluss.refresh_from_db()
    assert beschluss.status != BeschlussStatus.OFFEN and beschluss.stimmen.count() == 0
    assert "bereits ausgewertet" in antwort.content.decode()


def test_eine_abgelaufene_ruhende_rolle_liest_als_abgelaufene(client, ordnung):  # noqa: F811
    """Läuft die Zeit einer ruhenden Rolle ab, sagt das Band „endete am“ — nicht „ruht, solange sie ruht“."""
    leute = rat(1)
    rolle = ruhen_lassen(leute[0])
    rolle.endet_am = timezone.localdate() - tage(1)
    rolle.save(update_fields=["endet_am"])
    client.force_login(leute[0])
    inhalt = client.get(reverse("gremien:integritaet")).content.decode()
    assert "Ihre Rolle endete am" in inhalt and "Ihre Rolle ruht seit" not in inhalt


def test_neben_einer_ruhenden_rolle_gibt_es_keine_zweite_berufung_im_selben_rat(client, ordnung):  # noqa: F811
    """Das Ruhen lässt sich nicht durch eine neue Berufung in denselben Rat umgehen (lit f Z 1)."""
    leute = rat(1)
    ruhen_lassen(leute[0])
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    client.force_login(admin)
    antwort = client.post(
        reverse("gremien:rollen_aktion"),
        {
            "aktion": "berufen",
            "mitglied": leute[0].pk,
            "gremium": Gremium.INTEGRITAETSRAT,
            "endet_am": (timezone.localdate() + tage(365)).isoformat(),
        },
        follow=True,
    )
    assert Rolle.objects.filter(mitglied=leute[0], gremium=Gremium.INTEGRITAETSRAT).count() == 1
    assert "schon eine aktive Rolle (oder eine ruhende)" in antwort.content.decode()
    assert Rolle.hat(leute[0], Gremium.INTEGRITAETSRAT) is False
