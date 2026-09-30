"""Die Fachoperationen des Sitzungsmodus (FB-L5, S10b) — der einzige Schreibweg für Sitzungen,
Tagesordnungspunkte und Livemeldungen.

Jede Operation prüft selbst, ob der Mandatar schreiben darf (Mandat aktiv, Befugnis nicht ruhend
nach § 7 Abs 10 lit f Z 6), läuft unter der Zeilensperre der Sitzung und hängt einen Audit-Eintrag
an — nur Kennungen, nie Texte. Die Ansichten prüfen zusätzlich Besitz und Mitwirkung (Status aktiv,
Identität geprüft). Gelöscht oder geändert wird nichts: Punkte und Meldungen werden angehängt, eine
Korrektur ist eine neue Meldung (`berichtigt`), das Ende wird einmal gesetzt."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext as _

from mandatare.models import Aufgabe, Livemeldung, Mandat, Sitzung, Stimmverhalten, Tagesordnungspunkt
from plattform_core.sitzung import MELDUNG_ZEICHEN
from verfahren.models import AuditEintrag

TITEL_MAX = 200
STREAM_MAX = 500
#: So viele Punkte nimmt die Tagesordnung beim Start auf einmal — Missbrauchsgrenze, keine Stellgröße.
PUNKTE_BEIM_START_MAX = 60


class SitzungFehler(ValueError):
    """Die Handlung ist so nicht möglich — die Meldung sagt dem Mandatar, warum."""


def darf_live_melden(mandat: Mandat) -> bool:
    """Das Mandat ist aktiv, und die Befugnis ruht nicht (§ 7 Abs 10 lit f Z 6) — dieselbe Bedingung wie
    für die Mandatsfrage. Status und Identität des Mitglieds prüft die Ansicht."""
    return mandat.aktiv and mandat.vertrauen_entzogen_am is None


def stream_pruefen(url: str) -> str:
    """Leer oder ein https-Link auf einen fremden Rechner — der Link öffnet außerhalb der Plattform."""
    url = (url or "").strip()
    if not url:
        return ""
    teile = urlsplit(url)
    if len(url) > STREAM_MAX or teile.scheme != "https" or not teile.netloc:
        raise SitzungFehler(_("Der Stream-Link muss mit https:// beginnen."))
    return url


def _gesperrt(sitzung: Sitzung, jetzt) -> Sitzung:
    """Die Sitzung unter Zeilensperre neu laden und prüfen, dass sie läuft und geschrieben werden darf."""
    frisch = Sitzung.objects.select_for_update().select_related("mandat").get(pk=sitzung.pk)
    if not darf_live_melden(frisch.mandat):
        raise SitzungFehler(_("Der Live-Modus steht nur einem aktiven Mandat mit nicht ruhender Befugnis offen."))
    if not frisch.laeuft(jetzt):
        raise SitzungFehler(_("Die Sitzung ist beendet — ihr Protokoll bleibt, wie es ist."))
    return frisch


def sitzung_beginnen(
    mandat: Mandat, aufgabe: Aufgabe, stream: str = "", punkte: list[str] | None = None, jetzt=None
) -> Sitzung:
    """Den Live-Modus für einen angekündigten Sitzungstag einschalten — nur an diesem Tag (Wiener Zeit),
    einmal je Sitzungstag, und nicht, solange eine andere Sitzung desselben Mandats läuft."""
    jetzt = jetzt or timezone.now()
    stream = stream_pruefen(stream)
    titel = [t.strip()[:TITEL_MAX] for t in (punkte or []) if t.strip()]
    if len(titel) > PUNKTE_BEIM_START_MAX:
        raise SitzungFehler(_("Höchstens %(n)d Punkte auf einmal.") % {"n": PUNKTE_BEIM_START_MAX})
    with transaction.atomic():
        mandat = Mandat.objects.select_for_update().get(pk=mandat.pk)
        if not darf_live_melden(mandat):
            raise SitzungFehler(_("Der Live-Modus steht nur einem aktiven Mandat mit nicht ruhender Befugnis offen."))
        if aufgabe.mandat_id != mandat.pk or not aufgabe.sitzungstag or aufgabe.frist is None:
            raise SitzungFehler(_("Eine Sitzung gibt es nur zu einem angekündigten Sitzungstag."))
        if aufgabe.sitzungstag_datum != timezone.localdate(jetzt):
            raise SitzungFehler(_("Der Live-Modus lässt sich nur am Sitzungstag selbst einschalten."))
        if Sitzung.objects.filter(aufgabe=aufgabe).exists():
            raise SitzungFehler(_("Zu diesem Sitzungstag gibt es schon eine Sitzung."))
        for andere in Sitzung.objects.filter(mandat=mandat, ende__isnull=True):
            andere.fortschreiben(jetzt)
            if andere.laeuft(jetzt):
                raise SitzungFehler(_("Es läuft schon eine Sitzung — erst diese beenden."))
        try:
            with transaction.atomic():
                sitzung = Sitzung.objects.create(mandat=mandat, aufgabe=aufgabe, beginn=jetzt, stream=stream)
        except IntegrityError:
            raise SitzungFehler(_("Zu diesem Sitzungstag gibt es schon eine Sitzung.")) from None
        for nummer, t in enumerate(titel, start=1):
            Tagesordnungspunkt.objects.create(sitzung=sitzung, nummer=nummer, titel=t, erstellt_am=jetzt)
        AuditEintrag.anhaengen(
            {"typ": "sitzung_begonnen", "mandat": mandat.pk, "sitzung": sitzung.pk, "aufgabe": aufgabe.pk,
             "punkte": len(titel)}
        )
    return sitzung


def punkt_anhaengen(sitzung: Sitzung, titel: str, antrag=None, jetzt=None) -> Tagesordnungspunkt:
    """Einen Tagesordnungspunkt anhängen — die nächste Nummer, nie eine Lücke, nie eine Änderung."""
    jetzt = jetzt or timezone.now()
    titel = (titel or "").strip()[:TITEL_MAX]
    if not titel:
        raise SitzungFehler(_("Der Punkt braucht einen Titel."))
    with transaction.atomic():
        sitzung = _gesperrt(sitzung, jetzt)
        nummer = (sitzung.punkte.aggregate(n=Max("nummer"))["n"] or 0) + 1
        punkt = Tagesordnungspunkt.objects.create(
            sitzung=sitzung, nummer=nummer, titel=titel, antrag=antrag, erstellt_am=jetzt
        )
        ereignis = {"typ": "tagesordnungspunkt", "mandat": sitzung.mandat_id, "sitzung": sitzung.pk, "punkt": punkt.pk}
        if antrag is not None:
            ereignis["antrag"] = antrag.pk
        AuditEintrag.anhaengen(ereignis)
    return punkt


def punkt_verknuepfen(punkt: Tagesordnungspunkt, antrag, jetzt=None) -> None:
    """Den Antrag eines ohne Antrag angelegten Punkts nachreichen — einmal; ein gesetzter bleibt."""
    jetzt = jetzt or timezone.now()
    with transaction.atomic():
        _gesperrt(punkt.sitzung, jetzt)
        frisch = Tagesordnungspunkt.objects.select_for_update().get(pk=punkt.pk)
        if frisch.antrag_id is not None:
            raise SitzungFehler(_("Der Punkt ist schon mit einem Antrag verknüpft."))
        frisch.antrag = antrag
        frisch.save(update_fields=["antrag"])
        AuditEintrag.anhaengen(
            {"typ": "tagesordnungspunkt_verknuepft", "mandat": frisch.sitzung.mandat_id, "sitzung": frisch.sitzung_id,
             "punkt": frisch.pk, "antrag": antrag.pk}
        )
    punkt.antrag = antrag


def meldung_abgeben(
    sitzung: Sitzung,
    text: str,
    punkt: Tagesordnungspunkt | None = None,
    stimme: str = "",
    abgestimmt: bool = False,
    berichtigt: Livemeldung | None = None,
    jetzt=None,
) -> Livemeldung:
    """Eine Livemeldung — höchstens 280 Zeichen, optional zu einem Punkt, mit angekündigter oder
    abgegebener Stimme. `berichtigt` nimmt eine frühere Meldung derselben Sitzung zurück; jede Meldung
    lässt sich einmal berichtigen, die Berichtigung selbst wieder."""
    jetzt = jetzt or timezone.now()
    text = (text or "").strip()
    if not text:
        raise SitzungFehler(_("Die Meldung braucht Text."))
    if len(text) > MELDUNG_ZEICHEN:
        raise SitzungFehler(_("Eine Meldung hat höchstens %(n)d Zeichen.") % {"n": MELDUNG_ZEICHEN})
    if stimme and stimme not in Stimmverhalten.values:
        raise SitzungFehler(_("Unbekannte Stimme."))
    if abgestimmt and not stimme:
        raise SitzungFehler(_("„Abgestimmt“ braucht die Stimme."))
    with transaction.atomic():
        sitzung = _gesperrt(sitzung, jetzt)
        if punkt is not None and punkt.sitzung_id != sitzung.pk:
            raise SitzungFehler(_("Der Punkt gehört nicht zu dieser Sitzung."))
        if berichtigt is not None:
            if berichtigt.sitzung_id != sitzung.pk:
                raise SitzungFehler(_("Berichtigt werden nur Meldungen derselben Sitzung."))
            if Livemeldung.objects.filter(berichtigt=berichtigt).exists():
                raise SitzungFehler(_("Diese Meldung ist schon berichtigt."))
        meldung = Livemeldung.objects.create(
            sitzung=sitzung,
            punkt=punkt,
            zeitpunkt=jetzt,
            text=text,
            stimme=stimme,
            abgestimmt=bool(abgestimmt),
            berichtigt=berichtigt,
        )
        ereignis = {"typ": "livemeldung", "mandat": sitzung.mandat_id, "sitzung": sitzung.pk, "meldung": meldung.pk}
        if berichtigt is not None:
            ereignis["berichtigt"] = berichtigt.pk
        AuditEintrag.anhaengen(ereignis)
    return meldung


def stream_setzen(sitzung: Sitzung, url: str, jetzt=None) -> None:
    """Den Link auf den amtlichen Stream setzen oder ändern, solange die Sitzung läuft."""
    jetzt = jetzt or timezone.now()
    url = stream_pruefen(url)
    with transaction.atomic():
        frisch = _gesperrt(sitzung, jetzt)
        frisch.stream = url
        frisch.save(update_fields=["stream"])
        AuditEintrag.anhaengen({"typ": "sitzung_stream", "mandat": frisch.mandat_id, "sitzung": frisch.pk})
    sitzung.stream = url


def sitzung_beenden(sitzung: Sitzung, jetzt=None) -> None:
    """Den Live-Modus beenden — das Ende wird einmal gesetzt, danach ist die Seite das Protokoll.
    Ein Mandatar, dessen Befugnis inzwischen ruht, darf trotzdem beenden: Beenden schreibt nichts Neues."""
    jetzt = jetzt or timezone.now()
    with transaction.atomic():
        frisch = Sitzung.objects.select_for_update().get(pk=sitzung.pk)
        if not frisch.laeuft(jetzt):
            raise SitzungFehler(_("Die Sitzung ist schon beendet."))
        frisch.ende = jetzt
        frisch.save(update_fields=["ende"])
        AuditEintrag.anhaengen({"typ": "sitzung_beendet", "mandat": frisch.mandat_id, "sitzung": frisch.pk})
    sitzung.ende = jetzt
