"""Zweite Behebungsrunde der Gesamtprüfung, Paket „nachweis“: der Prüfstand der Audit-Kette.

GP-157: Steht die Prüfung der Kette still, sagte `/audit/` weiter „intakt“ und nannte die seither
angehängten Einträge nicht. GP-158 (Rest): Der Grund „zeit“ hat einen lesbaren Text wie die übrigen."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from verfahren import audit_pruefung
from verfahren.audit_pruefung import LAUF, lauf
from verfahren.hintergrund import LAEUFE, ausfuehren
from verfahren.models import AuditEintrag, Hintergrundlauf

pytestmark = pytest.mark.django_db


def _pruefzeile():
    return Hintergrundlauf.objects.get(name=LAUF)


def _geprueft_vor(tage, jetzt=None):
    jetzt = jetzt or timezone.now()
    zeile = _pruefzeile()
    stand = dict(zeile.zuletzt_stand)
    stand["geprueft_am"] = (jetzt - timedelta(days=tage)).isoformat()
    Hintergrundlauf.objects.filter(name=LAUF).update(zuletzt_stand=stand)


def _kette_geprueft(n=3):
    for i in range(n):
        AuditEintrag.anhaengen({"typ": "probe", "nr": i})
    assert ausfuehren(next(la for la in LAEUFE if la.name == LAUF))


def _pruefabsatz(client):
    inhalt = client.get(reverse("verfahren:audit")).content.decode()
    anfang = inhalt.index('id="pruefung"')
    return inhalt[inhalt.rindex("<p", 0, anfang): inhalt.index("</p>", anfang)]


# ── GP-157: überfälliger Prüfstand ────────────────────────────────────────────────────────


def test_ein_45_tage_alter_pruefstand_ist_auf_der_seite_ueberfaellig(client):
    _kette_geprueft()
    _geprueft_vor(45)
    for i in range(5):
        AuditEintrag.anhaengen({"typ": "probe", "danach": i})
    absatz = _pruefabsatz(client)
    assert "ueberfaellig" in absatz and "badge-warn" in absatz
    assert "überfällig" in absatz
    assert "5 Einträge ungeprüft" in absatz


def test_ein_frischer_pruefstand_ist_nicht_ueberfaellig(client):
    _kette_geprueft()
    _geprueft_vor(1)
    absatz = _pruefabsatz(client)
    assert "überfällig" not in absatz and "ueberfaellig" not in absatz


def test_die_grenze_sind_zwei_prueftakte():
    jetzt = timezone.now()
    tage = audit_pruefung.PRUEFSTAND_UEBERFAELLIG_TAKTE
    assert tage == 2
    assert not audit_pruefung.pruefstand_ueberfaellig({"geprueft_am": (jetzt - timedelta(hours=47)).isoformat()}, jetzt)
    assert audit_pruefung.pruefstand_ueberfaellig({"geprueft_am": (jetzt - timedelta(hours=49)).isoformat()}, jetzt)


def test_altbestand_ohne_oder_mit_unlesbarem_pruefzeitpunkt(client):
    """Ein Stand von früher ohne `geprueft_am` oder mit unlesbarem Wert wirft nicht."""
    jetzt = timezone.now()
    assert not audit_pruefung.pruefstand_ueberfaellig({}, jetzt)
    assert not audit_pruefung.pruefstand_ueberfaellig({"geprueft_am": "kaputt"}, jetzt)
    assert not audit_pruefung.pruefstand_ueberfaellig({"geprueft_am": None}, jetzt)
    Hintergrundlauf.objects.create(name=LAUF, zuletzt_stand={"intakt": True, "geprueft_bis": 0, "eintraege": 0,
                                                             "geprueft_am": "kaputt"})
    assert client.get(reverse("verfahren:audit")).status_code == 200


def test_ein_gebrochener_alter_stand_bleibt_gebrochen_und_ist_ueberfaellig(client):
    _kette_geprueft()
    eintrag = AuditEintrag.objects.order_by("lfd")[1]
    AuditEintrag._base_manager.filter(pk=eintrag.pk).update(ereignis={**eintrag.ereignis, "nr": 99})
    lauf_stand = audit_pruefung.pruefen(voll=True)
    Hintergrundlauf.objects.filter(name=LAUF).update(zuletzt_stand=lauf_stand)
    _geprueft_vor(45)
    absatz = _pruefabsatz(client)
    assert "gebrochen" in absatz and "überfällig" in absatz


# ── GP-158 (Rest): lesbarer Grund für eine abweichende Zeitspalte ─────────────────────────


def test_jeder_bruchgrund_hat_einen_lesbaren_text():
    assert set(audit_pruefung.GRUENDE) >= {"hash", "vorgaenger", "anker", "zeit"}
    assert all(len(text) > 20 and text != grund for grund, text in audit_pruefung.GRUENDE.items())
    assert "Zeit" in audit_pruefung.GRUENDE["zeit"]


def test_der_lauf_meldet_den_grund_zeit():
    _kette_geprueft()
    eintrag = AuditEintrag.objects.order_by("lfd")[1]
    AuditEintrag._base_manager.filter(pk=eintrag.pk).update(zeit=eintrag.zeit - timedelta(days=400))
    Hintergrundlauf.objects.filter(name=LAUF).update(zuletzt_stand={})
    stand = lauf()
    assert stand["intakt"] is False and stand["grund"] == "zeit" and stand["bruch"] == eintrag.lfd


def test_der_befehl_nennt_den_grund_zeit_in_worten():
    """GP-158: Der Prüfbefehl führt keine eigene Liste der Gründe — er liest die der Prüfung."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    from verfahren.management.commands import audit_pruefen

    _kette_geprueft()
    eintrag = AuditEintrag.objects.order_by("lfd")[1]
    AuditEintrag._base_manager.filter(pk=eintrag.pk).update(zeit=eintrag.zeit - timedelta(days=400))
    with pytest.raises(CommandError) as fehler:
        call_command("audit_pruefen", "--voll")
    meldung = str(fehler.value)
    assert f"bei Eintrag {eintrag.lfd}: " in meldung
    assert str(audit_pruefung.GRUENDE["zeit"]) in meldung
    assert not hasattr(audit_pruefen, "GRUENDE") or audit_pruefen.GRUENDE is audit_pruefung.GRUENDE


# ── GP-009 (Auflage): der frei geschriebene Grund einer Streichung von der Fachliste ──────

STREICHUNG = {"typ": "fachliste_gestrichen", "eintrag": 7, "grund": "Frau Beispielname ist verzogen.", "durch": 815}


def test_der_grund_einer_streichung_von_der_fachliste_ist_oeffentlich_geschwaerzt(client):
    eintrag = AuditEintrag.anhaengen(dict(STREICHUNG))
    assert "salz" in eintrag.ereignis  # schutzwürdig: gesalzen, der Hash darf offen stehen
    seite = client.get(reverse("verfahren:audit")).content.decode()
    assert "Beispielname" not in seite and "<dt>grund</dt><dd>•</dd>" in seite
    antwort = client.get(reverse("verfahren:audit_json"))
    assert "Beispielname" not in antwort.content.decode()
    zeile = antwort.json()["eintraege"][-1]
    assert zeile["typ"] == "fachliste_gestrichen" and zeile["geschwaerzt"] is True
    assert zeile["grund"] == "•" and zeile["ereignis"]["grund"] == "•" and zeile["ereignis"]["eintrag"] == 7
    assert zeile["hash"] == eintrag.hash


def test_die_schwaerzung_wirkt_auch_auf_frueher_geschriebene_streichungen(client, monkeypatch):
    """Altbestand: Ein Eintrag, der beim Schreiben noch nicht als schutzwürdig galt und kein Salz
    trägt, zeigt öffentlich weder den Grund noch seinen Hash (sonst ließe er sich durchprobieren)."""
    from verfahren import audit_oeffentlich

    with monkeypatch.context() as frueher:
        frueher.setattr(audit_oeffentlich, "PERSONENGRUENDE", ("verwaltung", "rolle_beendet"))
        alt = AuditEintrag.anhaengen({"typ": "fachliste_gestrichen", "eintrag": 8, "grund": "Herr Beispielname pausiert."})
    assert "salz" not in alt.ereignis
    danach = AuditEintrag.anhaengen({"typ": "probe"})
    zeilen = {z["lfd"]: z for z in client.get(reverse("verfahren:audit_json")).json()["eintraege"]}
    assert zeilen[alt.lfd]["grund"] == "•" and zeilen[alt.lfd]["hash"] is None
    assert zeilen[danach.lfd]["vorgaenger"] is None
    assert "Beispielname" not in client.get(reverse("verfahren:audit")).content.decode()
