"""Geschützter Hauptwohnsitzkreis neuer Verfahren, getrennt von allgemeinen Rechten.

Die technische Vorbereitung ist noch nicht an die Einbringungs-/Handlungswege
angeschlossen. Ein Altverfahren ohne teilnahmegebiet wird niemals nachbefüllt.
"""

from django.db import transaction
from django.db.models import Q

from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus, Wohnsitzart
from plattform_core.teilnehmerkreis import Gebiet, GebietsFehler, Gemeindestand, gebiet_fuer
from verfahren.models import Antrag, AuditEintrag, OertlicheTeilnahme


def gemeindestand(gemeinde):
    return Gemeindestand(gemeinde.kennziffer, gemeinde.name, gemeinde.bezirk, gemeinde.bundesland)


def hauptgebiet(mitglied, ebene):
    """Frischen eigenen Hauptwohnsitz lesen; keine Übernahme aus Neben-/Freitextorten."""
    from mitglieder.models import Gemeinde

    if ebene == "bund":
        return gebiet_fuer(ebene, None, ())
    aktuell = Mitglied.objects.select_related("wohnsitz").get(pk=mitglied.pk)
    if aktuell.wohnsitz_art_aktuell != Wohnsitzart.OESTERREICH or not aktuell.wohnsitz_id:
        raise GebietsFehler("Ein tatsächlich gemeldeter Hauptwohnsitz fehlt.")
    stamm = tuple(gemeindestand(g) for g in Gemeinde.objects.all())
    return gebiet_fuer(ebene, gemeindestand(aktuell.wohnsitz), stamm)


@transaction.atomic
def kreis_festhalten(antrag):
    """Nur einen ausdrücklich als neu deklarierten Kreis einmalig atomar aufnehmen.

    Der Einbringungsweg muss das teilnahmegebiet bereits beim Erstellen setzen.
    None ist allein der historische Weg und darf hier nie aufgewertet werden.
    Erst danach die anteilige Unterstützungsschwelle aus genau diesem Kreis
    berechnen. Die umgebende Einbringungstransaktion umfasst alle Schritte.
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
        konten = Mitglied.objects.filter(
            Q(wohnsitz_art=Wohnsitzart.OESTERREICH) | Q(wohnsitz_art=""),
            wohnsitz__kennziffer__in=gebiet.gemeinden, testkonto=False,
        ).values_list("pk", flat=True)
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
    if antrag.teilnahmegebiet is None:
        return True  # ausschließlich Altverfahren, keine neue Regel rückwirkend
    gebiet = Gebiet.aus_dict(antrag.teilnahmegebiet)
    if gebiet.ebene == "bund":
        return True
    if antrag.teilnehmerkreis_am is None or not getattr(mitglied, "is_authenticated", False):
        return False
    return antrag.oertlicher_kreis.filter(mitglied_id=mitglied.pk).exists()


def mitglieder_im_kreis(antrag):
    konten = Mitglied.objects.all()
    if antrag.teilnahmegebiet is None:
        return konten
    gebiet = Gebiet.aus_dict(antrag.teilnahmegebiet)
    if gebiet.ebene == "bund":
        return konten
    if antrag.teilnehmerkreis_am is None:
        return konten.none()
    return konten.filter(oertliche_verfahrenskreise__antrag=antrag)


def berechtigte_zaehlen(antrag, gegenstand, stichtag, uebergang=False):
    """Genau dieselben allgemeinen Voraussetzungen wie die parteiweite Zählung."""
    konten = mitglieder_im_kreis(antrag).filter(
        is_active=True, status=Mitgliedsstatus.AKTIV, testkonto=False,
    ).exclude(beitritt=None).exclude(identitaetsstufe=Identitaetsstufe.UNGEPRUEFT)
    return sum(m.ist_stimmberechtigt(gegenstand, stichtag, uebergang=uebergang) for m in konten)
