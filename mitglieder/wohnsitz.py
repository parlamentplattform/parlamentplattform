"""Wohnsitzangabe ohne erzwungene oder erfundene österreichische Gemeinde."""

from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from mitglieder.models import Gemeinde, Wohnsitzart


def wohnsitz_auswahl(*, registrierung=False):
    return forms.ChoiceField(
        label=gettext_lazy("Wohnsitz"),
        choices=[(w, n) for w, n in Wohnsitzart.choices if w or not registrierung],
        required=False,
        widget=forms.Select(attrs={"class": "wohnsitz-auswahl"}),
        initial=Wohnsitzart.OESTERREICH if registrierung else "",
        help_text=gettext_lazy(
            "Eine österreichische Gemeinde ist nur bei „Wohnsitz in Österreich“ erforderlich. "
            "Ohne festen Wohnsitz oder mit Wohnsitz im Ausland lassen Sie die Gemeinde leer."
        ),
    )


class WohnsitzFormularMixin:
    wohnsitz_pflicht = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemeinde_objekt = None

    def clean_gemeinde(self):
        # Auch ohne JavaScript: Ein beim Wechsel noch mitgesendeter alter Ort wird verworfen.
        if "wohnsitz_art" in self.data and self.data.get("wohnsitz_art") != Wohnsitzart.OESTERREICH:
            return ""
        eingabe = self.cleaned_data["gemeinde"].strip()
        if not eingabe:
            return ""
        treffer, kandidaten = Gemeinde.finden(eingabe)
        if treffer:
            self.gemeinde_objekt = treffer
            return treffer.name
        if kandidaten:
            optionen = "; ".join(g.anzeige for g in kandidaten)
            if self.wohnsitz_pflicht:
                raise forms.ValidationError(_("Diesen Gemeindenamen gibt es mehrmals — bitte präzisieren: %s.") % optionen)
            raise forms.ValidationError(_("Mehrdeutig — bitte präzisieren: %(optionen)s.") % {"optionen": optionen})
        raise forms.ValidationError(_("Steht nicht im amtlichen Gemeindeverzeichnis."))

    def clean(self):
        daten = super().clean()
        # Alte bereits geöffnete Formulare besitzen die neue Auswahl noch nicht.
        art = daten.get("wohnsitz_art") or (Wohnsitzart.OESTERREICH if self.gemeinde_objekt else "")
        daten["wohnsitz_art"] = art
        if (art == Wohnsitzart.OESTERREICH or (self.wohnsitz_pflicht and not art)) and not self.gemeinde_objekt:
            if "gemeinde" not in self.errors:
                self.add_error("gemeinde", _("Bitte wählen Sie Ihre Wohnsitz-Gemeinde oder eine der anderen Wohnsitzoptionen."))
        return daten


def wohnsitz_anwenden(mitglied, form):
    """Angabe und regionale Felder gemeinsam setzen; Rückgabe für das Audit ohne Ortswerte."""
    g = form.gemeinde_objekt
    art = form.cleaned_data["wohnsitz_art"]
    alt = (mitglied.wohnsitz_art_aktuell, mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz_id)
    neu = (art, g.name if g else "", g.bundesland if g else "", g.pk if g else None)
    mitglied.wohnsitz_art, mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz_id = neu
    return ["wohnsitz"] if alt != neu else []
