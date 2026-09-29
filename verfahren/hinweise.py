"""Rückmeldung in den Feldern des Parlaments (Befunde B1/B2, 28.9.2026).

Eine Handlung aus Kachel oder Feed-Zeile (Unterstützen, Abstimmen, Filter) kehrt nie auf die
Antragsseite zurück und setzt keine Flash-Meldung: Die View antwortet — bei Erfolg wie bei jedem
Fehler — mit einem Redirect auf `weiter`, ergänzt um `?hinweis=<code>&feld=<kennung>`; das
Parlament rendert den Hinweis im Kopf des genannten Felds. htmx tauscht das Feld samt Hinweis,
ohne JavaScript ist es derselbe Weg mit Seitenwechsel (Grundregel 3).

Dasselbe Wörterbuch trägt die Kurzform für die Kachel: Wer nicht handeln darf, sieht statt der
Knöpfe den Zustand mit Link — kein Erklärsatz (Grundregel 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus

#: Die Felder des Parlaments, die Kacheln oder Feed-Zeilen zeigen — nur diese nimmt `feld` an.
FELDER = ("filter", "wichtig", "region")

#: Hinweiscodes: `text` steht im Feldkopf, `kurz` (wenn vorhanden) in der Kachel statt der Knöpfe,
#: `link` ist ein URL-Name (mit `link_text`), `art` färbt den Hinweis (ok / fehler).
HINWEISE: dict[str, dict] = {
    "erfasst": {"text": _("Unterstützung erfasst."), "art": "ok"},
    "zurueckgezogen": {"text": _("Unterstützung zurückgezogen."), "art": "ok"},
    "stimme": {"text": _("Stimme erfasst — änderbar bis zum Fristende."), "art": "ok"},
    "stimme_fehler": {"text": _("Stimme nicht erfasst — läuft die Abstimmung noch?"), "art": "fehler"},
    "phase_vorbei": {"text": _("Die Unterstützungsphase ist beendet."), "art": "fehler"},
    "mandat": {"text": _("Personenwahl: Zustimmung je Bewerbung auf der Antragsseite."), "art": "fehler"},
    "bestaetigung": {
        "text": _("Ein Bestätigungsantrag wird nicht unterstützt (§ 7 Abs 10 lit f Z 3)."),
        "art": "fehler",
    },
    "vf_nur_stimmberechtigte": {
        "text": _("Unterstützen nur mit Stimmrecht für Personenwahlen am Einbringungstag (§ 7 Abs 10 lit c)."),
        "art": "fehler",
    },
    "aussetzung": {"text": _("Abstimmung durch den Integritätsrat ausgesetzt (§ 6 Abs 3 lit d)."), "art": "fehler"},
    "gesperrt_ungeprueft": {
        "kurz": _("Identität noch ungeprüft"),
        "text": _("Identität noch ungeprüft (§ 4 Abs 1)."),
        "link": "mitglieder:beitrag",
        "link_text": _("Beitrag"),
        "art": "fehler",
    },
    "gesperrt_pausiert": {
        "kurz": _("Mitwirkung ruht"),
        "text": _("Mitwirkung ruht — Beitrag ausständig (§ 4 Abs 3)."),
        "link": "mitglieder:beitrag",
        "link_text": _("Beitrag"),
        "art": "fehler",
    },
    "gesperrt_ausgeschlossen": {
        "kurz": _("Mitwirkung ruht"),
        "text": _("Von der Mitwirkung ausgeschlossen (§ 4 Abs 5)."),
        "art": "fehler",
    },
    "testkonto": {"kurz": _("Testkonto"), "text": _("Testkonto — ohne Mitwirkung."), "art": "fehler"},
    "adresswechsel": {
        "kurz": _("Adresswechsel offen"),
        "text": _("Änderung der Anmeldeadresse offen — die Stimmabgabe ruht."),
        "link": "mitglieder:profil",
        "link_text": _("Profil"),
        "art": "fehler",
    },
    "nicht_stimmberechtigt": {
        "kurz": _("Nicht stimmberechtigt am Stichtag"),
        "text": _("Nicht stimmberechtigt am Stichtag (§ 4 Abs 4)."),
        "link": "verfahren:rollen",
        "link_text": _("Wer darf was"),
        "art": "fehler",
    },
    # WeicherFilter (FB-B3)
    "filter_aktiv": {"text": _("Filter gespeichert und aktiv."), "art": "ok"},
    "profil_geloescht": {"text": _("Konfiguration gelöscht."), "art": "ok"},
    "name_fehlt": {"text": _("Bitte einen Namen angeben."), "art": "fehler"},
    "name_vergeben": {"text": _("Eine Konfiguration mit diesem Namen gibt es schon."), "art": "fehler"},
    "profile_voll": {
        "text": _("Höchstens fünf Konfigurationen — zuerst eine löschen oder überschreiben."),
        "art": "fehler",
    },
}


def _link(code: str) -> tuple[str | None, str]:
    eintrag = HINWEISE[code]
    name = eintrag.get("link")
    if not name:
        return None, ""
    try:
        return reverse(name), str(eintrag.get("link_text", ""))
    except NoReverseMatch:
        return None, ""


def hinweis_lage(request) -> dict | None:
    """`?hinweis=<code>&feld=<kennung>` der Adresse als Hinweis für die Vorlage — None, wenn
    Code oder Feld unbekannt sind (fremde oder alte Adressen zeigen nichts)."""
    code = request.GET.get("hinweis", "")
    feld = request.GET.get("feld", "")
    if code not in HINWEISE or feld not in FELDER:
        return None
    link, link_text = _link(code)
    return {
        "feld": feld,
        "code": code,
        "text": HINWEISE[code]["text"],
        "art": HINWEISE[code].get("art", "ok"),
        "link": link,
        "link_text": link_text,
    }


def kachel_sperre(code: str | None) -> dict | None:
    """Die Kurzform eines Sperrgrunds für Kachel und Feed-Zeile: Zustand plus Link, keine Knöpfe."""
    if not code or code not in HINWEISE:
        return None
    link, link_text = _link(code)
    return {"code": code, "kurz": HINWEISE[code].get("kurz") or HINWEISE[code]["text"], "link": link, "link_text": link_text}


def kachel_feld(request) -> str | None:
    """Die Kennung des Ursprungsfelds aus dem Formular — None, wenn die Handlung von der
    Antragsseite kommt (dort bleiben Flash und 403-Seiten richtig)."""
    feld = request.POST.get("feld", "")
    return feld if feld in FELDER else None


def sicherer_pfad(weiter: str) -> bool:
    """Nur ein Pfad dieser Seite: beginnt mit genau einem „/“, enthält kein Steuer- oder
    Leerzeichen und gilt Django als lokal. `urlsplit` entfernt Tab, CR und LF — aus „/\t/x“
    würde sonst ein fremder Host mit leerem Pfad und nach der Handlung ein 500."""
    return (
        weiter.startswith("/")
        and not weiter.startswith("//")
        and not any(zeichen.isspace() or ord(zeichen) < 0x20 or ord(zeichen) == 0x7F for zeichen in weiter)
        and url_has_allowed_host_and_scheme(weiter, allowed_hosts=None)
    )


def weiter_ohne_hinweis(pfad: str) -> str:
    """Denselben Pfad ohne alte `hinweis`/`feld`-Parameter — sonst zeigte ein Feld nach der
    nächsten Handlung noch den vorigen Hinweis."""
    teile = urlsplit(pfad)
    rest = [(k, v) for k, v in parse_qsl(teile.query, keep_blank_values=True) if k not in ("hinweis", "feld")]
    return urlunsplit(("", "", teile.path, urlencode(rest), teile.fragment))


def weiter_mit_hinweis(request, code: str, feld: str):
    """Redirect auf `weiter` (sicher, sonst das Parlament) mit Hinweis und Feld — und dem Anker
    des Felds, damit die Seite ohne JavaScript am Handy beim richtigen Feld steht."""
    assert code in HINWEISE, code
    weiter = request.POST.get("weiter", "")
    if not sicherer_pfad(weiter):
        weiter = reverse("verfahren:parlament")
    teile = urlsplit(weiter_ohne_hinweis(weiter))
    abfrage = parse_qsl(teile.query, keep_blank_values=True) + [("hinweis", code), ("feld", feld)]
    return redirect(urlunsplit(("", "", teile.path, urlencode(abfrage), f"feld-{feld}")))


def mitwirkungssperre(nutzer) -> str | None:
    """Warum ein angemeldetes Mitglied nicht einbringen, unterstützen oder beraten darf —
    dieselben Gründe wie `_mitwirkung_gesperrt` (§ 4, F-51), als Code; None, wenn es darf.
    Ein Testkonto wirkt nie mit: Es steht in keinem Nenner, also auch in keinem Zähler."""
    if nutzer.testkonto:
        return "testkonto"
    if nutzer.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
        return "gesperrt_ungeprueft"
    if nutzer.status == Mitgliedsstatus.PAUSIERT:
        return "gesperrt_pausiert"
    if nutzer.status != Mitgliedsstatus.AKTIV:
        return "gesperrt_ausgeschlossen"
    return None


@dataclass(frozen=True)
class Handlungslage:
    """Einmal je Seite gerechnet (nicht je Kachel): was das Mitglied grundsätzlich darf.
    `mitwirkung` sperrt Unterstützen, `stimmabgabe` zusätzlich bei offenem Adresswechsel (F-51);
    das Stimmrecht am Stichtag rechnet `stimmsperre` je Antrag — ohne Abfrage."""

    angemeldet: bool = False
    mitwirkung: str | None = None
    stimmabgabe: str | None = None

    def stimmsperre(self, nutzer, antrag) -> str | None:
        from verfahren.models import gegenstand_fuer, uebergangsregel_fuer

        if self.stimmabgabe:
            return self.stimmabgabe
        if not nutzer.ist_stimmberechtigt(
            gegenstand_fuer(antrag), antrag.stichtag_der_stimmberechtigung(), uebergang=uebergangsregel_fuer(antrag)
        ):
            return "nicht_stimmberechtigt"
        return None


def handlungslage(nutzer) -> Handlungslage:
    if nutzer is None or not nutzer.is_authenticated:
        return Handlungslage()
    sperre = mitwirkungssperre(nutzer)
    stimme = sperre or ("adresswechsel" if nutzer.adresswechsel_offen else None)
    return Handlungslage(angemeldet=True, mitwirkung=sperre, stimmabgabe=stimme)
