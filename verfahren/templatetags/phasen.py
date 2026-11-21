"""Menschliche, übersetzbare Namen für die technischen Phasenwerte (F-33).

Die Datenbank führt Phasen als stabile Slugs (`unterstuetzung`, `abstimmung` …);
angezeigt wird immer die übersetzte Form.
"""

from fractions import Fraction

from django import template
from django.utils import formats
from django.utils.translation import gettext, ngettext
from django.utils.translation import gettext_lazy as _

from plattform_core import tally

register = template.Library()

NAMEN = {
    "unterstuetzung": _("Unterstützung"),
    "beratung": _("Beratung"),
    "abstimmung": _("Abstimmung"),
    "angenommen": _("angenommen"),
    "abgelehnt": _("abgelehnt"),
    "verfallen": _("verfallen"),
    "zurueckgewiesen": _("zurückgewiesen"),
    "zurueckgezogen": _("zurückgezogen"),
    # Stimmwerte (für „Ihre aktuelle Stimme“)
    "ja": _("Ja"),
    "nein": _("Nein"),
    "enthaltung": _("Enthaltung"),
    # Vollzugsstatus des Umsetzungsregisters (F-55)
    "offen": _("offen"),
    "in_umsetzung": _("in Umsetzung"),
    "blockiert": _("blockiert"),
    "umgesetzt": _("umgesetzt"),
    "zurueckgestellt": _("zurückgestellt"),
}


@register.filter
def phase_name(wert: str) -> str:
    return str(NAMEN.get(wert, wert))


@register.filter
def antrag_phase(antrag) -> str:
    """Der Phasenname eines Antrags für Badge und Listen (GP-049): Endete ein leerer örtlicher Kreis in
    „abgelehnt“, heißt der Ausgang „kein Beschluss“ (`Antrag.ergebnis_name`). Die Phase bleibt; gefragt
    wird nur bei „abgelehnt“, und das Ergebniswort stellt keine Abfrage."""
    phase = getattr(antrag, "phase", "")
    if phase == "abgelehnt" and getattr(antrag, "ergebnis", None) == "kein_beschluss":
        return str(antrag.ergebnis_name)
    return phase_name(phase)


# Ampelfarben des Umsetzungsregisters (F-55) als Token-Klassen aus base.html —
# dieselben Farben wie die Meldungen, in hell und dunkel (FB-P3).
KLASSEN = {
    "umgesetzt": "badge-ok",
    "in_umsetzung": "badge-info",
    "blockiert": "badge-warn",
    "zurueckgestellt": "badge-hinweis",
    "offen": "badge-still",
}


def anteil_text(mindestbeteiligung: float) -> str:
    """Die Mindestbeteiligung als Prozentzahl ohne Zeichen („5“, „12,5“) — derselbe Bruch wie in
    `tally._mindestbeteiligung_text`, mit dem Dezimalzeichen der Sprache."""
    prozent = Fraction(mindestbeteiligung).limit_denominator(10_000) * 100
    if prozent.denominator == 1:
        return str(prozent.numerator)
    return f"{float(prozent):.2f}".rstrip("0").rstrip(".").replace(".", formats.get_format("DECIMAL_SEPARATOR"))


def _mindest_text(stimmberechtigte: int, mindestbeteiligung: float) -> str:
    """„5 Stimmen (5 %)“ wie in `tally._mindestbeteiligung_text`, mit dem Dezimalzeichen der Sprache."""
    kopfzahl = tally.mindeststimmen(stimmberechtigte, mindestbeteiligung)
    return ngettext("%(n)s Stimme (%(anteil)s %%)", "%(n)s Stimmen (%(anteil)s %%)", kopfzahl) % {
        "n": kopfzahl, "anteil": anteil_text(mindestbeteiligung),
    }


def _sach_satz(a) -> str:
    if a.fall == tally.FALL_LEERER_KREIS:
        return gettext("Keine Stimmberechtigten im festgehaltenen örtlichen Kreis — kein Beschluss.")
    zahlen = {
        "ja": a.ja, "nein": a.nein, "enthaltung": a.enthaltung, "abgegeben": a.abgegeben,
        "berechtigte": a.stimmberechtigte,
    }
    if a.fall == tally.FALL_BETEILIGUNG_VERFEHLT:
        return gettext(
            "Abgelehnt: Mindestbeteiligung verfehlt — %(abgegeben)s/%(berechtigte)s Stimmberechtigten, "
            "erforderlich %(mindest)s (§ 5 Abs 4)."
        ) % {**zahlen, "mindest": _mindest_text(a.stimmberechtigte, a.mindestbeteiligung)}
    if a.mehrheitsbasis == "ja_nein":
        zahlen["mehrheit"] = gettext("Ja %(ja)s : Nein %(nein)s") % zahlen
    else:
        zahlen["mehrheit"] = gettext("Ja %(ja)s von %(abgegeben)s abgegebenen") % zahlen
    if a.fall == tally.FALL_ANGENOMMEN:
        return gettext(
            "Angenommen: %(mehrheit)s, Enthaltungen %(enthaltung)s; Beteiligung %(abgegeben)s/%(berechtigte)s "
            "(§ 5 Abs 4)."
        ) % zahlen
    return gettext(
        "Abgelehnt: keine Mehrheit — %(mehrheit)s, Enthaltungen %(enthaltung)s; Beteiligung "
        "%(abgegeben)s/%(berechtigte)s."
    ) % zahlen


def _wahl_satz(w) -> str:
    if w.fall == tally.FALL_KEINE_BEWERBUNG:
        return gettext("Keine wählbare Bewerbung — die Kandidatur bleibt ohne Ergebnis (§ 7 Abs 1).")
    if w.fall == tally.FALL_LEERER_KREIS:
        return gettext("Keine Stimmberechtigten im festgehaltenen örtlichen Kreis — niemand gewählt.")
    if w.fall == tally.FALL_KEINE_ZUSTIMMUNG:
        return gettext("Keine Bewerbung erhielt eine Zustimmung — niemand gilt als gewählt.")
    zahlen = {
        "beteiligung": w.beteiligung, "berechtigte": w.stimmberechtigte,
        "mindest": _mindest_text(w.stimmberechtigte, w.mindestbeteiligung),
    }
    if w.fall == tally.FALL_GEWAEHLT:
        stimmen = next(p.stimmen for p in w.plaetze if p.bewerbung_id == w.gewonnen_id)
        return gettext(
            "Gewählt ist Bewerbung %(bewerbung)s mit %(stimmen)s Zustimmungen; Beteiligung "
            "%(beteiligung)s/%(berechtigte)s erreicht die Mindestbeteiligung von %(mindest)s (§ 5 Abs 4, § 7 Abs 1)."
        ) % {**zahlen, "bewerbung": w.gewonnen_id, "stimmen": stimmen}
    return gettext(
        "Mindestbeteiligung verfehlt: %(beteiligung)s/%(berechtigte)s, erforderlich %(mindest)s (§ 5 Abs 4) "
        "— keine Bewerbung gilt als gewählt."
    ) % zahlen


@register.filter
def ergebnis_satz(auszaehlung) -> str:
    """Die Begründung einer Auszählung in der Sprache der Seite (GP-139): gebaut aus den Zahlen und dem Fall
    (`tally.FALL_*`) mit übersetzbaren Mustern. Auf Deutsch ist es Zeichen für Zeichen der Satz des Kerns, der
    als Urtext in Audit und Export steht. Ohne Fall bleibt der Satz, wie er ist."""
    fall = getattr(auszaehlung, "fall", None)
    if fall is None:
        return getattr(auszaehlung, "begruendung", "")
    if hasattr(auszaehlung, "plaetze"):
        return _wahl_satz(auszaehlung)
    return _sach_satz(auszaehlung)


@register.filter
def vollzug_klasse(wert: str) -> str:
    return KLASSEN.get(wert, "badge-still")


RING_UMFANG = 50.3  # 2·π·8 — der Kreis mit r = 8 im 20-px-Fristring (FB-D2)


@register.filter
def rest_ring(prozent) -> str:
    """stroke-dashoffset für den Fristring: 0 % verstrichen = voller Versatz, 100 % = 0."""
    try:
        anteil = min(100, max(0, float(prozent))) / 100
    except (TypeError, ValueError):
        anteil = 0
    return f"{RING_UMFANG * (1 - anteil):.1f}"
