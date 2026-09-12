"""Das eigene Profil (FB-K5) und der Austritt (§ 4 Abs 5).

Grundsätze:
- Zugang hat jedes angemeldete Konto — auch pausierte und ungeprüfte: Datenexport
  und Austritt sind Rechte des Menschen, keine Mitwirkungsrechte (darum `login_required`
  und nicht die Mitwirkungssperre der Verfahrensansichten).
- Änderbar sind Anzeigename, Wohnsitz und Nebenwohnsitz. Die Anmeldeadresse ändert nur
  die Verwaltung (Einspruchslink, Wartefrist, zweiter Admin — `Adresswechsel`), der
  Anmeldename nie (an ihm hängt die Beitragsreferenz).
- Der Nebenwohnsitz ordnet nur zusätzlich einer Region zu, sobald die Stellgröße
  `region-nebenwohnsitz-zaehlt` auf 1 steht; am Stimmrecht ändert er nichts (§ 5 Abs 6).
- Jede schreibende Handlung landet im öffentlichen Audit-Log (F-22) — mit Feldnamen und
  Mitgliedsnummer, nie mit Werten (kein Ort, kein Name, keine Adresse).
- Austritt heißt Anonymisieren und Deaktivieren, nie Löschen (Grundregel 7, § 8 Abs 4):
  Anträge, Unterstützungen, Beiträge im Chat, Stimmen, Beitragseingänge und die Audit-
  Kette bleiben vollständig; nur das rein Persönliche geht.
"""

from __future__ import annotations

import json

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as dj_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from mitglieder.models import Adresswechsel, Gemeinde, Mitglied, Mitgliedsstatus
from parameter.models import zahl
from verfahren.models import AuditEintrag, BewerbungsZustimmung, Stimmabgabe, StimmRegister

BESTAETIGUNGSWORT = "AUSTRITT"
REGISTERSCHLUESSEL = "region-nebenwohnsitz-zaehlt"  # die Stellgröße, die der Profiltext nennt


class AustrittFehler(ValueError):
    """Der Austritt ist für dieses Konto nicht möglich (satzungsgebender Erstzugang)."""


def gemeinden_datalist() -> list[str]:
    """Die Werte der `<datalist id="gemeinden">` — „Name (Bezirk)“, wie Registrierung und Verwaltung."""
    return [f"{name} ({bezirk})" for name, bezirk in Gemeinde.objects.values_list("name", "bezirk")]


def nebenwohnsitz_zaehlt() -> int:
    """Die Stellgröße, die der Profiltext nennt (heute 0 oder 1); andere Werte wirken wie 0."""
    return zahl("region-nebenwohnsitz-zaehlt", 0)  # Literal: der Registerwächter liest den Aufruf


def _auditieren(aktion: str, mitglied: Mitglied, **extra) -> None:
    AuditEintrag.anhaengen({"typ": "profil", "aktion": aktion, "mitglied": mitglied.pk, **extra})


def _gemeinde_pruefen(eingabe: str) -> Gemeinde | None:
    """Leer → None; sonst genau eine Gemeinde des amtlichen Verzeichnisses (wie die Verwaltung)."""
    eingabe = eingabe.strip()
    if not eingabe:
        return None
    treffer, kandidaten = Gemeinde.finden(eingabe)
    if treffer:
        return treffer
    if kandidaten:
        optionen = "; ".join(g.anzeige for g in kandidaten)
        raise forms.ValidationError(_("Mehrdeutig — bitte präzisieren: %(optionen)s.") % {"optionen": optionen})
    raise forms.ValidationError(_("Steht nicht im amtlichen Gemeindeverzeichnis."))


class ProfilFormular(forms.Form):
    """Anzeigename, Wohnsitz, Nebenwohnsitz — was ein Mitglied selbst pflegt."""

    anzeigename = forms.CharField(
        label=gettext_lazy("Öffentlicher Anzeigename (leer = Klarname)"), max_length=50, required=False
    )
    gemeinde = forms.CharField(
        label=gettext_lazy("Wohnsitz-Gemeinde (leer = keine Angabe)"),
        max_length=140,
        required=False,
        widget=forms.TextInput(attrs={"list": "gemeinden", "autocomplete": "off"}),
    )
    nebenwohnsitz = forms.CharField(
        label=gettext_lazy("Nebenwohnsitz-Gemeinde (leer = keiner)"),
        max_length=140,
        required=False,
        widget=forms.TextInput(attrs={"list": "gemeinden", "autocomplete": "off"}),
    )

    def __init__(self, *args, mitglied: Mitglied, **kwargs):
        super().__init__(*args, **kwargs)
        self.mitglied = mitglied
        self.gemeinde_objekt: Gemeinde | None = None
        self.nebenwohnsitz_objekt: Gemeinde | None = None

    def clean_anzeigename(self) -> str:
        name = " ".join(self.cleaned_data["anzeigename"].split())  # Leerraum normalisieren
        if not name:
            return ""
        andere = Mitglied.objects.exclude(pk=self.mitglied.pk).annotate(
            klarname=Concat("first_name", Value(" "), "last_name")
        )
        kollision = andere.filter(
            Q(pseudonym_oeffentlich__iexact=name)
            | Q(klarname__iexact=name)
            | Q(first_name__iexact=name, last_name="")
            | Q(first_name="", last_name__iexact=name)
        )
        if kollision.exists():
            raise forms.ValidationError(
                _("Dieser Name ist schon vergeben — er gehört zum Anzeigenamen oder Klarnamen eines anderen Mitglieds.")
            )
        return name

    def clean_gemeinde(self) -> str:
        self.gemeinde_objekt = _gemeinde_pruefen(self.cleaned_data["gemeinde"])
        return self.gemeinde_objekt.name if self.gemeinde_objekt else ""

    def clean_nebenwohnsitz(self) -> str:
        self.nebenwohnsitz_objekt = _gemeinde_pruefen(self.cleaned_data["nebenwohnsitz"])
        return self.nebenwohnsitz_objekt.name if self.nebenwohnsitz_objekt else ""

    def clean(self):
        daten = super().clean()
        if (
            self.gemeinde_objekt is not None
            and self.nebenwohnsitz_objekt is not None
            and self.gemeinde_objekt.pk == self.nebenwohnsitz_objekt.pk
        ):
            self.add_error("nebenwohnsitz", _("Der Nebenwohnsitz ist bereits Ihr Wohnsitz."))
        return daten


def _profil_anwenden(mitglied: Mitglied, form: ProfilFormular) -> list[str]:
    """Schreibt die Formularwerte ans Mitglied; gibt die geänderten Felder zurück (für das Audit)."""
    d = form.cleaned_data
    geaendert: list[str] = []
    if mitglied.pseudonym_oeffentlich != d["anzeigename"]:
        mitglied.pseudonym_oeffentlich = d["anzeigename"]
        geaendert.append("anzeigename")
    g = form.gemeinde_objekt
    if g is not None:
        if mitglied.wohnsitz_id != g.pk:
            # Dreiklang wie Registrierung und Verwaltung: Name, Bundesland und Verweis gemeinsam.
            mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz = g.name, g.bundesland, g
            geaendert.append("wohnsitz")
    elif mitglied.gemeinde or mitglied.wohnsitz_id:
        mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz = "", "", None
        geaendert.append("wohnsitz")
    n = form.nebenwohnsitz_objekt
    neben_pk = n.pk if n is not None else None
    if mitglied.nebenwohnsitz_id != neben_pk:
        mitglied.nebenwohnsitz = n
        geaendert.append("nebenwohnsitz")
    if geaendert:
        mitglied.save()
        _auditieren("geaendert", mitglied, felder=sorted(geaendert))  # Feldnamen, nie Werte
    return geaendert


@login_required
def profil(request):
    mitglied = request.user
    if request.method == "POST":
        form = ProfilFormular(request.POST, mitglied=mitglied)
        if form.is_valid():
            if _profil_anwenden(mitglied, form):
                messages.success(request, _("Profil gespeichert."))
            else:
                messages.info(request, _("Keine Änderungen."))
            return redirect("mitglieder:profil")
    else:
        form = ProfilFormular(
            mitglied=mitglied,
            initial={
                "anzeigename": mitglied.pseudonym_oeffentlich,
                "gemeinde": mitglied.wohnsitz.anzeige if mitglied.wohnsitz_id else mitglied.gemeinde,
                "nebenwohnsitz": mitglied.nebenwohnsitz.anzeige if mitglied.nebenwohnsitz_id else "",
            },
        )
    return render(
        request,
        "mitglieder/profil.html",
        {
            "form": form,
            "gemeinden": gemeinden_datalist(),
            "nebenwohnsitz_zaehlt": nebenwohnsitz_zaehlt(),
            "registerschluessel": REGISTERSCHLUESSEL,
            "adresswechsel": Adresswechsel.offener(mitglied),
        },
    )


@login_required
@require_POST
def sitzungen_beenden(request):
    """Alle anderen Geräte abmelden — die eigene Sitzung bleibt.

    Es gibt kein Sitzungsmodell mit Mitgliedsbezug (Djangos DB-Sitzungen tragen die Kennung
    nur verschlüsselt in `session_data`). Der Hebel ist der Sitzungs-Hash: Jede Sitzung merkt
    sich `get_session_auth_hash()`, einen HMAC über das Passwortfeld. `set_unusable_password()`
    schreibt bei jedem Aufruf einen NEUEN Zufallswert in dieses Feld (das Konto ist ohnehin
    passwortlos — der Wert bleibt unbrauchbar, ändert sich aber). Damit stimmt der gespeicherte
    Hash aller bestehenden Sitzungen nicht mehr, und Djangos `get_user` verwirft sie beim
    nächsten Aufruf. `update_session_auth_hash` schreibt der aktuellen Sitzung den neuen Hash,
    darum bleibt genau dieses Gerät angemeldet. Die Beitragsreferenz hängt nicht am Passwort."""
    mitglied = request.user
    mitglied.set_unusable_password()
    mitglied.save(update_fields=["password"])
    update_session_auth_hash(request, mitglied)
    _auditieren("sitzungen_beendet", mitglied)
    messages.success(request, _("Alle anderen Geräte sind abgemeldet — dieses bleibt angemeldet."))
    return redirect("mitglieder:profil")


# ── Datenexport (Art 15 und 20 DSGVO) ────────────────────────────────────────


def _gemeinde_export(g: Gemeinde | None) -> dict | None:
    if g is None:
        return None
    return {"name": g.name, "bezirk": g.bezirk, "bundesland": g.get_bundesland_display()}


def _stimmen_export(mitglied: Mitglied) -> list[dict]:
    """Die eigenen Stimmen über das Stimmregister — Antrag, Pseudonym, Prüfcode, Stimmwert und
    Zustimmungen zu Bewerbungen. Nur der Mensch selbst sieht diese Brücke (F-25)."""
    stimmen = []
    for eintrag in StimmRegister.objects.filter(mitglied=mitglied).select_related("antrag").order_by("antrag_id"):
        abgabe = Stimmabgabe.objects.filter(antrag=eintrag.antrag, pseudonym=eintrag.pseudonym).first()
        zustimmungen = BewerbungsZustimmung.objects.filter(
            bewerbung__antrag=eintrag.antrag, pseudonym=eintrag.pseudonym
        ).select_related("bewerbung")
        stimmen.append(
            {
                "antrag": eintrag.antrag_id,
                "titel": eintrag.antrag.titel,
                "pseudonym": eintrag.pseudonym.hex,
                "pruefcode": eintrag.pruefcode,
                "stimme": abgabe.stimme if abgabe else None,
                "abgegeben_am": abgabe.abgegeben_am if abgabe else None,
                "zustimmungen": [
                    {
                        "bewerbung": z.bewerbung_id,
                        "abgegeben_am": z.abgegeben_am,
                        "zurueckgenommen_am": z.zurueckgenommen_am,
                    }
                    for z in zustimmungen
                ],
            }
        )
    return stimmen


def daten_export(mitglied: Mitglied) -> dict:
    """Alles, was die Plattform über diesen Menschen führt — eine Quelle, schlichte Abbildung.

    Nicht enthalten: Bank-Kennungen der Beitragseingänge (`umsatz_id`), Einspruchs- und
    Token-Hashes, Audit-Zeilen Dritter. Der Stimmregister-Teil fehlt, solange eine Änderung
    der Anmeldeadresse offen ist — dieselbe Sperre wie „Meine Stimme prüfen“ (F-51)."""
    m = mitglied
    daten: dict = {
        "exportiert_am": timezone.now(),
        "system_id": getattr(settings, "DDOE_SYSTEM_ID", ""),
        "mitglied": m.pk,
        "stammdaten": {
            "anmeldename": m.username,
            "email": m.email,
            "vorname": m.first_name,
            "nachname": m.last_name,
            "anzeigename": m.pseudonym_oeffentlich,
            "beitritt": m.beitritt,
            "identitaetsstufe": m.identitaetsstufe,
            "geprueft_seit": m.geprueft_seit,
            "status": m.status,
            "status_grund": m.status_grund,
            "status_seit": m.status_seit,
            "beitrag_zuletzt_am": m.beitrag_zuletzt_am,
            "ist_admin": m.ist_admin,
            "favoriten_zuerst": m.favoriten_zuerst,
            "registriert_am": m.date_joined,
            "zuletzt_angemeldet": m.last_login,
        },
        "wohnsitz": _gemeinde_export(m.wohnsitz) or ({"name": m.gemeinde} if m.gemeinde else None),
        "nebenwohnsitz": _gemeinde_export(m.nebenwohnsitz),
        "beitraege": [
            {"betrag": b.betrag, "gebucht_am": b.gebucht_am, "namens_hinweis": b.namens_hinweis}
            for b in m.beitraege.all()
        ],
        "adresswechsel": [
            {
                "status": w.status,
                "beantragt_am": w.beantragt_am,
                "frist_bis": w.frist_bis,
                "bestaetigt_am": w.bestaetigt_am,
                "erledigt_am": w.erledigt_am,
            }
            for w in m.adresswechsel.all()
        ],
        "antraege": [
            {"antrag": a.pk, "titel": a.titel, "art": a.art, "eingebracht_am": a.eingebracht_am, "phase": a.phase}
            for a in m.antraege.all()
        ],
        "unterstuetzungen": [
            {"antrag": u.antrag_id, "erklaert_am": u.erklaert_am, "zurueckgezogen_am": u.zurueckgezogen_am}
            for u in m.unterstuetzung_set.all()
        ],
        "kommentare": [
            {
                "antrag": k.antrag_id,
                "text": k.text,
                "phase": k.phase,
                "erstellt_am": k.erstellt_am,
                "bearbeitet_am": k.bearbeitet_am,
                "geloescht": k.geloescht,
                "ausgeblendet_am": k.ausgeblendet_am,
            }
            for k in m.kommentar_set.all()
        ],
        "reaktionen": [
            {"kommentar": r.kommentar_id, "art": r.art, "erstellt_am": r.erstellt_am} for r in m.reaktion_set.all()
        ],
        "favoriten": [{"antrag": f.antrag_id, "erstellt_am": f.erstellt_am} for f in m.favoriten.all()],
        "abos": [
            {"kategorie": a.kategorie_id, "erstellt_am": a.erstellt_am} for a in m.kategorie_abos.all()
        ],
        "filterprofile": [
            {"name": p.name, "regler": p.regler, "favoriten_zuerst": p.favoriten_zuerst, "aktiv": p.aktiv}
            for p in m.filterprofile.all()
        ],
        "bewerbungen": [
            {
                "antrag": b.antrag_id,
                "vorstellung": b.vorstellung,
                "erstellt_am": b.erstellt_am,
                "zurueckgezogen": b.zurueckgezogen,
            }
            for b in m.bewerbungen.all()
        ],
        "mandate": [
            {
                "mandat": md.pk,
                "bezeichnung": md.bezeichnung,
                "ebene": md.ebene,
                "gebiet": md.gebiet,
                "angetreten": md.angetreten,
                "beendet": md.beendet,
                "vorstellung": md.vorstellung,
                "aufgaben": [
                    {
                        "titel": a.titel,
                        "beschreibung": a.beschreibung,
                        "frist": a.frist,
                        "sitzungstag": a.sitzungstag,
                        "status": a.status,
                        "antrag": a.antrag_id,
                    }
                    for a in md.aufgaben.all()
                ],
                "berichte": [
                    {"art": b.art, "monat": b.monat, "text": b.text, "eingereicht_am": b.eingereicht_am}
                    for b in md.berichte.all()
                ],
                "rechenschaft": [
                    {
                        "gegenstand": r.gegenstand,
                        "sitzung_am": r.sitzung_am,
                        "beschluss_plattform": r.beschluss_plattform,
                        "stimme": r.stimme,
                        "begruendung": r.begruendung,
                        "eingetragen_am": r.eingetragen_am,
                    }
                    for r in md.rechenschaft.all()
                ],
            }
            for md in m.mandate.all()
        ],
        "rollen": [
            {
                "gremium": r.gremium,
                "berufen_am": r.berufen_am,
                "endet_am": r.endet_am,
                "bestaetigt": r.bestaetigt,
                "beendet_grund": r.beendet_grund,
                "antrag": r.antrag_id,
            }
            for r in m.rollen.all()
        ],
        "meldungen": [
            {
                "kommentar": me.kommentar_id,
                "grund": me.grund,
                "erlaeuterung": me.erlaeuterung,
                "erstellt_am": me.erstellt_am,
                "entscheidung": me.entscheidung,
            }
            for me in m.meldung_set.all()
        ],
        "beanstandungen": [
            {"antrag": b.antrag_id, "text": b.text, "erstellt_am": b.erstellt_am, "erledigt_vermerk": b.erledigt_vermerk}
            for b in m.beanstandung_set.all()
        ],
        "anstoesse": [
            {"text": a.text, "seite": a.seite, "erstellt": a.erstellt, "status": a.status} for a in m.anstoesse.all()
        ],
    }
    if m.adresswechsel_offen:
        daten["stimmen"] = None
        daten["stimmen_hinweis"] = str(
            _(
                "Für Ihr Konto läuft eine Änderung der Anmeldeadresse. Bis sie entschieden ist, "
                "zeigt die Plattform Ihren Registereintrag nicht an."
            )
        )
    else:
        daten["stimmen"] = _stimmen_export(m)
    return daten


@login_required
def export_json(request):
    """Art 15/20 DSGVO: die eigenen Daten zum Mitnehmen — nur an das angemeldete Konto."""
    inhalt = json.dumps(daten_export(request.user), ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
    _auditieren("datenexport", request.user)
    antwort = HttpResponse(inhalt, content_type="application/json; charset=utf-8")
    antwort["Content-Disposition"] = 'attachment; filename="meine-daten.json"'
    return antwort


# ── Austritt (§ 4 Abs 5) ─────────────────────────────────────────────────────


@transaction.atomic
def austreten(mitglied: Mitglied, jetzt=None) -> None:
    """Der selbst erklärte Austritt: anonymisieren und deaktivieren — alles oder nichts.

    Was bleibt (Grundregel 7, § 8 Abs 4): Anträge, Unterstützungen (auch zurückgezogene),
    Beiträge im Chat samt Verfasser-Verweis (NULL hieße „Die Plattform“), Reaktionen,
    Bewerbungen, Beitragseingänge (Buchhaltung), veröffentlichte Stimmen und Zustimmungen,
    beendete Mandate, Rollen und Fachlisteneinträge, die Audit-Kette. Das Pseudonym bleibt,
    damit veröffentlichte Dokumente ihren Namen behalten; wer unter Klarnamen auftrat,
    erscheint künftig als „Ehemaliges Mitglied n“.

    Das StimmRegister bleibt ebenfalls: Es ist der Ein-Stimme-Schutz laufender Abstimmungen
    (unique je Antrag und Mitglied) und der Weg, die eigene Stimme in der veröffentlichten Liste
    wiederzufinden. Audit-Kette und Stimmlisten tragen nur Pseudonyme; das inaktive Konto kann
    den Registereintrag nicht mehr aufrufen, und die satzungsmäßige Löschfrist gilt unverändert.

    Was geht: Klarname, Anmeldeadresse, Wohnsitze, Adminrechte, Anmeldbarkeit, Filterprofile,
    Abos, Favoriten, Lesestände, Tokens. Offene Mandate, aktive Rollen und der Fachlisteneintrag
    werden beendet, ein offener Adresswechsel widerrufen."""
    from gremien.models import Fachliste
    from mandatare.models import Mandat

    # Guard VOR dem Leeren: `ist_fixer_admin` hängt an der E-Mail-Adresse — nach dem Leeren
    # wäre er es nicht mehr, und die Verwaltung stünde herrenlos da.
    if mitglied.ist_fixer_admin:
        raise AustrittFehler(_("Der satzungsgebende Erstzugang kann nicht austreten."))
    jetzt = jetzt or timezone.now()
    heute = timezone.localdate(jetzt)

    wechsel = Adresswechsel.offener(mitglied)
    if wechsel is not None:
        wechsel.widerrufen("austritt")

    for mandat in Mandat.aktive_von(mitglied):
        mandat.beendet = heute
        mandat.save(update_fields=["beendet"])
        AuditEintrag.anhaengen({"typ": "mandat_beendet", "mandat": mandat.pk})

    for rolle in mitglied.rollen.filter(beendet_grund="", endet_am__gte=heute):
        rolle.beendet_grund = "Austritt"
        rolle.save(update_fields=["beendet_grund"])
        AuditEintrag.anhaengen({"typ": "rolle_beendet", "rolle": rolle.pk, "grund": rolle.beendet_grund})

    eintrag = Fachliste.objects.filter(mitglied=mitglied).first()
    if eintrag is not None:
        felder = []
        if eintrag.gestrichen_am is None:
            eintrag.gestrichen_am, eintrag.gestrichen_grund = heute, "Austritt"
            felder += ["gestrichen_am", "gestrichen_grund"]
        if eintrag.einwilligung_widerrufen_am is None:
            eintrag.einwilligung_widerrufen_am = heute  # § 8 Abs 4: der Schlüssel statt des Namens
            felder.append("einwilligung_widerrufen_am")
        if felder:
            eintrag.save(update_fields=felder)

    # Rein Persönliches — nichts davon betrifft ein Verfahren.
    mitglied.filterprofile.all().delete()
    mitglied.kategorie_abos.all().delete()
    mitglied.favoriten.all().delete()
    mitglied.lesestaende.all().delete()
    mitglied.tokens.all().delete()

    mitglied.status_setzen(Mitgliedsstatus.AUSGETRETEN, "")
    mitglied.is_active = False
    mitglied.ist_admin = False
    mitglied.first_name = mitglied.last_name = ""
    mitglied.email = ""
    mitglied.username = f"ausgetreten-{mitglied.pk}"  # unique und ohne Personenbezug
    mitglied.gemeinde, mitglied.bundesland = "", ""
    mitglied.wohnsitz = mitglied.nebenwohnsitz = None
    mitglied.status_grund = ""
    if not mitglied.pseudonym_oeffentlich:
        # Sonst fiele `anzeigename` auf den Anmeldenamen zurück — und der war die E-Mail-Adresse.
        mitglied.pseudonym_oeffentlich = f"Ehemaliges Mitglied {mitglied.pk}"
    mitglied.set_unusable_password()  # neuer Zufallswert: alle Sitzungen enden (siehe sitzungen_beenden)
    mitglied.save()
    AuditEintrag.anhaengen({"typ": "austritt", "mitglied": mitglied.pk})


@login_required
def austritt(request):
    mitglied = request.user
    if request.method == "POST":
        if request.POST.get("bestaetigung", "").strip() != BESTAETIGUNGSWORT:
            messages.error(request, _("Der Austritt wurde nicht vollzogen — das Bestätigungswort fehlt."))
            return redirect("mitglieder:profil_austritt")
        try:
            austreten(mitglied)
        except AustrittFehler as e:
            messages.error(request, str(e))
            return redirect("mitglieder:profil_austritt")
        dj_logout(request)
        messages.info(request, _("Sie sind ausgetreten. Ihr Konto ist geschlossen; Ihre Beiträge zu Verfahren bleiben."))
        return redirect("verfahren:index")
    return render(
        request,
        "mitglieder/profil_austritt.html",
        {
            "bestaetigungswort": BESTAETIGUNGSWORT,
            "offene_mandate": mitglied.aktive_mandate.count(),
            "aktive_rollen": mitglied.rollen.filter(beendet_grund="", endet_am__gte=timezone.localdate()).count(),
        },
    )
