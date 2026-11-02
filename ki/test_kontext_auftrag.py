"""Neue Textstände trennen, genaue Eingaben archivieren, Fehlläufe richtig zuordnen."""

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from gremien.models import Entwurf
from ki.anbieter import AnbieterFehler, AttrappenAnbieter
from ki.kontext import eingabe
from ki.models import KIAuftrag, KILauf, Zweck
from ki.test_kontext import vorschlag
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def a(ordnung, settings):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    return antrag_einbringen(mitglied_anlegen("quelle"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)


def test_antrag1_und_vorschlag1_koexistieren_idempotent_ohne_neue_anbieteraufrufe(a):
    f = vorschlag(a)
    original = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    neu = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=f)
    nochmal = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=f)
    assert neu.pk == nochmal.pk and neu.pk != original.pk
    assert neu.fassung_nummer == original.fassung_nummer == 1
    assert neu.vorschlagsfassung_id == f.pk and original.vorschlagsfassung_id is None
    assert KIAuftrag.objects.count() == 2 and not KILauf.objects.exists()
    assert neu.kontext == nochmal.kontext


def test_vorschlagsfassung_darf_keine_originalvektoren_ueberschreiben(a):
    with pytest.raises(ValueError, match="Textvektoren"):
        einreihen(Zweck.AEHNLICHKEIT, a, a.eingebracht_von, vorschlagsfassung=vorschlag(a))
    assert not KIAuftrag.objects.exists()


def test_rechtsbezug_erfolg_haelt_tatsaechliche_eingabe_vor_spaeterer_aenderung_fest(a):
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    vorher = eingabe(auftrag.kontext)
    a.titel = "Späterer Titel"
    a.save(update_fields=["titel"])
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Neuer Wortlaut")
    assert auftrag_ausfuehren(auftrag.pk) == "erledigt"
    auftrag.refresh_from_db()
    assert auftrag.lauf.eingabe == vorher
    assert auftrag.lauf.kontext == {"auftrag": auftrag.pk, "versuch": 1, "text": auftrag.kontext}
    assert "Späterer Titel" not in auftrag.lauf.eingabe


def test_fehlgeschlagener_anbieteraufruf_hat_denselben_kontext_wie_sein_auftrag(a, monkeypatch):
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von, vorschlagsfassung=vorschlag(a))
    def kaputt(*args):
        raise AnbieterFehler("Testausfall")
    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    assert auftrag_ausfuehren(auftrag.pk) == "verschoben"
    auftrag.refresh_from_db()
    assert not auftrag.lauf.erfolgreich
    assert auftrag.lauf.eingabe == eingabe(auftrag.kontext)
    assert auftrag.lauf.kontext["text"] == auftrag.kontext
    assert "sperrcode" not in auftrag.lauf.kontext


def test_fehler_ohne_neuen_lauf_verknuepft_keinen_frueheren_erfolg(a, settings):
    alter = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    auftrag_ausfuehren(alter.pk)
    alter.refresh_from_db()
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Neue Fassung")
    neu = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    assert auftrag_ausfuehren(neu.pk) == "verschoben"
    neu.refresh_from_db()
    assert neu.lauf_id is None
    assert KILauf.objects.count() == 1 and alter.lauf.erfolgreich


def test_legacyauftrag_bekommt_nur_im_neuen_lauf_einen_ehrlichen_kontext(a):
    alt = KIAuftrag.objects.create(
        zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von, fassung_nummer=1,
    )
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    assert alt.kontext == {}
    assert alt.lauf.eingabe == eingabe(alt.lauf.kontext["text"])
    assert alt.lauf.kontext["text"]["fassung_nummer"] == 1


def test_einbettung_verwendet_ebenfalls_den_festgehaltenen_antragstext(a):
    auftrag = einreihen(Zweck.AEHNLICHKEIT, a, a.eingebracht_von)
    vorher = auftrag.kontext
    a.titel = "Später geänderter Titel"
    a.save(update_fields=["titel"])
    assert auftrag_ausfuehren(auftrag.pk) == "erledigt"
    auftrag.refresh_from_db()
    assert auftrag.lauf.eingabe == f"{vorher['titel']}\n{vorher['wortlaut']}"
    assert auftrag.lauf.kontext["text"] == vorher


def test_einreichen_und_erneut_einreichen_beauftragen_je_die_veroeffentlichte_fassung(a):
    a.phase = "beratung"
    a.save(update_fields=["phase"])
    f = vorschlag(a)
    e = f.entwurf
    assert e.einreichen()
    assert KIAuftrag.objects.get().vorschlagsfassung_id == f.pk
    assert e.einreichen() and KIAuftrag.objects.count() == 1
    from gremien.models import EntwurfsFassung
    f2 = EntwurfsFassung.objects.create(
        entwurf=e, nummer=2, wortlaut="Eingereichte Überarbeitung", verfasst_von=a.eingebracht_von,
    )
    assert e.einreichen()
    assert set(KIAuftrag.objects.values_list("vorschlagsfassung_id", flat=True)) == {f.pk, f2.pk}
    assert not KILauf.objects.exists()


def test_ausserhalb_beratung_wird_kein_vorschlag_beauftragt(a):
    f = vorschlag(a)
    assert not f.entwurf.einreichen()
    assert not KIAuftrag.objects.exists()


def test_datenbankfehler_der_einreihung_hemmt_keinen_vorschlag_oder_aeussere_transaktion(a, monkeypatch):
    from ki import warteschlange
    a.phase = "beratung"
    a.save(update_fields=["phase"])
    e = vorschlag(a).entwurf
    def kaputt(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM absichtlich_fehlende_testtabelle")
    monkeypatch.setattr(warteschlange, "einreihen", kaputt)
    with transaction.atomic():
        assert e.einreichen()
        assert Entwurf.objects.get(pk=e.pk).eingereichte_fassung == 1
    assert not KIAuftrag.objects.exists()


def test_auftragsschutz_erlaubt_statuswechsel_aber_keine_neue_textquelle(a):
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    auftrag.versuche = 2
    auftrag.save(update_fields=["versuche"])
    auftrag.kontext = {}
    with pytest.raises(ValidationError):
        auftrag.save()
    with pytest.raises(ValidationError):
        KIAuftrag.objects.filter(pk=auftrag.pk).update(fassung_nummer=999)
    with pytest.raises(ValidationError):
        KIAuftrag.objects.filter(pk=auftrag.pk).update(kontext={})
    auftrag.refresh_from_db()
    auftrag.vorschlagsfassung = vorschlag(a)
    with pytest.raises(ValidationError):
        auftrag.save(update_fields=["vorschlagsfassung"])


def test_neuer_laufkontext_kann_nicht_nachtraeglich_umgeschrieben_werden(a):
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    auftrag_ausfuehren(auftrag.pk)
    lauf = KILauf.objects.get()
    lauf.kontext = {}
    with pytest.raises(ValidationError):
        lauf.save(update_fields=["kontext"])
    with pytest.raises(ValidationError):
        KILauf.objects.filter(pk=lauf.pk).update(kontext={})
    lauf.refresh_from_db()
    lauf.eingabe += " Nachträglich anderer Text"
    with pytest.raises(ValidationError):
        lauf.save(update_fields=["eingabe"])
