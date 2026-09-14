"""Post an Mitglieder (FB-K7): der Willkommensbrief und der Freischaltungsbrief.

Grundsätze:
- Versand ist Höflichkeit, kein Vollzug: Scheitert er (SMTP, Netz — alles `OSError`), läuft
  der Vorgang weiter, und der Brief wird nicht nachgeholt. Der Stempel am Konto
  (`willkommen_post_am`, `freischaltung_post_am`) hält den ERSTEN Versandversuch fest — es
  gibt genau einen Brief je Konto, auch bei doppeltem Klick auf den Link, bei erneuter
  Verbuchung oder beim Stufenwechsel geprüft → Präsenz.
- Immer Deutsch: Ein Sprachfeld am Konto gibt es nicht (die Sprache merkt sich das Gerät,
  nicht das Konto — Profilkarte „Sprache“); darum `translation.override("de")`. Die Texte
  laufen trotzdem durch den Katalog, damit ein späteres Sprachfeld nur den Override ersetzt.
- Ehrlich: Ab wann das Stimmrecht besteht, rechnet `plattform_core.eligibility` aus dem
  Beitritt (Sachfragen 3, Personenwahlen 12 Monate); solange `DDOE_UEBERGANGSREGEL` gilt,
  nennt der Brief den Satzungsbezug (§ 4 Abs 4 lit d) statt Daten, die nicht gelten.
- Audit `{"typ": "post", "art": …, "mitglied": pk}` — ohne Adresse, ohne Inhalt; kein Versand
  an inaktive Konten (Austritt, Ausschluss, nie bestätigt).
"""

from __future__ import annotations

import logging
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _

from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Mitglied, Mitgliedsstatus
from plattform_core.eligibility import ANWARTSCHAFT_MONATE, Gegenstand, monate_addieren
from verfahren.models import AuditEintrag

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
            "Stimmberechtigt sind Sie ohne Wartefrist — für den Aufbau gilt die Übergangsregel des "
            "§ 4 Abs 4 lit d; die Anwartschaftsfristen entfallen, bis die Mitgliederversammlung die "
            "erste Verfahrensordnung beschlossen hat."
        )
    beitritt = mitglied.beitritt or heute
    return _(
        "Stimmberechtigt sind Sie nach der Anwartschaft des § 4 Abs 4: bei Sachfragen %(sachfragen)s, "
        "bei Personenwahlen, Satzungsänderungen und der Auflösung %(personenwahlen)s."
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


def _senden(mitglied: Mitglied, art: str, betreff: str, text: str) -> bool:
    try:
        send_mail(betreff, text, settings.DEFAULT_FROM_EMAIL, [mitglied.email])
    except OSError:
        log.exception("Brief „%s“ an Mitglied %s nicht versendbar.", art, mitglied.pk)
        return False
    AuditEintrag.anhaengen({"typ": "post", "art": art, "mitglied": mitglied.pk})
    return True


def _stempeln(mitglied: Mitglied, stempel: str) -> None:
    setattr(mitglied, stempel, timezone.now())
    mitglied.save(update_fields=[stempel])


def _brief(vorlage: str, kontext: dict) -> str:
    basis = settings.DDOE_BASIS_URL.rstrip("/")
    return render_to_string(vorlage, {**kontext, "basis": basis, "schluss": SCHLUSS}).strip() + "\n"


def willkommen_senden(mitglied: Mitglied) -> bool:
    """Nach der E-Mail-Bestätigung: was ab sofort gilt, ab wann das Stimmrecht besteht, dass es
    eine geprüfte Identität braucht (Beitrag, persönliche Referenz), drei Einstiege. Einmal je Konto."""
    if not _zustellbar(mitglied, "willkommen_post_am"):
        return False
    _stempeln(mitglied, "willkommen_post_am")
    with translation.override("de"):
        text = _brief(
            "mitglieder/post/willkommen.txt",
            {
                "name": _anrede(mitglied),
                "anzeigename": mitglied.anzeigename,
                "stimmrecht": stimmrechts_satz(mitglied),
                "referenz": beitragsreferenz(mitglied),
            },
        )
        betreff = _("Willkommen — ParlamentPlattform")
    return _senden(mitglied, "willkommen", betreff, text)


def freischaltung_senden(mitglied: Mitglied) -> bool:
    """Beim ersten Wechsel von „ungeprüft“ auf eine geprüfte Stufe — gleich ob durch den
    Bankabgleich oder die Verwaltung: Prüfung abgeschlossen, Stufe, Stimmrecht ab wann. Einmal je Konto."""
    if not _zustellbar(mitglied, "freischaltung_post_am"):
        return False
    _stempeln(mitglied, "freischaltung_post_am")
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
            },
        )
        betreff = _("Ihre Prüfung ist abgeschlossen — ParlamentPlattform")
    return _senden(mitglied, "freischaltung", betreff, text)
