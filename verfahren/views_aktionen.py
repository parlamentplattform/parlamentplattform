"""Handelnde Ansichten: einbringen, unterstützen, kommentieren, abstimmen, exportieren.

Berechtigungsstufen (aus Satzung § 4):
- Lesen: alle, ohne Login (F-20).
- Einbringen, unterstützen, kommentieren: bestätigte Mitglieder
  (Identitätsstufe mindestens „geprüft").
- Abstimmen: stimmberechtigte Mitglieder (Anwartschaft; im Aufbau gilt die
  Übergangsregel nach § 4 Abs 4 lit d — eingestellt über DDOE_UEBERGANGSREGEL, beim Einbringen
  in die Ordnung des Antrags eingefroren).
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext
from django.views.decorators.http import require_POST

from ki.anbieter import anbieter_waehlen
from ki.models import Zweck
from mitglieder.models import Bundesland, Mitglied, Mitgliedsstatus, Wohnsitzart
from mitglieder.post import region_benachrichtigen
from parameter.models import zahl
from plattform_core import Gegenstand, Phase
from plattform_core.schema import offenes_format
from plattform_core.teilnehmerkreis import WIENER_BEZIRKE, GebietsFehler
from verfahren.aehnlichkeit import aehnliche_antraege
from verfahren.einbringwahl import (
    direkt_unterstuetzen,
    einstufung_festhalten,
    einstufungen,
    pruefstand_fuer,
    pruefstand_lesen,
    pruefung_aus_stand,
)
from verfahren.hinweise import (
    HINWEISE,
    kachel_feld,
    mitwirkungssperre,
    sicherer_pfad,
    unerreichbare_schwellen,
    weiter_mit_hinweis,
    weiter_ohne_hinweis,
)
from verfahren.models import (
    Antrag,
    Antragsart,
    AuditEintrag,
    Bewerbung,
    BewerbungsFehler,
    BewerbungsZustimmung,
    Ebene,
    Favorit,
    FilterProfil,
    Kategorie,
    KategorieAbo,
    Kommentar,
    Rueckgabezusage,
    StimmabgabeFehler,
    StimmRegister,
    Unterstuetzung,
    Verfahrensordnung,
    VollzugAusgesetzt,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
    gegenstand_fuer,
    kandidatursperre,
    kategorien_zuordnen,
    stimme_abgeben,
    uebergangsregel_fuer,
    vollzug_fortschreiben,
)
from verfahren.teilnahme import (
    eigene_kreise,
    gebietsname,
    hauptgebiet,
    oertlich_begrenzt,
    oertlich_zulaessig,
    ohne_oertliche_zuordnung,
    wien_ohne_bezirk,
    wohnsitz_ohne_verzeichnis,
)

OFFENE_PHASEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]

def nebenwohnsitz_zaehlt() -> bool:
    """Stellgröße `region-nebenwohnsitz-zaehlt` (§ 14 Abs 3): Nur der Wert 1 schaltet ein, alles
    andere wirkt wie 0. Der Nebenwohnsitz ordnet dann ZUSÄTZLICH einer Region zu — für „Meine
    Region“. Für neue örtliche Anträge und ihre Teilnahme zählt nur der Hauptwohnsitz."""
    return zahl("region-nebenwohnsitz-zaehlt", 0) == 1


def _mitwirkung_gesperrt(request):
    """403-Antwort, wenn Mitwirkungsrechte fehlen — sonst None.

    Gründe: Testkonto (steht in keinem Nenner, wirkt nie mit), unbestätigte Identität (§ 4)
    oder ruhender Status (F-51: pausiert bis zum Beitragseingang bzw. ausgeschlossen nach
    § 4 Abs 5). Den Satzungsbezug liefert `HINWEISE` (GP-176). Richtig für Formulare der Antragsseite; Kachel- und Feed-Formulare (mit
    `feld`) gehen den Redirect-Weg mit Hinweis im Feld (`_abbruch`), damit das Feld nie
    verschwindet."""
    code = mitwirkungssperre(request.user)
    if code == "gesperrt_ungeprueft":
        return render(
            request, "verfahren/nur_bestaetigte.html", {"satzung": HINWEISE[code]["satzung"]}, status=403,
        )
    if code:
        return render(
            request,
            "verfahren/mitwirkung_ruht.html",
            {
                "pausiert": request.user.status == Mitgliedsstatus.PAUSIERT,
                "testkonto": code == "testkonto",
                "satzung": HINWEISE[code].get("satzung", ""),
            },
            status=403,
        )
    return None


def _abbruch(request, feld, code, sonst):
    """Die Weiche für jeden Fehl- und Erfolgsfall einer Handlung (Befund B1): Aus Kachel oder
    Feed-Zeile (`feld`) antwortet ein Redirect auf `weiter` mit Hinweis im Ursprungsfeld —
    mit und ohne JavaScript derselbe Weg, nie die Antragsseite, keine Flash-Meldung. Von der
    Antragsseite liefert `sonst()` die bisherige Antwort (Flash und Redirect oder 403-Seite)."""
    if feld:
        return weiter_mit_hinweis(request, code, feld)
    return sonst()


def _oertlich_abweisen(request, antrag, feld=None):
    # Grund und nächster Schritt: ohne örtliche Zuordnung bleibt die Bundesebene, sonst die eigene
    # Region; der Kreis selbst ist bei Einbringung festgehalten (GP-056)
    lage = {
        "antrag": antrag,
        "ohne_oertliche_zuordnung": ohne_oertliche_zuordnung(request.user),
        "wien_ohne_bezirk": bool((antrag.teilnahmegebiet or {}).get("wiener_bezirk")) and wien_ohne_bezirk(request.user),
    }
    return _abbruch(request, feld, "nicht_im_teilnehmerkreis", lambda: render(
        request, "verfahren/oertlich_nicht_berechtigt.html", lage, status=403,
    ))


def _wohnsitzstand(haupt, mitglied) -> str:
    """Kennung des Hauptwohnsitzes samt Wiener Gemeindebezirk, wie das Formular ihn zeigt."""
    stand = f"gemeinde:{haupt.kennziffer}"
    if haupt.bundesland == Bundesland.WIEN and mitglied.wiener_hauptbezirk:
        stand += f"/bezirk:wien:{mitglied.wiener_hauptbezirk}"
    return stand


class AntragsFormular(forms.Form):
    """Titel, Wortlaut, Begründung — und die Ebene, gebunden an den eigenen Wohnsitz:
    Regionale Anträge sind nur in der ansässigen Region möglich (F-43); das Gebiet
    kommt aus dem Mitgliedsprofil, nie aus freier Eingabe. Lebensbereiche wählt
    niemand von Hand — die ordnet die Plattform automatisch zu (F-47)."""

    art = forms.ChoiceField(
        label=gettext_lazy("Art des Antrags"),
        widget=forms.RadioSelect,
        required=False,
        initial=Antragsart.SACHE.value,
        choices=[
            (
                Antragsart.SACHE.value,
                gettext_lazy("Sachantrag — ein Beschluss in der Sache"),
            ),
            (
                Antragsart.MANDAT.value,
                gettext_lazy(
                    "Mandats-Kandidatur — eine Personenwahl (§ 7 Abs 1): Mitglieder bewerben sich "
                    "am Antrag, die meiste Zustimmung gewinnt, die Reihenfolge ergibt die Liste"
                ),
            ),
        ],
    )
    titel = forms.CharField(
        label=gettext_lazy("Titel"),
        max_length=200,
        help_text=gettext_lazy("Bei einer Mandats-Kandidatur: das Mandat, z. B. „Listenreihung Gemeinderat …“."),
    )
    wortlaut = forms.CharField(
        label=gettext_lazy("Wortlaut des Antrags"),
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text=gettext_lazy(
            "Bei einer Mandats-Kandidatur: Beschreibung des Mandats — Aufgabe, Zeitraum, Zuständigkeit."
        ),
    )
    begruendung = forms.CharField(
        label=gettext_lazy("Begründung"), widget=forms.Textarea(attrs={"rows": 6}), required=False
    )
    ebene = forms.ChoiceField(label=gettext_lazy("Gilt für"), widget=forms.RadioSelect, required=False)

    def __init__(self, *args, mitglied=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mitglied = mitglied
        wahlen = [(Ebene.BUND.value, _("Ganz Österreich"))]
        haupt = (
            mitglied.wohnsitz if mitglied is not None and mitglied.wohnsitz_art_aktuell == Wohnsitzart.OESTERREICH
            else None
        )
        self.wien_ohne_bezirk = False
        # Der Wohnsitzstand beim Anzeigen des Formulars; ein Umzug dazwischen führt zur
        # Rückfrage statt still in die neue Gemeinde (GP-170)
        self.gebiet_kennung = ""
        self.wohnsitz_waehlen = mitglied is not None and wohnsitz_ohne_verzeichnis(mitglied)  # GP-055
        self.ohne_region = mitglied is not None and mitglied.wohnsitz_art in (  # GP-169
            Wohnsitzart.OHNE_FESTEN_WOHNSITZ, Wohnsitzart.AUSLAND,
        )
        if haupt is not None:
            self.gebiet_kennung = _wohnsitzstand(haupt, mitglied)
            wahlen.append((Ebene.LAND.value, _("Mein Bundesland (%s)") % haupt.get_bundesland_display()))
            bezirk = haupt.bezirk
            if haupt.bundesland == Bundesland.WIEN:
                bezirk = WIENER_BEZIRKE.get(mitglied.wiener_hauptbezirk, "")
                self.wien_ohne_bezirk = not bezirk
            if bezirk:
                wahlen.append((Ebene.BEZIRK.value, _("Mein Bezirk (%s)") % bezirk))
            wahlen.append((Ebene.GEMEINDE.value, _("Meine Gemeinde (%s)") % haupt.anzeige))
        self.gebietsstand = None
        self.fields["ebene"].choices = wahlen
        self.fields["ebene"].initial = Ebene.BUND.value

    def clean_ebene(self):
        wert = self.cleaned_data.get("ebene") or Ebene.BUND.value
        try:
            self.gebietsstand = hauptgebiet(self.mitglied, wert)
        except GebietsFehler as fehler:
            raise forms.ValidationError(str(fehler)) from fehler
        gesehen = self.data.get("gebiet_kennung", "")
        if wert != Ebene.BUND.value and gesehen and gesehen != self.gebiet_kennung:
            raise forms.ValidationError(_("Das Gebiet hat sich geändert. Bitte prüfen Sie Ihre Auswahl erneut."))
        return wert

    def clean_art(self):
        # Nur die angebotenen Arten: Eine Mandatsfrage (§ 7 Abs 9) eröffnet allein der Mandatar
        # aus seinem Instant-Report — nie ein POST auf /einbringen/. Das ChoiceField weist
        # fremde Werte schon ab; hier bleibt der Rückfall auf den Sachantrag für leere Eingaben.
        wert = self.cleaned_data.get("art") or Antragsart.SACHE.value
        return wert if wert in (Antragsart.SACHE.value, Antragsart.MANDAT.value) else Antragsart.SACHE.value

    def gebiet(self) -> str:
        return gebietsname(self.gebietsstand) if self.gebietsstand else ""

    def vergleichsdaten(self):
        daten = {**self.cleaned_data, "gebiet": self.gebiet()}
        if self.gebietsstand and self.gebietsstand.ebene != Ebene.BUND:
            daten["gebietsschluessel"] = self.gebietsstand.kennung
        return daten


class KommentarFormular(forms.Form):
    text = forms.CharField(
        # Die Höchstzahl prüft der Schreibweg gegen das Register (GP-083)
        label=gettext_lazy("Beitrag zur Beratung"), widget=forms.Textarea(attrs={"rows": 4})
    )


@login_required
def einbringen(request):
    """F-10 + F-35: Einbringen mit Ähnlichkeitshinweis — der Hinweis schlägt vor,
    er blockiert nie. „Trotzdem einbringen" ist immer gleichwertig möglich."""
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if ordnung is None:
        return render(request, "verfahren/keine_ordnung.html", status=503)

    pruefung = None  # das Ergebnis beider Ähnlichkeitsstufen (verfahren/aehnlichkeit.py)
    form = AntragsFormular(request.POST if request.method == "POST" else None, mitglied=request.user)

    def seite(ergebnis=None, token="", bestaetigung=None, vergleich=None):
        from ki.vergleichsanfragen import anbieten

        vergleichsangebot = (anbieten(form.vergleichsdaten(), request.user, token)
                             if token and ergebnis and ergebnis.treffer and not bestaetigung else "")
        return render(request, "verfahren/einbringen.html", {
            "form": form, "aehnliche": ergebnis.treffer if ergebnis else [],
            "oertlich_gesperrte_treffer": _oertlich_gesperrte_treffer(ergebnis, request.user),
            "pruefung": ergebnis, "pruefstand": token, "bestaetigung": bestaetigung,
            "vorschau_geprueft": ergebnis is not None,
            "ordnung": ordnung, "ki_anbieter": _ki_anbieter_name(),
            "gegenueberstellung_token": vergleichsangebot, "gegenueberstellung": vergleich,
            "vorschau_wartezeit": max(0, zahl("aehnlichkeit-vorschau-wartezeit-ms", 800)),
            "mindestzeichen": max(1, zahl("aehnlichkeit-vorschau-mindestzeichen", 40)),
            # Z-5 (E-05): Hinweis vor dem Absenden, wo die Schwelle im Ortskreis nicht erreichbar ist
            "schwelle_hinweise": unerreichbare_schwellen(request.user, ordnung, request.POST.get("art") or "sache"),
        })

    if request.method == "POST":
        if form.is_valid():
            d = form.cleaned_data
            daten = form.vergleichsdaten()
            token = request.POST.get("pruefstand", "")
            stand = pruefstand_lesen(token, daten, request.user) if token else None
            if request.POST.get("textvergleich"):
                from ki.betriebszugang import _sperrkonflikt
                from ki.gegenueberstellungen import anfordern, auswertung

                if stand is None or d["art"] != Antragsart.SACHE:
                    form.add_error(None, _("Der Text oder die Auswahl hat sich geändert. Bitte prüfen Sie die Treffer erneut."))
                    lokal = aehnliche_antraege(d["titel"], d["wortlaut"], request.user, bedeutung=False)
                    return seite(lokal, pruefstand_fuer(daten, request.user, lokal))
                pruefung = pruefung_aus_stand(stand)
                try:
                    vergleich = auswertung(anfordern(daten, request.user, token, request.POST["textvergleich"]), request.user)
                except ValueError:
                    form.add_error(None, _("Der Modellvergleich passt nicht mehr zu diesem Angebot oder die vollständigen Texte überschreiten seine Grenze. Prüfen Sie die Treffer erneut oder bringen Sie Ihren eigenen Antrag ein."))
                    return seite(pruefung, token)
                except OperationalError as fehler:
                    if not _sperrkonflikt(fehler):
                        raise
                    # SQLite kann bereits beim Reservieren der privaten Anfrage
                    # einen Schreibkonflikt melden. Kein zweiter Aufruf/Retry;
                    # die unveränderte menschliche Wahl bleibt gerendert.
                    vergleich = {"gueltig": False, "meldung": "datenbank_belegt"}
                return seite(pruefung, token, vergleich=vergleich)
            wahl = request.POST.get("unterstuetzen") or request.POST.get("unterstuetzen_bestaetigt")
            if wahl or request.POST.get("vergleich_zurueck") or (request.POST.get("trotzdem") and token):
                if stand is None or d["art"] != Antragsart.SACHE:
                    form.add_error(None, _("Der Text oder die Auswahl hat sich geändert. Bitte prüfen Sie die Treffer erneut."))
                    lokal = aehnliche_antraege(d["titel"], d["wortlaut"], request.user, bedeutung=False)
                    return seite(lokal, pruefstand_fuer(daten, request.user, lokal))
                pruefung = pruefung_aus_stand(stand)
                if wahl:
                    treffer = next((t for t in pruefung.treffer if str(t["antrag"].pk) == wahl), None)
                    if treffer is None:
                        form.add_error(None, _("Bitte wählen Sie einen der angezeigten Anträge."))
                        return seite(pruefung, token)
                    if not oertlich_zulaessig(treffer["antrag"], request.user):
                        form.add_error(None, _("Dieser Antrag kann von Ihnen nicht unterstützt werden. Ihr eigener Text bleibt erhalten."))
                        return seite(pruefung, token)
                    if request.POST.get("unterstuetzen_bestaetigt"):
                        ziel = direkt_unterstuetzen(request.user, treffer["antrag"].pk)
                        if ziel is not None:
                            messages.success(request, _("Ihre Unterstützung ist erfasst. Ihr eigener Text wurde nicht eingebracht."))
                            return redirect(reverse("verfahren:antrag", args=[ziel.pk]) + "#zone-einschaetzung")
                        form.add_error(None, _("Dieser Antrag kann von Ihnen nicht unterstützt werden. Ihr eigener Text bleibt erhalten."))
                        return seite(pruefung, token)
                    return seite(pruefung, token, treffer["antrag"])
                if request.POST.get("vergleich_zurueck"):
                    return seite(pruefung, token)
            # Ähnlichkeitshinweis nur für Sachanträge — Kandidaturen für dasselbe
            # Mandat sollen sich am BESTEHENDEN Antrag beteiligen (§ 7 Abs 1);
            # darauf weist die Antragsseite selbst hin.
            if not request.POST.get("trotzdem") and d["art"] == Antragsart.SACHE.value:
                pruefung = aehnliche_antraege(d["titel"], d["wortlaut"], request.user)
                stand = None
                if pruefung.treffer:
                    # § 5 Abs 10 lit d: Übersicht ähnlicher Anträge SAMT Beteiligung —
                    # damit sichtbar ist, wo Unterstützung am meisten bewegt.
                    return seite(pruefung, pruefstand_fuer(daten, request.user, pruefung))
            try:
                with transaction.atomic():
                    antrag = antrag_einbringen(
                        request.user, d["titel"], d["wortlaut"], d["begruendung"], ordnung,
                        ebene=d["ebene"], art=d["art"], neuer_teilnehmerkreis=True,
                        erwartetes_gebiet=form.gebietsstand,
                    )
                    if request.POST.get("trotzdem"):
                        einstufung_festhalten(antrag, stand)
            except GebietsFehler as fehler:
                form.add_error("ebene", str(fehler))
                return seite()
            zugeordnet = kategorien_zuordnen(antrag)  # F-47: die Plattform ordnet zu, nicht der Mensch
            region_benachrichtigen(antrag)  # Post an die betroffene Region — nur mit Einwilligung, im Hintergrundlauf
            if antrag.art == Antragsart.SACHE:
                _zukunftswerkstatt_beauftragen(antrag, request.user, pruefung)
            namen = ", ".join(k.pfad_kurz for k in zugeordnet)
            if antrag.ebene != Ebene.BUND and antrag.gebiet:
                # Die Meldung nennt das Gebiet, in dem der Antrag nun gilt (GP-170)
                if zugeordnet:
                    text = _(
                        "Ihr Antrag für %(gebiet)s ist eingebracht und sammelt jetzt Unterstützung. "
                        "Automatisch zugeordnet: %(namen)s."
                    ) % {"gebiet": antrag.gebiet, "namen": namen}
                else:
                    text = _("Ihr Antrag für %(gebiet)s ist eingebracht und sammelt jetzt Unterstützung.") % {
                        "gebiet": antrag.gebiet
                    }
                messages.success(request, text)
            elif zugeordnet:
                messages.success(
                    request,
                    _(
                        "Ihr Antrag ist eingebracht und sammelt jetzt Unterstützung. Automatisch zugeordnet: %s."
                    )
                    % namen,
                )
            else:
                messages.success(request, _("Ihr Antrag ist eingebracht und sammelt jetzt Unterstützung."))
            # ?neu=1: Die Antragsseite zeigt das Band zur Einschätzung — dort stehen die ersten
            # Informationen der Zukunftswerkstatt (betroffene Gesetze), sobald sie da sind.
            return redirect(reverse("verfahren:antrag", kwargs={"pk": antrag.pk}) + "?neu=1")
    return seite()


def _oertlich_gesperrte_treffer(ergebnis, mitglied):
    if not ergebnis:
        return set()
    antraege = [treffer["antrag"] for treffer in ergebnis.treffer if oertlich_begrenzt(treffer["antrag"])]
    eigene = eigene_kreise(mitglied, antraege)
    return {antrag.pk for antrag in antraege if antrag.pk not in eigene}


@login_required
@require_POST
def einbringen_vorschau(request):
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    form = AntragsFormular(request.POST, mitglied=request.user)
    lage = {
        "vorschau": True, "aehnliche": [],
        "mindestzeichen": max(1, zahl("aehnlichkeit-vorschau-mindestzeichen", 40)),
    }
    if form.is_valid() and form.cleaned_data["art"] == Antragsart.SACHE:
        d = form.cleaned_data
        laenge = len(d["titel"]) + len(d["wortlaut"])
        if lage["mindestzeichen"] <= laenge <= max(1, zahl("aehnlichkeit-vorschau-hoechstzeichen", 20000)):
            pruefung = aehnliche_antraege(d["titel"], d["wortlaut"], request.user, bedeutung=False)
            lage.update(
                aehnliche=pruefung.treffer, pruefung=pruefung,
                oertlich_gesperrte_treffer=_oertlich_gesperrte_treffer(pruefung, request.user),
                vorschau_geprueft=True,
                pruefstand=pruefstand_fuer(form.vergleichsdaten(), request.user, pruefung),
            )
        elif laenge > lage["mindestzeichen"]:
            lage["vorschau_zu_lang"] = True
    return render(request, "verfahren/_aehnliche_antraege.html", lage)


def _ki_anbieter_name() -> str:
    """Der Name des angeschlossenen KI-Anbieters, sonst leer: Nur wenn einer angeschlossen ist, geht
    der Entwurf beim Absenden zum Bedeutungsvergleich hinaus — nur dann sagt die Seite es."""
    return getattr(anbieter_waehlen(), "name", "")


def _zukunftswerkstatt_beauftragen(antrag, mitglied, pruefung) -> None:
    """Nach dem Einbringen eines Sachantrags: die betroffenen Gesetze einreihen (FB-H3, Warteschlange)
    und den Textvektor sichern — direkt, wenn die Prüfung ihn eben gerechnet hat (kein zweiter
    Aufruf), sonst als Auftrag „aehnlichkeit“ für den Hintergrundlauf. Beides ist Vorschlag,
    nichts davon hält den Antrag auf: Jeder Schritt läuft in einem eigenen Savepoint, ein Fehler
    landet im Protokoll statt auf einer Fehlerseite — der Antrag steht ja schon (GP-178)."""
    import logging

    from ki.warteschlange import einreihen_ohne_hemmung, rechtspruefung_ohne_hemmung
    from verfahren.aehnlichkeit import einbettung_speichern

    rechtspruefung_ohne_hemmung(antrag, mitglied)
    if pruefung is not None and pruefung.neuer_vektor is not None:
        try:
            with transaction.atomic():
                einbettung_speichern(antrag, 1, pruefung.bedeutungsmodell, pruefung.neuer_vektor)
        except Exception:
            logging.getLogger(__name__).exception("Textvektor für Antrag %s nicht gespeichert", antrag.pk)
    elif anbieter_waehlen() is not None:
        einreihen_ohne_hemmung(Zweck.AEHNLICHKEIT, antrag, mitglied)


def _mit_flash(request, stufe, text, pk):
    """Der bisherige Weg von der Antragsseite: Flash-Meldung und zurück zum Antrag."""

    def antwort():
        getattr(messages, stufe)(request, text)
        return redirect("verfahren:antrag", pk=pk)

    return antwort


@login_required
@require_POST
@transaction.atomic
def unterstuetzen(request, pk):
    antrag = get_object_or_404(Antrag.objects.select_for_update(), pk=pk)
    feld = kachel_feld(request)  # Kachel/Feed → Rückmeldung im Feld statt Antragsseite oder 403
    code = mitwirkungssperre(request.user)
    if code:
        return _abbruch(request, feld, code, lambda: _mitwirkung_gesperrt(request))
    if not oertlich_zulaessig(antrag, request.user):
        return _oertlich_abweisen(request, antrag, feld)
    antrag.fortschreiben()
    if antrag.phase != Phase.UNTERSTUETZUNG.value:
        return _abbruch(
            request, feld, "phase_vorbei",
            _mit_flash(request, "error", _("Die Unterstützungsphase dieses Antrags ist beendet."), pk),
        )
    if antrag.art == Antragsart.VERTRAUENSFRAGE:
        # § 7 Abs 10 lit c: Abweichend von § 4 Abs 4 lit b kann die Vertrauensfrage nur
        # unterstützen, wer am Tag der Einbringung für Personenwahlen stimmberechtigt war —
        # derselbe Kreis, aus dem die Schwelle gerechnet wurde. Der Bestätigungsantrag (lit f Z 3)
        # kennt keine Unterstützung: Er gilt mit dem Einbringen als unterstützt.
        from verfahren.views import vertrauensfrage_unterstuetzen_erlaubt

        vf = antrag._vertrauensfrage()
        if vf is not None and vf.art == "bestaetigung":
            return _abbruch(
                request, feld, "bestaetigung",
                _mit_flash(
                    request, "error",
                    _("Ein Bestätigungsantrag wird nicht unterstützt — die Abstimmung beginnt am siebten Tag nach Einbringung (§ 7 Abs 10 lit f Z 3)."),
                    pk,
                ),
            )
        if not vertrauensfrage_unterstuetzen_erlaubt(request.user, antrag):
            return _abbruch(
                request, feld, "vf_nur_stimmberechtigte",
                lambda: render(
                    request,
                    "verfahren/vertrauensfrage_nur_stimmberechtigte.html",
                    {"antrag": antrag, "stichtag": timezone.localdate(antrag.eingebracht_am)},
                    status=403,
                ),
            )
    # Grundregel 7: Eine zurückgezogene Unterstützung wird gestempelt, nicht gelöscht — und
    # jede Richtung steht im Audit-Log (ohne Mitgliedsbezug), damit die Zahl der Unterstützer
    # zu jedem Zeitpunkt nachvollziehbar bleibt (§ 5 Abs 3 lit b).
    eintrag, neu = antrag.unterstuetzungen.get_or_create(mitglied=request.user)
    if neu or eintrag.zurueckgezogen_am is not None:
        if not neu:
            eintrag.zurueckgezogen_am = None
            eintrag.erklaert_am = timezone.now()
            eintrag.save(update_fields=["zurueckgezogen_am", "erklaert_am"])
        AuditEintrag.anhaengen({"typ": "unterstuetzung", "antrag": antrag.pk})
        antrag.fortschreiben()  # Schwelle eventuell gerade erreicht
        return _abbruch(
            request, feld, "erfasst", _mit_flash(request, "success", _("Danke — Ihre Unterstützung ist erfasst."), pk)
        )
    eintrag.zurueckgezogen_am = timezone.now()
    eintrag.save(update_fields=["zurueckgezogen_am"])
    AuditEintrag.anhaengen({"typ": "unterstuetzung_zurueckgezogen", "antrag": antrag.pk})
    return _abbruch(
        request, feld, "zurueckgezogen", _mit_flash(request, "info", _("Ihre Unterstützung wurde zurückgezogen."), pk)
    )


def _chat_antwort(request, antrag, anker: str = "", fehler=None, entwurf=None, erfolg=None):
    """Nach jeder Chat-Handlung: mit htmx nur die Zone tauschen, sonst zurück auf den Anker.

    Ein Fehler (Befund B2) geht nie über Django-messages: Die Zone trägt `chat.fehler` (Text,
    optional Link) und `chat.entwurf` (text, ist_kritik, bezug_absatz, antwort_auf), das Formular
    zeigt den eingegebenen Text mit der Meldung darüber. Ohne JavaScript steht dafür die ganze
    Antragsseite mit Fehler und Entwurf — kein Redirect, der den Text verlöre. Eine Bestätigung
    (`erfolg`) steht mit htmx ebenso in der Zone, ohne JavaScript als Meldung auf der Antragsseite,
    auf die der Redirect führt — nie auf einer fremden, späteren Seite (GP-071)."""
    from verfahren.views import _antwort_vorgabe, _chat_lage, antrag_detail

    if request.headers.get("HX-Request"):
        lage = _chat_lage(antrag, request.user)
        lage["fehler"] = fehler
        lage["erfolg"] = erfolg
        lage["entwurf"] = entwurf
        lage["antwort_vorgabe"] = _antwort_vorgabe(antrag, (entwurf or {}).get("antwort_auf"))
        return render(request, "verfahren/_chat.html", {"antrag": antrag, "chat": lage})
    if fehler:
        return antrag_detail(request, antrag.pk, chat_fehler=fehler, chat_entwurf=entwurf)
    if erfolg:
        messages.success(request, erfolg)
    ziel = reverse("verfahren:antrag", kwargs={"pk": antrag.pk})
    return redirect(f"{ziel}#{anker}" if anker else ziel)


def _chat_fehler(text, link: str | None = None, link_text: str = "") -> dict:
    return {"text": text, "link": link, "link_text": link_text}


@login_required
@require_POST
def kommentieren(request, pk):
    """Einen Beitrag in den Chat schreiben (FB-G1) — als eigener Faden oder als Antwort."""
    from verfahren.chat import BeitragZuLang, ChatGesperrt, beitrag_schreiben, kritik_mindestzeichen
    from verfahren.hinweise import HINWEISE, kachel_sperre
    from verfahren.views import ganze_zahl

    antrag = get_object_or_404(Antrag, pk=pk)
    # Der Entwurf begleitet jeden Fehler zurück ins Formular — nichts Eingegebenes geht verloren
    entwurf = {
        "text": request.POST.get("text") or "",
        "ist_kritik": request.POST.get("ist_kritik") == "1",
        "bezug_absatz": request.POST.get("bezug_absatz") or "",
        "antwort_auf": request.POST.get("antwort_auf") or "",
    }
    code = mitwirkungssperre(request.user)
    if code:
        if not request.headers.get("HX-Request"):
            return _mitwirkung_gesperrt(request)
        sperre = kachel_sperre(code)
        return _chat_antwort(
            request, antrag,
            fehler=_chat_fehler(HINWEISE[code]["text"], sperre["link"], sperre["link_text"]), entwurf=entwurf,
        )
    antrag.fortschreiben()
    antwort_auf = None
    roh = entwurf["antwort_auf"]
    if roh:
        antwort_auf = Kommentar.objects.filter(
            pk=roh, antrag=antrag, archiviert_am__isnull=True
        ).first() if ganze_zahl(roh) is not None else None  # GP-109
        if antwort_auf is None:
            entwurf["antwort_auf"] = ""
            return _chat_antwort(
                request, antrag,
                fehler=_chat_fehler(_("Der Beitrag, auf den Sie antworten wollten, ist nicht mehr im laufenden Chat.")),
                entwurf=entwurf,
            )
    form = KommentarFormular(request.POST)
    if not form.is_valid():
        return _chat_antwort(request, antrag, fehler=_chat_fehler(_("Bitte einen Text eingeben.")), entwurf=entwurf)
    absatz = entwurf["bezug_absatz"]
    try:
        beitrag = beitrag_schreiben(
            antrag, request.user, form.cleaned_data["text"], antwort_auf,
            ist_kritik=entwurf["ist_kritik"], bezug_absatz=ganze_zahl(absatz),
        )
    except ChatGesperrt as fehler:
        return _chat_antwort(request, antrag, fehler=_chat_fehler(str(fehler)), entwurf=entwurf)
    except BeitragZuLang as fehler:
        return _chat_antwort(
            request, antrag, fehler=_chat_fehler(_zu_lang_text(fehler.hoechst)), entwurf=entwurf,
        )
    except ValueError:
        return _chat_antwort(
            request, antrag,
            fehler=_chat_fehler(_kritik_zu_kurz_text(kritik_mindestzeichen())),
            entwurf=entwurf,
        )
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


def _zu_lang_text(hoechst: int) -> str:
    return _("Ein Beitrag darf höchstens %(n)s Zeichen lang sein — bitte kürzen.") % {"n": hoechst}


def _kritik_zu_kurz_text(mindestens: int) -> str:
    return _(
        "Kritik am Vorschlag braucht einen Absatzbezug und mindestens %(n)s Zeichen — "
        "so kann der Expertenrat damit arbeiten."
    ) % {"n": mindestens}


def _eigener_beitrag(request, pk, beitrag_pk):
    """Beitrag samt Antrag holen und prüfen, dass er dem Mitglied gehört und änderbar ist."""
    antrag = get_object_or_404(Antrag, pk=pk)
    beitrag = get_object_or_404(Kommentar, pk=beitrag_pk, antrag=antrag)
    return antrag, beitrag


@login_required
@require_POST
def beitrag_bearbeiten(request, pk, beitrag_pk):
    """Den eigenen Beitrag ändern — nur binnen des Bearbeitungsfensters aus dem Register, danach steht er (FB-G1)."""
    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    if not beitrag.darf_bearbeiten(request.user):
        minuten = Kommentar.bearbeitungsfenster_minuten()  # die geltende Zahl, nicht fest „fünf“
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}", fehler=_chat_fehler(ngettext(
            "Ändern ist nur in der ersten Minute möglich.",
            "Ändern ist nur in den ersten %(n)s Minuten möglich.",
            minuten,
        ) % {"n": minuten}))
    text = (request.POST.get("text") or "").strip()
    if not text:
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}", fehler=_chat_fehler(_("Bitte einen Text eingeben.")))
    from verfahren.chat import chat_zeichen_hoechstzahl

    hoechst = chat_zeichen_hoechstzahl()
    if len(text) > hoechst:
        # Abweisen statt still kürzen (GP-083)
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}", fehler=_chat_fehler(_zu_lang_text(hoechst)))
    if beitrag.ist_kritik:
        # Beim Ändern gilt dieselbe Mindestlänge wie beim Schreiben (GP-015, § 5 Abs 13)
        from verfahren.chat import kritik_mindestzeichen

        if len(text) < kritik_mindestzeichen():
            return _chat_antwort(
                request, antrag, f"k-{beitrag.pk}", fehler=_chat_fehler(_kritik_zu_kurz_text(kritik_mindestzeichen()))
            )
    beitrag.text = text
    beitrag.bearbeitet_am = timezone.now()
    with transaction.atomic():
        beitrag.save(update_fields=["text", "bearbeitet_am"])
        _abstimmungschat_auditieren(beitrag, "beitrag_geaendert")
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


def _abstimmungschat_auditieren(beitrag, typ: str) -> None:
    """Im Abstimmungs-Chat zählen Beiträge für die Entscheidung der Unterstützer (§ 5 Abs 13):
    Ändern und Zurückziehen stehen deshalb im Audit — ohne Text und ohne Person (GP-015)."""
    if (beitrag.phase or "").startswith("vorschlag-"):
        AuditEintrag.anhaengen({"typ": typ, "antrag": beitrag.antrag_id, "beitrag": beitrag.pk})


@login_required
@require_POST
def beitrag_entfernen(request, pk, beitrag_pk):
    """Den eigenen Beitrag zurückziehen (FB-G1): Der Text weicht einem Vermerk, der Faden bleibt.
    Gelöscht wird nichts — Antworten darunter verlören sonst ihren Bezug (Grundregel 7)."""
    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    if beitrag.mitglied_id != request.user.pk or beitrag.archiviert_am:
        return _chat_antwort(
            request, antrag, f"k-{beitrag.pk}",
            fehler=_chat_fehler(_("Nur eigene Beiträge im laufenden Chat lassen sich zurückziehen.")),
        )
    if not beitrag.geloescht:
        beitrag.geloescht = True
        with transaction.atomic():
            beitrag.save(update_fields=["geloescht"])
            _abstimmungschat_auditieren(beitrag, "beitrag_zurueckgezogen")
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


@login_required
@require_POST
def reagieren(request, pk, beitrag_pk):
    """Zustimmen, ablehnen oder die eigene Reaktion zurücknehmen (FB-G1, FB-G6).

    Außerhalb des Abstimmungs-Chats ist nur Zustimmung möglich und rein informativ: Die Reihung
    bleibt chronologisch (D-G1, Grundregel 6). Im Abstimmungs-Chat des Expertenrats-Vorschlags
    ist die Reaktion das Votum der Unterstützer — dort reagieren nur sie (§ 5 Abs 12)."""
    from django.db import IntegrityError

    from verfahren.chat import (
        ReaktionGeschlossen,
        abstimmungschat,
        chat_offen,
        darf_reagieren,
        reaktion_umschalten,
    )
    from verfahren.models import Reaktionsart

    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    code = mitwirkungssperre(request.user)
    if code and request.headers.get("HX-Request"):
        # Kein stummer Klick: Der Grund steht in der Zone, wie beim Schreiben (GP-071)
        from verfahren.hinweise import HINWEISE, kachel_sperre

        sperre = kachel_sperre(code)
        return _chat_antwort(
            request, antrag, f"k-{beitrag.pk}",
            fehler=_chat_fehler(HINWEISE[code]["text"], sperre["link"], sperre["link_text"]),
        )
    if code:
        return _mitwirkung_gesperrt(request)
    # § 5 Abs 13: Reagieren geht „bis zum Fristende“. Erst fortschreiben — ist die Frist um, wertet das
    # die Runde aus und räumt ihre Beiträge ins Archiv; die Reaktion trifft dann ins Leere statt in
    # eine schon entschiedene Rechnung (Bestandsaufnahme A8). Hat das die Phase gewechselt, zeichnet
    # htmx die ganze Seite neu — Abstimmen-Karte und Block „So kam der Vorschlag zustande“ (Prüfung 0.51.0).
    gewechselt = antrag.fortschreiben()
    beitrag.refresh_from_db()
    geschlossen = _chat_fehler(_("Auf diesen Beitrag lässt sich nicht mehr reagieren."))
    fehler = None
    if beitrag.archiviert_am or beitrag.geloescht or not chat_offen(antrag):
        fehler = geschlossen
    elif not darf_reagieren(antrag, request.user):
        fehler = _chat_fehler(_("Reagieren können die Unterstützer dieses Antrags."))
    else:
        art = Reaktionsart.ZUSTIMMUNG
        if request.POST.get("art") == Reaktionsart.ABLEHNUNG and abstimmungschat(antrag) is not None:
            art = Reaktionsart.ABLEHNUNG
        try:
            reaktion_umschalten(beitrag, request.user, art)
        except ReaktionGeschlossen:
            fehler = geschlossen
        except IntegrityError:
            # Die Audit-Kette war gerade überholt (AuditEintrag.anhaengen gibt nach drei Versuchen auf):
            # nichts ist gespeichert — das Mitglied soll es wissen, statt dass der Klick verschwindet.
            fehler = _chat_fehler(_("Die Reaktion ließ sich gerade nicht speichern. Bitte noch einmal."))
    antwort = _chat_antwort(request, antrag, f"k-{beitrag.pk}", fehler=fehler)
    if gewechselt and request.headers.get("HX-Request"):
        antwort["HX-Refresh"] = "true"
    return antwort


@login_required
@require_POST
def melden(request, pk, beitrag_pk):
    """Einen Beitrag melden (Art 16 DSA, § 5 Abs 2, FB-G1). Die Meldung geht an die Verwaltung
    und bleibt nachlesbar; entschieden wird dort mit öffentlichem Grund."""
    from verfahren.models import AuditEintrag, Meldung

    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    grund = request.POST.get("grund", "")
    if grund not in Meldung.Grund.values:
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}", fehler=_chat_fehler(_("Bitte einen Grund wählen.")))
    with transaction.atomic():  # GP-129: Meldung und Eintrag gemeinsam oder gar nicht
        meldung, neu = Meldung.objects.get_or_create(
            kommentar=beitrag,
            mitglied=request.user,
            defaults={"grund": grund, "erlaeuterung": (request.POST.get("erlaeuterung") or "").strip()[:500]},
        )
        if neu:
            AuditEintrag.anhaengen(
                {"typ": "beitrag_gemeldet", "antrag": antrag.pk, "beitrag": beitrag.pk, "grund": grund}
            )
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}", erfolg=_("Danke — die Meldung liegt der Verwaltung vor."))


@login_required
@require_POST
def meldung_entscheiden(request, beitrag_pk):
    """Die Verwaltung entscheidet über die offenen Meldungen eines Beitrags (FB-G1, GP-014):
    ausblenden mit öffentlichem Grund oder keine Maßnahme. Der Text bleibt gespeichert
    (Grundregel 7), die Meldungen tragen Zeitpunkt und Entscheidung, das Audit den Vorgang."""
    from verfahren.models import Meldung

    if not request.user.hat_adminrechte:
        return render(request, "mitglieder/verwaltung_kein_zugang.html", status=403)
    entscheidung = request.POST.get("entscheidung", "")
    grund = (request.POST.get("grund") or "").strip()[:200]
    if entscheidung not in ("ausblenden", "keine_massnahme"):
        messages.error(request, _("Bitte eine Entscheidung wählen."))
        return redirect("verfahren:meldungen")
    if entscheidung == "ausblenden" and not grund:
        messages.error(request, _("Ausblenden braucht einen öffentlichen Grund."))
        return redirect("verfahren:meldungen")
    with transaction.atomic():
        beitrag = get_object_or_404(Kommentar.objects.select_for_update(), pk=beitrag_pk)
        offene = Meldung.objects.filter(kommentar=beitrag, erledigt_am__isnull=True)
        anzahl = offene.count()
        if not anzahl:
            messages.info(request, _("Über die Meldungen zu diesem Beitrag ist schon entschieden."))
            return redirect("verfahren:meldungen")
        jetzt = timezone.now()
        ereignis = {"beitrag": beitrag.pk, "meldungen": anzahl}
        ereignis.update({"sitzung": beitrag.sitzung_id} if beitrag.sitzung_id else {"antrag": beitrag.antrag_id})
        if entscheidung == "ausblenden":
            if beitrag.ausgeblendet_am is None:
                beitrag.ausgeblendet_am = jetzt
                beitrag.ausgeblendet_grund = grund
                beitrag.save(update_fields=["ausgeblendet_am", "ausgeblendet_grund"])
            offene.update(erledigt_am=jetzt, entscheidung="ausgeblendet")
            AuditEintrag.anhaengen({"typ": "beitrag_ausgeblendet", **ereignis})
            messages.success(request, _("Der Beitrag ist ausgeblendet; der Grund steht öffentlich an seiner Stelle."))
        else:
            offene.update(erledigt_am=jetzt, entscheidung="keine_massnahme")
            AuditEintrag.anhaengen({"typ": "meldung_ohne_massnahme", **ereignis})
            messages.success(request, _("Entschieden: keine Maßnahme. Der Beitrag bleibt stehen."))
    return redirect("verfahren:meldungen")


@login_required
@require_POST
def chat_gelesen(request, pk):
    """Den Lesestand vorrücken (FB-G2) — schickt die Zone, damit die „neu"-Linie verschwindet."""
    from verfahren.chat import gelesen_merken

    antrag = get_object_or_404(Antrag, pk=pk)
    gelesen_merken(antrag, request.user)
    return _chat_antwort(request, antrag)


@login_required
@require_POST
def abstimmen(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    feld = kachel_feld(request)  # Kachel/Feed → Rückmeldung im Feld statt Antragsseite oder 403
    if not oertlich_zulaessig(antrag, request.user):
        return _oertlich_abweisen(request, antrag, feld)
    antrag.fortschreiben()
    if antrag.art == Antragsart.MANDAT:
        return _abbruch(
            request, feld, "mandat",
            _mit_flash(request, "error", _("Bei einer Mandats-Kandidatur stimmen Sie den einzelnen Bewerbungen zu."), pk),
        )
    stichtag = antrag.stichtag_der_stimmberechtigung()
    # § 4 Abs 4: derselbe Gegenstand wie beim Zählen der Stimmberechtigten (`fortschreiben`) —
    # die Vertrauensfrage ist eine Personenwahl (§ 7 Abs 10 lit a und e), alles andere Sachfrage.
    if not request.user.ist_stimmberechtigt(
        gegenstand_fuer(antrag), stichtag, uebergang=uebergangsregel_fuer(antrag)
    ):
        # Ungeprüfte und ruhende Konten sind nie stimmberechtigt — der Kachel-Hinweis nennt den Grund
        # — und die Antragsseite dieselbe Sperrseite wie beim Unterstützen; die Seite zur Anwartschaft
        # nur, wenn wirklich die Anwartschaft fehlt (GP-070)
        code = mitwirkungssperre(request.user) or "nicht_stimmberechtigt"
        return _abbruch(
            request, feld, code,
            lambda: _mitwirkung_gesperrt(request)
            or render(request, "verfahren/nicht_stimmberechtigt.html", status=403),
        )
    if request.user.adresswechsel_offen:
        # F-51: Solange die Anmeldeadresse in Änderung ist, gehört das Konto vielleicht nicht
        # mehr dem Menschen, der hier stimmen will — die Stimmabgabe ruht bis zur Entscheidung.
        return _abbruch(
            request, feld, "adresswechsel",
            _mit_flash(
                request, "error",
                _("Für Ihr Konto läuft eine Änderung der Anmeldeadresse — bis sie entschieden ist, ruht die Stimmabgabe."),
                pk,
            ),
        )
    if antrag.aussetzung_laeuft():
        # § 6 Abs 3 lit d: Die Aussetzung ist veröffentlicht; wer trotzdem stimmt, erfährt warum.
        return _abbruch(
            request, feld, "aussetzung",
            _mit_flash(
                request, "error",
                _("Die Abstimmung ist durch den Integritätsrat ausgesetzt (§ 6 Abs 3 lit d) — solange sie ruht, werden keine Stimmen angenommen; die Frist läuft danach weiter."),
                pk,
            ),
        )
    wahl = request.POST.get("stimme", "")
    try:
        stimme_abgeben(antrag, request.user, wahl)
        code, stufe, text = "stimme", "success", _("Ihre Stimme ist erfasst — bis zum Fristende können Sie sie ändern.")
    except (StimmabgabeFehler, ValueError):
        code, stufe, text = "stimme_fehler", "error", _("Diese Stimme konnte nicht erfasst werden (läuft die Abstimmung noch?).")
    if feld:
        return weiter_mit_hinweis(request, code, feld)
    getattr(messages, stufe)(request, text)
    # P4: Direktabstimmung aus der Regions-Kachel kehrt aufs Parlament zurück.
    weiter = request.POST.get("weiter", "")
    if sicherer_pfad(weiter):
        return redirect(weiter)
    return redirect("verfahren:antrag", pk=pk)


def _zurueck_zum_parlament(request, code: str | None = None, stufe: str = "info", text: str = ""):
    """Zurück ins Parlament. Aus dem Feld (`feld`, alle WeicherFilter-Formulare) steht die
    Rückmeldung als Hinweis im Feldkopf; ohne `feld` bleibt die Flash-Meldung."""
    feld = kachel_feld(request)
    if feld and code:
        return weiter_mit_hinweis(request, code, feld)
    if code and text:
        getattr(messages, stufe)(request, text)
    weiter = request.POST.get("weiter", "")
    if sicherer_pfad(weiter):
        return redirect(weiter_ohne_hinweis(weiter))
    return redirect("verfahren:parlament")


def _regler_aus_post(request):
    from plattform_core.weicherfilter import REGLER, regler_bereinigen

    return regler_bereinigen({name: request.POST.get(f"r_{name}") for name in REGLER})


@login_required
@require_POST
@transaction.atomic
def filter_anwenden(request):
    """P5: Regler anwenden — ins aktive Profil speichern oder als neues Profil
    anlegen (Höchstzahl aus dem Register). Wirkt nur auf die eigene Ansicht (§ 2 Abs 6)."""
    # Die Grenze gilt auch bei gleichzeitigen Neuanlagen desselben Mitglieds.
    get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    hoechstzahl = FilterProfil.hoechstzahl()
    regler = _regler_aus_post(request)
    favoriten_zuerst = bool(request.POST.get("favoriten_zuerst"))
    profile = request.user.filterprofile
    name_neu = (request.POST.get("profilname") or "").strip()[:24]
    werte = {"regler": regler, "favoriten_zuerst": favoriten_zuerst}

    zu_viele = (
        _("Höchstens %(grenze)s Konfigurationen — bitte zuerst eine löschen oder überschreiben.")
        % {"grenze": hoechstzahl}
        if hoechstzahl else _("Neue Konfigurationen sind gesperrt.")
    )
    if request.POST.get("als_neues"):
        if not name_neu:
            return _zurueck_zum_parlament(
                request, "name_fehlt", "error", _("Bitte einen Namen für die neue Konfiguration angeben.")
            )
        if profile.count() >= hoechstzahl and not profile.filter(name=name_neu).exists():
            return _zurueck_zum_parlament(request, "profile_voll", "error", zu_viele)
        profil, _egal = FilterProfil.objects.update_or_create(mitglied=request.user, name=name_neu, defaults=werte)
    else:
        profil = profile.filter(aktiv=True).first()
        if profil is None:
            if profile.count() >= hoechstzahl:
                return _zurueck_zum_parlament(request, "profile_voll", "error", zu_viele)
            profil, _egal = FilterProfil.objects.get_or_create(
                mitglied=request.user, name=str(_("Eigenes")), defaults=werte
            )
        profil.regler = regler
        profil.favoriten_zuerst = favoriten_zuerst
    profil.aktiv = True
    profil.save()
    profile.exclude(pk=profil.pk).update(aktiv=False)
    return _zurueck_zum_parlament(
        request, "filter_aktiv", "success",
        _("Ihr Filter „%s“ ist aktiv — die Reihung folgt jetzt Ihren offenen Reglern.") % profil.name,
    )


@login_required
@require_POST
def beanstanden(request, pk):
    """FB-F2 (§ 6 Abs 11 lit b): eine Einschätzung der Zukunftswerkstatt beanstanden.
    Der Vermerk ist öffentlich und bleibt stehen. Er ist als Anforderung eines Korrekturlaufs
    gedacht. Für festgehaltene öffentliche Rechtsbezüge kann die zuständige Gruppe 1 eine
    getrennte Nachrechnung anfordern. Andere Einschätzungen sind noch nicht erfasst.
    Wie jede Mitwirkung mit Namen im Arbeitsbereich: nur bestätigte, aktive Mitglieder (§ 4,
    F-51) — sonst könnte ein ungeprüftes Konto unbegrenzt öffentliche Texte absetzen."""
    from ki.models import Zweck
    from verfahren.models import AuditEintrag, Beanstandung
    from verfahren.views import _lesbarer_lauf

    antrag = get_object_or_404(Antrag, pk=pk)
    if antrag.art in (Antragsart.MANDAT, Antragsart.VERTRAUENSFRAGE):
        # Über Menschen rechnet keine Maschine (FB-F4): Bei Personenwahlen gibt es keine Einschätzung,
        # also nichts zu beanstanden — kein unsichtbarer Datensatz, keine falsche Rückmeldung (GP-084).
        raise Http404
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    text = (request.POST.get("text") or "").strip()[:2000]
    if not text:
        messages.error(request, _("Bitte beschreiben Sie, was an der Einschätzung falsch ist."))
        return _zurueck_zum_antrag(request, antrag)
    # Das Formular steht in der Kopfkarte: Ziel ist die Einschätzung, die sie zeigt; ohne eine
    # solche der jüngste lesbare Lauf (Rechtsbezug) — nie der Textvektor-Lauf, den liest kein Mensch.
    lauf = _lesbarer_lauf(antrag, Zweck.EINSCHAETZUNG) or _lesbarer_lauf(antrag)
    # Neue Formulare binden genau den gelesenen Lauf. Eine inzwischen neue
    # Einschätzung darf das Ziel eines bereits geöffneten Formulars nicht ändern.
    if request.POST.get("lauf"):
        from ki.models import KILauf

        try:
            lauf = KILauf.objects.get(pk=int(request.POST["lauf"]), antrag=antrag,
                erfolgreich=True, zweck__in=(Zweck.EINSCHAETZUNG, Zweck.RECHTSBEZUG, Zweck.RECHTSFOLGEN))
        except (ValueError, KILauf.DoesNotExist):
            messages.error(request, _("Der gewählte Lauf gehört nicht zu dieser öffentlichen Einschätzung."))
            return _zurueck_zum_antrag(request, antrag)
    # Drossel je Konto und Stunde, wie beim Bedeutungsvergleich: Jeder Vermerk bleibt dauerhaft
    # öffentlich stehen — ein einzelnes Konto soll die Zone nicht füllen können (GP-084).
    from mitglieder.botschutz import drossel_zuviel

    # Registerwert `beanstandung-je-stunde` je Konto und Kalenderstunde: 0 heißt keine Grenze und sperrt nie
    # (ausgeliefert ausgeschaltet, Zahl offen: E-13.4); ab 1 drosselt der Wert.
    grenze = zahl("beanstandung-je-stunde", 0)
    if grenze >= 1 and drossel_zuviel(None, "beanstandung", grenze, kennung=f"konto:{request.user.pk}"):
        messages.error(request, ngettext(
            "Höchstens eine Beanstandung je Stunde — bitte später noch einmal.",
            "Höchstens %(n)s Beanstandungen je Stunde — bitte später noch einmal.",
            grenze,
        ) % {"n": grenze})
        return _zurueck_zum_antrag(request, antrag)
    with transaction.atomic():
        beanstandung = Beanstandung.objects.create(antrag=antrag, lauf=lauf, mitglied=request.user, text=text)
        AuditEintrag.anhaengen(
            {
                "typ": "einschaetzung_beanstandet",
                "antrag": antrag.pk,
                "beanstandung": beanstandung.pk,
                "lauf": lauf.pk if lauf else None,
            }
        )
    messages.success(
        request,
        _(
            "Ihre Beanstandung ist öffentlich vermerkt und bleibt stehen. Die zuständige Gruppe 1 kann "
            "für einen festgehaltenen öffentlichen Rechts- oder Folgenbericht eine Nachrechnung anfordern."
        ),
    )
    return _zurueck_zum_antrag(request, antrag)


@login_required
@require_POST
def korrektur_anfordern(request, pk, beanstandung_pk):
    from django.core.exceptions import ValidationError
    from django.http import HttpResponseForbidden

    from ki.korrekturen import anfordern
    from verfahren.models import Beanstandung

    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    b = get_object_or_404(Beanstandung, pk=beanstandung_pk, antrag=antrag)
    try:
        anfordern(b, request.user)
    except PermissionError:
        return HttpResponseForbidden(_("Eine Nachrechnung kann nur die für diesen Antrag zuständige aktive Gruppe 1 anfordern."))
    except ValidationError as fehler:
        messages.error(request, fehler.messages[0])
    else:
        messages.success(request, _("Die Nachrechnung ist eingereiht. Original und Beanstandung bleiben unverändert; es gelten die vorhandenen Modellbudgets."))
    # Der Anker öffnet am Handy auch mit JavaScript die richtige Zone.
    return redirect(reverse("verfahren:antrag", args=[antrag.pk]) + f"#beanstandung-{b.pk}")


def _zurueck_zum_antrag(request, antrag):
    weiter = request.POST.get("weiter", "")
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:antrag", pk=antrag.pk)


@login_required
@require_POST
def filter_vorschau(request):
    """FB-B2 Live-Vorschau: reiht mit den gerade gezogenen Reglern, speichert nichts —
    die Antwort ist nur die Liste (#filter-liste), htmx tauscht sie sanft aus."""
    from verfahren.views import LAUFEND, _abo_ids, _meine_favoriten, _meine_stimmen, _weicherfilter_feed

    regler = _regler_aus_post(request)
    favoriten_zuerst = bool(request.POST.get("favoriten_zuerst"))
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)
    jetzt = timezone.now()
    feed = _weicherfilter_feed(
        request.user, antraege, laufend, jetzt, _abo_ids(request.user),
        _meine_stimmen(request.user, list(laufend)), regler, favoriten_zuerst,
    )
    return render(
        request,
        "verfahren/_filter_liste.html",
        {
            "feed": feed,
            # Derselbe Stern wie im Parlament: Ohne die Favoriten stand er leer, und sein Klick
            # entfernte den Favoriten (GP-072).
            "meine_favoriten": _meine_favoriten(request.user),
            "meine_unterstuetzungen": set(
                Unterstuetzung.gueltige().filter(mitglied=request.user).values_list("antrag_id", flat=True)
            ),
            # Die Zeilen der Vorschau kehren nach einer Handlung ins Parlament zurück — nicht auf
            # diese POST-Adresse (`request.get_full_path` wäre /filter/vorschau/).
            "weiter_ziel": reverse("verfahren:parlament"),
        },
    )


@login_required
@require_POST
@transaction.atomic
def filter_favoriten(request):
    """FB-B1: Schalter „★ Favoriten zuerst“ umschalten — in der aktiven Konfiguration,
    sonst in der Voreinstellung des Mitglieds."""
    mitglied = get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    profil = mitglied.filterprofile.filter(aktiv=True).first()
    if profil is not None:
        profil.favoriten_zuerst = not profil.favoriten_zuerst
        profil.save(update_fields=["favoriten_zuerst"])
    else:
        mitglied.favoriten_zuerst = not mitglied.favoriten_zuerst
        mitglied.save(update_fields=["favoriten_zuerst"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
@transaction.atomic
def filter_umbenennen(request, pk):
    """FB-B3: Konfiguration umbenennen (≤ 24 Zeichen, je Mitglied eindeutig)."""
    get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    name = (request.POST.get("name") or "").strip()[:24]
    if not name:
        return _zurueck_zum_parlament(request, "name_fehlt", "error", _("Bitte einen Namen angeben."))
    if request.user.filterprofile.exclude(pk=profil.pk).filter(name=name).exists():
        return _zurueck_zum_parlament(
            request, "name_vergeben", "error", _("Eine Konfiguration mit diesem Namen gibt es schon.")
        )
    profil.name = name
    profil.save(update_fields=["name"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
@transaction.atomic
def filter_waehlen(request, pk):
    get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    request.user.filterprofile.update(aktiv=False)
    profil.aktiv = True
    profil.save(update_fields=["aktiv"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
@transaction.atomic
def filter_neutral(request):
    """Zurück zur strengen Voreinstellung: Phase und Frist, chronologisch."""
    get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    request.user.filterprofile.update(aktiv=False)
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
@transaction.atomic
def filter_loeschen(request, pk):
    get_object_or_404(Mitglied.objects.select_for_update(), pk=request.user.pk)
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    profil.delete()
    return _zurueck_zum_parlament(request, "profil_geloescht", "info", _("Profil „%s“ gelöscht.") % profil.name)


@login_required
@require_POST
def bewerben(request, pk):
    """§ 7 Abs 1 (F-70): sich am Kandidatur-Antrag beteiligen — man wird im
    Antragsfenster als wählbar geführt. Möglich bis zum Abstimmungsbeginn."""
    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    if not oertlich_zulaessig(antrag, request.user):
        return _oertlich_abweisen(request, antrag)
    if not request.user.ist_stimmberechtigt(
        Gegenstand.PERSONENWAHL, timezone.localdate(), uebergang=uebergangsregel_fuer(antrag)
    ):
        return render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    if not request.POST.get("waehlbar"):
        messages.error(
            request,
            _("Bitte bestätigen Sie, dass Sie die gesetzlichen Voraussetzungen der Wählbarkeit erfüllen."),
        )
        return redirect("verfahren:antrag", pk=pk)
    # § 7 Abs 3: Die Erklärung, ob die Rückgabezusage abgegeben wird, gehört zur Beteiligung am
    # Kandidatur-Antrag — Pflichtangabe, aber frei in beide Richtungen; „nicht abgegeben“ ist
    # weder Hindernis noch Makel, nur ein öffentlich ausgewiesener Sachverhalt.
    zusage = request.POST.get("rueckgabezusage", "")
    if zusage not in (Rueckgabezusage.ABGEGEBEN.value, Rueckgabezusage.NICHT_ABGEGEBEN.value):
        messages.error(
            request,
            _("Bitte erklären Sie, ob Sie die Rückgabezusage abgeben oder nicht abgeben (§ 7 Abs 3) — beides ist zulässig."),
        )
        return redirect("verfahren:antrag", pk=pk)
    try:
        bewerbung_einreichen(antrag, request.user, request.POST.get("vorstellung", ""), rueckgabezusage=zusage)
        messages.success(
            request, _("Ihre Bewerbung ist erfasst — Sie werden im Antragsfenster als wählbar geführt.")
        )
    except BewerbungsFehler as fehler:
        if kandidatursperre(request.user):
            # § 7 Abs 10 lit f Z 3: Die Fachoperation sagt, warum — übersetzt.
            messages.error(request, str(fehler))
        else:
            messages.error(request, _("Bewerben ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1)."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def bewerbung_zurueckziehen(request, pk):
    """Der Rückzug bleibt dokumentiert; die Bewerbung zählt nicht mehr.

    Möglich nur bis zum Abstimmungsbeginn — wie das Bewerben (§ 7 Abs 1). Ein Rückzug
    während der Wahl nähme den Zustimmungen ihre Bewerbung: `kandidatur_auszaehlen` zählt
    Beteiligung nur aus verbliebenen Zustimmungen, eine Wahl ließe sich so gezielt unter die
    Mindestbeteiligung drücken, ohne dass die Wähler es erfahren."""
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value):
        messages.error(request, _("Ein Rückzug ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1)."))
        return redirect("verfahren:antrag", pk=pk)
    bewerbung = antrag.bewerbungen.filter(mitglied=request.user, zurueckgezogen=False).first()
    if bewerbung:
        from verfahren.models import AuditEintrag

        with transaction.atomic():  # GP-129: Rückzug und Eintrag gemeinsam oder gar nicht
            bewerbung.zurueckgezogen = True
            bewerbung.save(update_fields=["zurueckgezogen"])
            AuditEintrag.anhaengen(
                {"typ": "bewerbung_zurueckgezogen", "antrag": antrag.pk, "bewerbung": bewerbung.pk}
            )
        messages.info(request, _("Ihre Bewerbung ist zurückgezogen — das bleibt öffentlich dokumentiert."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def kandidatur_zustimmen(request, pk, bewerbung_pk):
    """Zustimmungswahl (§ 7 Abs 1): Zustimmung geben oder zurücknehmen —
    geheim über das Stimmregister, änderbar bis zum Fristende."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not oertlich_zulaessig(antrag, request.user):
        return _oertlich_abweisen(request, antrag)
    antrag.fortschreiben()
    stichtag = antrag.stichtag_der_stimmberechtigung()
    if not request.user.ist_stimmberechtigt(
        Gegenstand.PERSONENWAHL, stichtag, uebergang=uebergangsregel_fuer(antrag)
    ):
        # Gesperrte Konten erfahren den wahren Grund, nicht den zur Anwartschaft (GP-070)
        return _mitwirkung_gesperrt(request) or render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    if request.user.adresswechsel_offen:
        messages.error(
            request,
            _("Für Ihr Konto läuft eine Änderung der Anmeldeadresse — bis sie entschieden ist, ruht die Stimmabgabe."),
        )
        return redirect("verfahren:antrag", pk=pk)
    bewerbung = get_object_or_404(Bewerbung, pk=bewerbung_pk, antrag=antrag)
    try:
        dazu = bewerbung_zustimmen(antrag, request.user, bewerbung)
        if dazu:
            messages.success(request, _("Zustimmung erfasst — bis zum Fristende können Sie sie zurücknehmen."))
        else:
            messages.info(request, _("Zustimmung zurückgenommen."))
    except StimmabgabeFehler:
        messages.error(
            request, _("Diese Zustimmung konnte nicht erfasst werden (läuft die Abstimmung noch?).")
        )
    return redirect("verfahren:antrag", pk=pk)


@offenes_format  # GP-199: öffentlich, ohne Anmeldung dasselbe
def export_json(request, pk):
    """F-21/F-23: maschinenlesbarer Export zum unabhängigen Nachrechnen —
    kompatibel mit verify/nachrechnen.py. Erst nach Abstimmungsende verfügbar,
    damit kein Zwischenstand die laufende Abstimmung beeinflusst."""
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    if antrag.phase not in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        return JsonResponse({"fehler": "Export erst nach Abstimmungsende (§ 5 Abs 3 lit d)."}, status=409)
    daten = {
        "antrag": antrag.pk,
        "titel": antrag.titel,
        "art": antrag.art,
        "eigenstaendigkeit": einstufungen(antrag),
        "policy": antrag.policy_snapshot,
        "stimmberechtigte": antrag.stimmberechtigte_anzahl,
        "stimmen": [
            {"pseudonym": s.pseudonym.hex, "stimme": s.stimme}
            for s in antrag.stimmabgaben.order_by("pseudonym")
        ],
        "exportiert_am": timezone.now().isoformat(),
    }
    if antrag.teilnahmegebiet is not None:
        daten["teilnahmegebiet"] = antrag.teilnahmegebiet
        daten["teilnehmerkreis_am"] = antrag.teilnehmerkreis_am.isoformat() if antrag.teilnehmerkreis_am else None
    vf = antrag._vertrauensfrage()
    if vf is not None:
        # § 7 Abs 10 lit e: ausgezählt wie eine Sachfrage — `art` bleibt „vertrauensfrage“, damit
        # verify/nachrechnen.py „verloren/gewonnen“ liefert; dazu, worüber entschieden wurde.
        daten["vertrauensfrage"] = {
            "art": vf.art,
            "mandat": vf.mandat_id,
            "stimmberechtigte_am_einbringungstag": vf.stimmberechtigte_partei_am_einbringungstag,
            "schwelle": vf.schwelle_partei,
            "ergebnis": vf.ergebnis_wort,
        }
    if antrag.art == Antragsart.MANDAT:
        # Personenwahl (§ 7 Abs 1): Bewerbungen in Einreichungsreihenfolge und alle
        # Zustimmungen (Pseudonym → Bewerbung) — jede Person kann das Ergebnis
        # damit unabhängig nachrechnen; die eigene Stimme findet man per Prüfcode.
        daten["bewerbungen"] = [
            {
                "bewerbung": b.pk,
                "name": b.mitglied.anzeigename,
                "eingereicht_am": b.erstellt_am.isoformat(),
                "zurueckgezogen": b.zurueckgezogen,
            }
            for b in antrag.bewerbungen.all()
        ]
        # Vollständig UND nachrechenbar: zurückgenommene Zustimmungen stehen mit Vermerk dabei
        # (Grundregel 7), die Auszählung zählt nur die gültigen. Kein Zeitpunkt: Er verbände das
        # Pseudonym mit einem Eintrag der öffentlichen Audit-Kette (GP-022).
        daten["zustimmungen"] = [
            {
                "pseudonym": z.pseudonym.hex,
                "bewerbung": z.bewerbung_id,
                "zurueckgenommen": z.zurueckgenommen_am is not None,
            }
            for z in BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).order_by(
                "pseudonym", "bewerbung_id"
            )
        ]
    # Die Audit-Spur des Antrags mit vollem Hash und Vorgänger — verify/nachrechnen.py rechnet jeden
    # ungekürzten Eintrag nach (Bestandsaufnahme A7).
    from verfahren.archiv import audit_spur, nachweis_felder

    daten.update(nachweis_felder(antrag))  # Stichtag und Prüfsummen zum Abgleich mit der Kette (GP-028)
    daten["audit"] = audit_spur(antrag)
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Content-Disposition"] = f'attachment; filename="antrag-{antrag.pk}-export.json"'
    return antwort


def eigene_stimme(request, pk):
    """Zeigt dem eingeloggten Mitglied Pseudonym und Prüfcode der eigenen Stimme
    (F-21: 'meine Stimme steht korrekt in der Liste')."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not request.user.is_authenticated:
        from mitglieder.anmeldeziel import zur_anmeldung

        return zur_anmeldung(request)  # GP-100: mit der Seite als Ziel
    if request.user.adresswechsel_offen:
        # F-51: Bis die Adressänderung entschieden ist, bleibt das Pseudonym verborgen — sonst
        # erreichte eine Kontoübernahme genau das, was das Stimmgeheimnis schützt.
        return render(request, "verfahren/eigene_stimme.html", {"antrag": antrag, "eintrag": None, "gesperrt": True})
    eintrag = StimmRegister.objects.filter(antrag=antrag, mitglied=request.user).first()
    return render(request, "verfahren/eigene_stimme.html", {"antrag": antrag, "eintrag": eintrag})


@login_required
@require_POST
def favorisieren(request, pk):
    """Bereich a (§ 5 Abs 10 lit a, F-41): Favorit setzen bzw. entfernen.
    Favoriten sind rein persönlich und wirken nie auf Reihung oder Ergebnis."""
    antrag = get_object_or_404(Antrag, pk=pk)
    _egal, neu = Favorit.objects.get_or_create(antrag=antrag, mitglied=request.user)
    if not neu:
        Favorit.objects.filter(antrag=antrag, mitglied=request.user).delete()
    weiter = request.POST.get("weiter", "")
    if request.headers.get("HX-Request"):
        # App-Verhalten (P1): Der Stern tauscht sich selbst aus, ohne Neuladen und ohne
        # Flash-Meldung — ohne JavaScript läuft derselbe POST als gewöhnlicher Redirect weiter.
        return render(
            request,
            "verfahren/_stern.html",
            {"antrag": antrag, "ist_favorit": neu, "weiter": weiter or "/"},
        )
    if neu:
        messages.success(
            request,
            # GP-052: der Ort, den es gibt — „★ Gemerkt“ im WeicherFilter führt zu allen gemerkten Anträgen
            _("Gemerkt — Sie finden den Antrag im Parlament unter „★ Gemerkt“."),
        )
    else:
        messages.info(request, _("Favorit entfernt."))
    if sicherer_pfad(weiter):
        return redirect(weiter_ohne_hinweis(weiter))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def vollzug_eintragen(request, pk):
    """F-55, § 6 Abs 10: den Umsetzungsstand fortschreiben. Bis das Rollensystem
    (F-05) den Integrations- und Berichtswesenrat abbildet, schreiben Admins fort —
    jeder Eintrag ist öffentlich, dauerhaft und auditiert."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not request.user.hat_adminrechte:
        return render(request, "mitglieder/verwaltung_kein_zugang.html", status=403)
    from verfahren.models import Vollzugsstatus

    status = request.POST.get("status", "")
    if status not in Vollzugsstatus.values:
        # Eigene Meldung (GP-173): Sonst fiel der unbekannte Stand unter „nur angenommene Anträge“.
        messages.error(request, _("Unbekannter Umsetzungsstand: „%(stand)s“.") % {"stand": status[:40]})
        return redirect("verfahren:antrag", pk=pk)
    try:
        vollzug_fortschreiben(
            antrag, request.user, request.POST.get("status", ""), request.POST.get("vermerk", "")
        )
        messages.success(request, _("Umsetzungsstand fortgeschrieben — öffentlich im Register sichtbar."))
    except VollzugAusgesetzt:
        messages.error(
            request,
            _("Der Vollzug ist durch den Integritätsrat ausgesetzt — solange die Aussetzung läuft, wird das Register nicht fortgeschrieben (§ 6 Abs 3 lit d)."),
        )
    except ValueError:
        messages.error(request, _("Das Umsetzungsregister führt nur angenommene Anträge."))
    return redirect("verfahren:antrag", pk=pk)


def _laufend_je_ast() -> dict[int, int]:
    """Laufende Anträge je Knoten EINSCHLIESSLICH aller Unterkategorien —
    mit zwei Datenbankabfragen statt einer je Knoten."""
    from django.db.models import Count

    direkt: dict[int, int] = {
        zeile["kategorien"]: zeile["n"]
        for zeile in Antrag.objects.filter(phase__in=OFFENE_PHASEN, kategorien__isnull=False)
        .values("kategorien")
        .annotate(n=Count("id", distinct=True))
    }
    kinder: dict[int | None, list[int]] = {}
    for kid, eid in Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id"):
        kinder.setdefault(eid, []).append(kid)
    summen: dict[int, int] = {}

    def summe(kid: int) -> int:
        if kid not in summen:
            summen[kid] = direkt.get(kid, 0) + sum(summe(c) for c in kinder.get(kid, []))
        return summen[kid]

    for geschwister in kinder.values():
        for kid in geschwister:
            summe(kid)
    return summen


def kategorie_weiter(request, slug=None):
    """Die alte Lebensbereiche-Seite ist bewusst gefallen (Vorgabe 1.9. abends):
    Der Fächer wohnt direkt im Parlament, die Suche im Feldkopf. Alte Adressen
    und Lesezeichen landen sanft am richtigen Ort."""
    ziel = reverse("verfahren:parlament")
    if slug:
        return redirect(f"{ziel}?fach={slug}#feld-favoriten")
    return redirect(f"{ziel}#feld-favoriten")


@login_required
@require_POST
def kategorie_abonnieren(request, slug):
    """Abo umschalten — rein persönlich, wirkt nie auf Reihung oder Ergebnis."""
    kategorie = get_object_or_404(Kategorie, slug=slug, aktiv=True)
    _egal, neu = KategorieAbo.objects.get_or_create(kategorie=kategorie, mitglied=request.user)
    if not neu:
        KategorieAbo.objects.filter(kategorie=kategorie, mitglied=request.user).delete()
    weiter = request.POST.get("weiter", "")
    weiter = weiter_ohne_hinweis(weiter) if sicherer_pfad(weiter) else reverse("verfahren:parlament")
    if request.headers.get("HX-Request"):
        # FB-C4: mit htmx wechselt nur der Stern selbst — kein Feldtausch, keine Flash-Meldung
        return render(
            request,
            "verfahren/_kategorie_stern.html",
            {"slug": slug, "name": kategorie.name, "abonniert": neu, "weiter": weiter},
        )
    if neu:
        messages.success(
            request,
            _("„%s“ ist jetzt Favorit — Neues daraus erscheint in Ihrem Hauptfenster.") % kategorie.name,
        )
    else:
        messages.info(request, _("Favorit „%s“ entfernt.") % kategorie.name)
    return redirect(weiter)
