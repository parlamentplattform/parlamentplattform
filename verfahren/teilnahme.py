"""Geschützter Hauptwohnsitzkreis neuer Verfahren, getrennt von allgemeinen Rechten.

Ein Altverfahren ohne teilnahmegebiet wird niemals nachbefüllt.
"""

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from mitglieder.models import Bundesland, Gemeinde, Identitaetsstufe, Mitglied, Mitgliedsstatus, Wohnsitzart
from plattform_core.teilnehmerkreis import Gebiet, GebietsFehler, Gemeindestand, gebiet_fuer
from verfahren.models import Antrag, AuditEintrag, OertlicheTeilnahme, gegenstand_fuer, uebergangsregel_fuer


def wohnsitz_ohne_verzeichnis(mitglied) -> bool:
    """Altkonto mit österreichischem Wohnort nur als Freitext, ohne Eintrag im Gemeindeverzeichnis:
    Für neue örtliche Verfahren zählt es zu keinem Kreis, bis der Hauptwohnsitz gewählt ist (GP-055)."""
    if not getattr(mitglied, "is_authenticated", False) or not getattr(mitglied, "parteikonto", False):
        return False
    if mitglied.wohnsitz_id:
        return False
    return mitglied.wohnsitz_art_aktuell == Wohnsitzart.OESTERREICH or (
        not mitglied.wohnsitz_art and bool(mitglied.gemeinde)
    )


def ohne_oertliche_zuordnung(mitglied) -> bool:
    """Kein Hauptwohnsitz aus dem Gemeindeverzeichnis: Örtliche Kreise bleiben verschlossen, die
    Bundesebene offen — Sperrseite und Antragsseite nennen das als Grund (GP-056)."""
    if not getattr(mitglied, "is_authenticated", False):
        return False
    return not mitglied.wohnsitz_id or mitglied.wohnsitz_art_aktuell != Wohnsitzart.OESTERREICH


def gemeindestand(gemeinde):
    return Gemeindestand(gemeinde.kennziffer, gemeinde.name, gemeinde.bezirk, gemeinde.bundesland)


def hauptgebiet(mitglied, ebene, *, sperren=False):
    """Frischen eigenen Hauptwohnsitz lesen; keine Übernahme aus Neben-/Freitextorten."""
    if ebene == "bund":
        return gebiet_fuer(ebene, None, ())
    konten = Mitglied.objects.all()
    if sperren:
        konten = konten.select_for_update()
    aktuell = konten.get(pk=mitglied.pk)
    if not aktuell.parteikonto or aktuell.wohnsitz_art_aktuell != Wohnsitzart.OESTERREICH or not aktuell.wohnsitz_id:
        raise GebietsFehler(_("Für einen örtlichen Antrag ist ein gemeldeter Hauptwohnsitz erforderlich."))
    wiener_bezirk = aktuell.wiener_hauptbezirk
    if ebene == "bezirk" and aktuell.wohnsitz.bundesland == Bundesland.WIEN and not wiener_bezirk:
        raise GebietsFehler(_("Wählen Sie im Profil den Gemeindebezirk Ihres Wiener Hauptwohnsitzes."))
    stamm = tuple(gemeindestand(g) for g in Gemeinde.objects.filter(bundesland=aktuell.wohnsitz.bundesland))
    return gebiet_fuer(ebene, gemeindestand(aktuell.wohnsitz), stamm, wiener_bezirk=wiener_bezirk)


def konten_fuer(gebiet):
    """Nur örtliche Zuordnung, ohne Vorwegnahme allgemeiner Rechte."""
    konten = Mitglied.parteikonten.filter(testkonto=False)
    if gebiet.ebene == "bund":
        return konten
    konten = konten.filter(
        Q(wohnsitz_art=Wohnsitzart.OESTERREICH) | Q(wohnsitz_art=""),
        wohnsitz__kennziffer__in=gebiet.gemeinden,
    )
    if gebiet.wiener_bezirk:
        konten = konten.filter(wohnsitz__bundesland=Bundesland.WIEN, wiener_bezirk=gebiet.wiener_bezirk)
    return konten


def gebietsname(gebiet):
    return str(Bundesland(gebiet.land).label) if gebiet.ebene == "land" else gebiet.name


@transaction.atomic
def kreis_festhalten(antrag, *, _konten_ids=None):
    """Nur einen ausdrücklich als neu deklarierten Kreis einmalig atomar aufnehmen.

    Der Einbringungsweg muss das teilnahmegebiet bereits beim Erstellen setzen.
    None ist allein der historische Weg und darf hier nie aufgewertet werden.
    Bei der Einbringung entsprechen die übergebenen IDs der Grundgesamtheit
    vor Prüfung der allgemeinen Rechte für die anteilige Schwelle. Die
    umgebende Einbringungstransaktion umfasst alle Schritte.
    """
    aktuell = Antrag.objects.select_for_update().get(pk=antrag.pk)
    if aktuell.teilnahmegebiet is None:
        raise GebietsFehler("Altverfahren werden nicht mit einem neuen Kreis nachbefüllt.")
    gebiet = Gebiet.aus_dict(aktuell.teilnahmegebiet)
    if gebiet.ebene != aktuell.ebene:
        raise GebietsFehler("Gebiet und Antragsebene widersprechen einander.")
    if aktuell.teilnehmerkreis_am is not None or aktuell.oertlicher_kreis.exists():
        raise GebietsFehler("Der örtliche Teilnehmerkreis ist bereits festgehalten.")
    if gebiet.ebene != "bund":
        # Leere Wohnsitzart ist ein historischer, aus der vorhandenen Haupt-FK
        # hergeleiteter AT-Wohnsitz. Ausdrücklich Ausland/ohne festen Wohnsitz
        # bleibt auch bei einer veralteten FK außerhalb. Alle allgemeinen
        # Rechte werden separat geprüft: ungeprüfte Konten hier nicht verlieren.
        konten = konten_fuer(gebiet).values_list("pk", flat=True) if _konten_ids is None else _konten_ids
        OertlicheTeilnahme.objects.bulk_create(
            [OertlicheTeilnahme(antrag=aktuell, mitglied_id=pk) for pk in konten]
        )
    aktuell.teilnehmerkreis_am = aktuell.eingebracht_am
    aktuell.save(update_fields=["teilnehmerkreis_am"])
    antrag.teilnahmegebiet = aktuell.teilnahmegebiet
    antrag.teilnehmerkreis_am = aktuell.teilnehmerkreis_am
    AuditEintrag.anhaengen({
        "typ": "teilnehmerkreis_festgehalten", "antrag": antrag.pk,
        "fassung": gebiet.als_dict()["fassung"], "gebiet": gebiet.kennung,
        "festgehalten_am": aktuell.teilnehmerkreis_am.isoformat(),
        # Keine Mitgliedskennungen und keine Rückschlüsse auf Einzelstimmen.
    })


def oertlich_zulaessig(antrag, mitglied):
    if not getattr(mitglied, "parteikonto", False):
        return False
    if antrag.teilnahmegebiet is None:
        return True  # ausschließlich Altverfahren, keine neue Regel rückwirkend
    gebiet = Gebiet.aus_dict(antrag.teilnahmegebiet)
    if gebiet.ebene == "bund":
        return True
    if antrag.teilnehmerkreis_am is None or not getattr(mitglied, "is_authenticated", False):
        return False
    return antrag.oertlicher_kreis.filter(mitglied_id=mitglied.pk).exists()


def oertlich_begrenzt(antrag):
    # Alle aktuellen regionalen Fassungen sind gebunden; None allein ist der Altweg.
    return antrag.teilnahmegebiet is not None and antrag.ebene != "bund"


def eigene_kreise(mitglied, antraege):
    if mitglied is None or not mitglied.is_authenticated:
        return set()
    pks = [a.pk for a in antraege if oertlich_begrenzt(a) and a.teilnehmerkreis_am is not None]
    return set(OertlicheTeilnahme.objects.filter(
        antrag_id__in=pks, mitglied=mitglied,
    ).values_list("antrag_id", flat=True))


def mitglieder_im_kreis(antrag):
    konten = Mitglied.parteikonten.all()
    if antrag.teilnahmegebiet is None:
        return konten
    gebiet = Gebiet.aus_dict(antrag.teilnahmegebiet)
    if gebiet.ebene == "bund":
        return konten
    if antrag.teilnehmerkreis_am is None:
        return konten.none()
    return konten.filter(oertliche_verfahrenskreise__antrag=antrag)


def aktive_berechtigung(mitglied, gegenstand, stichtag, uebergang=False):
    return mitglied.is_active and mitglied.ist_stimmberechtigt(gegenstand, stichtag, uebergang=uebergang)


def stimmrecht_im_neuen_kreis(antrag, mitglied, *, frisch=False):
    """Historische Fachaufrufe bleiben bei ihren bisherigen Aufruferprüfungen."""
    if not oertlich_begrenzt(antrag):
        return True
    if antrag.stimmberechtigte_anzahl == 0 or not oertlich_zulaessig(antrag, mitglied):
        return False
    if frisch:
        mitglied = Mitglied.objects.filter(pk=mitglied.pk).first()
        if mitglied is None:
            return False
    return (
        aktive_berechtigung(
            mitglied, gegenstand_fuer(antrag), antrag.stichtag_der_stimmberechtigung(),
            uebergangsregel_fuer(antrag),
        )
        and not mitglied.adresswechsel_offen
    )


def berechtigte_zaehlen(antrag, gegenstand, stichtag, uebergang=False):
    """Genau dieselben allgemeinen Voraussetzungen wie die parteiweite Zählung."""
    konten = mitglieder_im_kreis(antrag).filter(
        is_active=True, status=Mitgliedsstatus.AKTIV, testkonto=False,
    ).exclude(beitritt=None).exclude(identitaetsstufe=Identitaetsstufe.UNGEPRUEFT)
    return sum(aktive_berechtigung(m, gegenstand, stichtag, uebergang) for m in konten)


def stimmbasis(antrag, gegenstand, stichtag, uebergang=False):
    if oertlich_begrenzt(antrag):
        return berechtigte_zaehlen(antrag, gegenstand, stichtag, uebergang)
    from mitglieder.models import stimmberechtigte_zaehlen

    return max(1, stimmberechtigte_zaehlen(gegenstand, stichtag, uebergang=uebergang))
