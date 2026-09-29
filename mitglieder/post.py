"""Mitgliederpost: dauerhafte Aufträge nach Datenbank-Commit (ADR-010).

Erfolgsstempel bezeichnen die tatsächlich vom Mailbackend angenommene Nachricht.
Fehler und fehlende PDF-Beilagen werden über den Postausgang erneut versucht.
"""

from __future__ import annotations

import logging
from datetime import date

from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _

from mitglieder.ausweis import ausweis_erstellbar, ausweis_pdf, dateiname
from mitglieder.auth_flows import beitragsreferenz
from mitglieder.mail import EmailMessage
from mitglieder.models import Bundesland, Mitglied, Mitgliedsstatus
from parameter.models import zahl
from plattform_core.eligibility import ANWARTSCHAFT_MONATE, Gegenstand, monate_addieren
from verfahren.models import Antrag, AuditEintrag, Ebene

log = logging.getLogger(__name__)

SCHLUSS = "Direkte Demokratie Österreich — Wir sind das Werkzeug."


def _ab(datum: date, heute: date) -> str:
    """„ab sofort“, wenn der Tag erreicht ist, sonst „ab dd.mm.yyyy“."""
    if datum <= heute:
        return _("ab sofort")
    return _("ab %(datum)s") % {"datum": formats.date_format(datum, "d.m.Y")}


def stimmrechts_satz(mitglied: Mitglied, heute: date | None = None) -> str:
    """Ab wann das Stimmrecht besteht — je Gegenstand aus Beitritt und Anwartschaft (§ 4 Abs 4),
    oder mit dem Satzungsbezug, solange die Übergangsregel des § 4 Abs 4 lit d gilt."""
    heute = heute or timezone.localdate()
    if settings.DDOE_UEBERGANGSREGEL:
        return _(
            "Nach Ihrer Freischaltung können Sie ohne zusätzliche Wartefrist abstimmen und wählen. "
            "Das gilt während unserer Aufbauphase. Später entscheiden die Mitglieder gemeinsam "
            "über die dauerhaften Verfahrensregeln."
        )
    beitritt = mitglied.beitritt or heute
    return _(
        "Über inhaltliche Vorschläge können Sie %(sachfragen)s abstimmen. "
        "An Personenwahlen und Abstimmungen über Änderungen der Satzung oder die Auflösung der Partei "
        "können Sie %(personenwahlen)s teilnehmen. Die unterschiedlichen Starttermine ergeben sich "
        "aus den Wartefristen ab Ihrem Beitritt."
    ) % {
        "sachfragen": _ab(monate_addieren(beitritt, ANWARTSCHAFT_MONATE[Gegenstand.SACHFRAGE]), heute),
        "personenwahlen": _ab(monate_addieren(beitritt, ANWARTSCHAFT_MONATE[Gegenstand.PERSONENWAHL]), heute),
    }


def _anrede(mitglied: Mitglied) -> str:
    """Der Brief geht an den Menschen selbst: Klarname wie in der Link-Mail; ohne Namen der Anzeigename."""
    return mitglied.get_full_name() or mitglied.anzeigename


def _zustellbar(mitglied: Mitglied, stempel: str) -> bool:
    return (
        mitglied.is_active
        and bool(mitglied.email)
        and mitglied.status not in (Mitgliedsstatus.AUSGESCHLOSSEN, Mitgliedsstatus.AUSGETRETEN)
        and getattr(mitglied, stempel) is None
    )


def _senden(mitglied: Mitglied, art: str, betreff: str, text: str, anhang: tuple[str, bytes] | None = None) -> bool:
    """Ein Brief, wahlweise mit einem PDF-Anhang (Dateiname, Inhalt) — der Mitgliedsausweis."""
    try:
        nachricht = EmailMessage(betreff, text, settings.DEFAULT_FROM_EMAIL, [mitglied.email])
        if anhang is not None:
            nachricht.attach(anhang[0], anhang[1], "application/pdf")
        if nachricht.send() != 1:
            return False
    except OSError:
        log.exception("Brief „%s“ an Mitglied %s nicht versendbar.", art, mitglied.pk)
        return False
    AuditEintrag.anhaengen({"typ": "post", "art": art, "mitglied": mitglied.pk, "anhang": anhang is not None})
    return True


def _ausweis_anhang(mitglied: Mitglied) -> tuple[str, bytes] | None:
    """Der Mitgliedsausweis mit einem Namen auf der Karte. Scheitert die Erzeugung
    (Logo-Datei, Zeichnung, Datenbank), geht
    der Brief ohne Anhang, nicht gar nicht: Der Freischaltungsbrief ist wichtiger als die Beilage, und
    die Störung steht im Protokoll."""
    if not ausweis_erstellbar(mitglied):
        return None
    try:
        return dateiname(mitglied), ausweis_pdf(mitglied)
    except Exception:  # jede Störung der Beilage — der Brief geht trotzdem
        log.exception("Mitgliedsausweis für Mitglied %s nicht erzeugbar.", mitglied.pk)
        return None


def _stempeln(mitglied: Mitglied, stempel: str) -> None:
    setattr(mitglied, stempel, timezone.now())
    mitglied.save(update_fields=[stempel])


def _brief(vorlage: str, kontext: dict) -> str:
    basis = settings.DDOE_BASIS_URL.rstrip("/")
    return render_to_string(vorlage, {**kontext, "basis": basis, "schluss": SCHLUSS}).strip() + "\n"


def _willkommen_brief(mitglied: Mitglied, anhang=None, vorschau=False) -> bool:
    """Nach der E-Mail-Bestätigung: was ab sofort gilt, ab wann das Stimmrecht besteht, dass es
    eine geprüfte Identität braucht (Beitrag, persönliche Referenz), drei Einstiege. Einmal je Konto."""
    if not vorschau and not _zustellbar(mitglied, "willkommen_post_am"):
        return False
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/willkommen.txt",
            {
                "name": _anrede(mitglied),
                "anzeigename": mitglied.anzeigename,
                "stimmrecht": stimmrechts_satz(mitglied),
                "referenz": beitragsreferenz(mitglied),
                "ausweis": anhang is not None,
            },
        )
        betreff = _("Willkommen — ParlamentPlattform")
    if vorschau:
        betreff = _("Vorschau: %(betreff)s") % {"betreff": betreff}
    return _senden(mitglied, "ausweis_vorschau" if vorschau else "willkommen", betreff, text, anhang)


def _freischaltung_brief(mitglied: Mitglied, anhang=None, vorschau=False) -> bool:
    """Beim ersten Wechsel von „ungeprüft“ auf eine geprüfte Stufe — gleich ob durch den
    Bankabgleich oder die Verwaltung: Prüfung abgeschlossen, Stufe, Stimmrecht ab wann. Einmal je Konto."""
    if not vorschau and not _zustellbar(mitglied, "freischaltung_post_am"):
        return False
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/freischaltung.txt",
            {
                "name": _anrede(mitglied),
                "stufe": mitglied.get_identitaetsstufe_display(),
                "stimmrecht": stimmrechts_satz(mitglied),
                # Die Verwaltung kann ein pausiertes Konto freischalten (Beitrag ausständig): Dann
                # ruhen die Mitwirkungsrechte weiter (F-51), und der Brief sagt das statt „ab sofort“.
                "ruht": mitglied.status != Mitgliedsstatus.AKTIV,
                "ausweis": anhang is not None,
                "nummer": mitglied.mitgliedsnummer_text,
            },
        )
        betreff = _("Ihre Prüfung ist abgeschlossen — ParlamentPlattform")
    if vorschau:
        betreff = _("Vorschau: %(betreff)s") % {"betreff": betreff}
    return _senden(mitglied, "ausweis_vorschau" if vorschau else "freischaltung", betreff, text, anhang)


def vertrauensfrage_senden(mandat, antrag) -> bool:
    """§ 7 Abs 10 lit b: Der Mandatsträger wird bei Einbringung einer Vertrauensfrage unverzüglich
    verständigt — ohne den Inhalt des Antrags, nur mit dem Link zur Antragsseite (dort steht alles,
    öffentlich, samt dem Feld für die Stellungnahme nach lit d). Genau einmal je Antrag: Der Stempel
    `Vertrauensfrage.verstaendigt_am` hält den ersten Versandversuch fest. Kein Versand an inaktive
    Konten; scheitert der Versand, läuft das Verfahren weiter (Untätigkeit hemmt nie)."""
    from mandatare.models import Vertrauensfrage

    try:
        vf = antrag.vertrauensfrage  # dieselbe Instanz wie beim Einbringen, wenn sie schon geladen ist
    except Vertrauensfrage.DoesNotExist:
        return False
    if vf.mandat_id != mandat.pk or vf.verstaendigt_am is not None:
        return False
    mitglied = mandat.mitglied
    vf.verstaendigt_am = timezone.now()
    vf.save(update_fields=["verstaendigt_am"])
    if not (
        mitglied.is_active
        and bool(mitglied.email)
        and mitglied.status not in (Mitgliedsstatus.AUSGESCHLOSSEN, Mitgliedsstatus.AUSGETRETEN)
    ):
        return False
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/vertrauensfrage.txt",
            {
                "name": _anrede(mitglied),
                "mandat": f"{mandat.bezeichnung}, {mandat.gebiet or mandat.get_ebene_display()}",
                "antrag": antrag.pk,
            },
        )
        betreff = _("Vertrauensfrage zu Ihrem Mandat — ParlamentPlattform")
    return _senden(mitglied, "vertrauensfrage", betreff, text)


# ── Verfahrenspost mit Einwilligung (Anweisung des Gründers 28.9.2026) ───────────────────────────


def neuer_antrag_brief(mitglied: Mitglied, antrag: Antrag) -> bool:
    """„Neuer Antrag in Ihrer Region“: Titel, Ebene und Gebiet, wer ihn eingebracht hat (Anzeigename),
    der Link — und warum der Brief kommt (Wohnsitz betroffen) samt dem Weg, ihn im Profil abzubestellen.
    Kein Werbesatz, kein Antragstext: Der steht öffentlich auf der Antragsseite."""
    with translation.override("de"):
        bund = antrag.ebene == Ebene.BUND.value
        text = _brief(
            "mitglieder/post/neuer_antrag.txt",
            {
                "name": _anrede(mitglied),
                "titel": antrag.titel,
                "ebene": antrag.get_ebene_display(),
                "gebiet": antrag.gebiet,
                "bund": bund,
                "eingebracht_von": antrag.eingebracht_von.anzeigename,
                "link": settings.DDOE_BASIS_URL.rstrip("/") + reverse("verfahren:antrag", kwargs={"pk": antrag.pk}),
            },
        )
        betreff = (
            _("Neuer Antrag für ganz Österreich — ParlamentPlattform")
            if bund
            else _("Neuer Antrag in Ihrer Region — ParlamentPlattform")
        )
    return _senden(mitglied, "neuer_antrag", betreff, text)


def rechtsbezug_brief(mitglied: Mitglied, antrag: Antrag) -> bool:
    """„Zukunftswerkstatt: betroffene Gesetze zu Ihrem Antrag“ — die Normen des jüngsten erfolgreichen
    Laufs, jede als nicht verifiziert, der Link zur Antragsseite, die Kennzeichnung als KI-Vorschlag und
    der Weg zum Abbestellen. Liegt (noch) kein Ergebnis vor, geht kein Brief; der Postausgang versucht
    es später erneut."""
    from ki.rechtsbezug import rechtsbezug_fuer

    ergebnis = rechtsbezug_fuer(antrag)
    if ergebnis is None:
        return False
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/rechtsbezug.txt",
            {
                "name": _anrede(mitglied),
                "titel": antrag.titel,
                "normen": ergebnis["normen"],
                "hinweis": ergebnis["hinweis"],
                "unsicherheit": ergebnis["unsicherheit_wort"],
                "modell": ergebnis["modell"],
                "auftrag_version": ergebnis["auftrag_version"],
                # Kontextstand (§ 6 Abs 11 lit b): Datum des Laufs in Wiener Zeit und die geprüfte Fassung
                "stand": formats.date_format(timezone.localtime(ergebnis["stand"]), "d.m.Y, H:i"),
                "fassung": ergebnis["fassung"],
                "link": settings.DDOE_BASIS_URL.rstrip("/")
                + reverse("verfahren:antrag", kwargs={"pk": antrag.pk})
                + "#rechtsbezug",
            },
        )
        betreff = _("Zukunftswerkstatt: betroffene Gesetze zu Ihrem Antrag")
    return _senden(mitglied, "rechtsbezug", betreff, text)


def beitragserinnerung_brief(mitglied: Mitglied) -> bool:
    """Die Beitragserinnerung der Verwaltung (§ 4 Abs 3): Beitragsseite, persönliche Referenz, der
    Hinweis, dass die Höhe Selbsteinschätzung bleibt — und der Weg zum Abbestellen im Profil."""
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/beitragserinnerung.txt",
            {"name": mitglied.first_name or mitglied.anzeigename, "referenz": beitragsreferenz(mitglied)},
        )
        betreff = _("Erinnerung: Ihr Mitgliedsbeitrag bei der DDÖ")
    return _senden(mitglied, "beitragserinnerung", betreff, text)


def _gemeinde_des_antrags(antrag: Antrag):
    """Die Gemeinde eines Gemeinde-Antrags als Verweis ins Verzeichnis — über den Wohnsitz oder
    Nebenwohnsitz des Antragstellers, denn `Antrag.gebiet` trägt nur den Namen, und Gemeindenamen sind
    nicht eindeutig. Ohne Treffer (Altbestand, geänderter Wohnsitz) bleibt der Namensvergleich."""
    m = antrag.eingebracht_von
    for g in (m.wohnsitz if m.wohnsitz_id else None, m.nebenwohnsitz if m.nebenwohnsitz_id else None):
        if g is not None and g.name == antrag.gebiet:
            return g
    return None


def region_empfaenger(antrag: Antrag):
    """Wer von einem neuen Antrag betroffen ist (§ 14 Abs 3): aktive oder pausierte, echte Konten mit
    E-Mail-Einwilligung, deren Wohnsitz im Gebiet des Antrags liegt — nie der Antragsteller. Der
    Nebenwohnsitz zählt zusätzlich, sobald `region-nebenwohnsitz-zaehlt` auf 1 steht; ein Antrag für
    ganz Österreich geht an alle, solange `post-neuer-antrag-bund` auf 1 steht. Ungeprüfte Konten
    sind dabei: Betroffen ist, wer dort wohnt, nicht, wer schon stimmen darf."""
    basis = (
        Mitglied.objects.filter(
            is_active=True,
            testkonto=False,
            post_einwilligung=True,
            status__in=(Mitgliedsstatus.AKTIV, Mitgliedsstatus.PAUSIERT),
        )
        .exclude(pk=antrag.eingebracht_von_id)
        .exclude(email="")
        .order_by("pk")
    )
    ebene, gebiet = antrag.ebene, antrag.gebiet
    if ebene == Ebene.BUND.value:
        return basis if zahl("post-neuer-antrag-bund", 1) == 1 else basis.none()
    if not gebiet:
        return basis.none()
    neben = zahl("region-nebenwohnsitz-zaehlt", 0) == 1
    if ebene == Ebene.LAND.value:
        schluessel = {str(label): wert for wert, label in Bundesland.choices}.get(gebiet)
        if schluessel is None:
            return basis.none()
        treffer = Q(bundesland=schluessel) | Q(wohnsitz__bundesland=schluessel)
        if neben:
            treffer |= Q(nebenwohnsitz__bundesland=schluessel)
    elif ebene == Ebene.BEZIRK.value:
        treffer = Q(wohnsitz__bezirk=gebiet)
        if neben:
            treffer |= Q(nebenwohnsitz__bezirk=gebiet)
    else:
        g = _gemeinde_des_antrags(antrag)
        if g is not None:
            treffer = Q(wohnsitz=g)
            if neben:
                treffer |= Q(nebenwohnsitz=g)
        else:
            treffer = Q(wohnsitz__name=gebiet) | Q(wohnsitz__isnull=True, gemeinde=gebiet)
            if neben:
                treffer |= Q(nebenwohnsitz__name=gebiet)
    return basis.filter(treffer).distinct()


def region_benachrichtigen(antrag: Antrag) -> int:
    """Je betroffenem Mitglied ein Postauftrag „neuer_antrag“ (Bezug `antrag:<pk>`, genau einmal je
    Antrag und Konto); zugestellt wird im Hintergrundlauf. Gibt die Zahl der neu angelegten Aufträge
    zurück und hält sie im Audit fest — ohne Personenbezug."""
    from mitglieder.postausgang import beauftragen

    anzahl = sum(bool(beauftragen(m, "neuer_antrag", antrag=antrag)) for m in region_empfaenger(antrag))
    AuditEintrag.anhaengen({"typ": "post_neuer_antrag", "antrag": antrag.pk, "empfaenger": anzahl})
    return anzahl


def willkommen_senden(mitglied: Mitglied) -> bool:
    from mitglieder.postausgang import beauftragen
    return beauftragen(mitglied, "willkommen")


def freischaltung_senden(mitglied: Mitglied) -> bool:
    from mitglieder.postausgang import beauftragen
    return beauftragen(mitglied, "freischaltung")
