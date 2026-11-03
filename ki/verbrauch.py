"""Eine lesende Gruppenabfrage, keine zusätzlichen Modell- oder Anbieteraufrufe."""

from django.db.models import Case, CharField, Count, F, Q, Sum, Value, When
from django.utils.translation import gettext_lazy as _

from ki.models import KILauf, Zweck
from plattform_core.modellverbrauch import zusammenfassen


def fuer_antrag(antrag):
    if not antrag.pk:
        raise ValueError("Verbrauch braucht einen gespeicherten Antrag.")
    gruppen = list(KILauf.objects.filter(antrag=antrag).annotate(
        verbrauch_zweck=Case(When(zweck__in=Zweck.values, then=F("zweck")),
                            default=Value("sonstige"), output_field=CharField()),
    ).values("verbrauch_zweck").annotate(
        laeufe=Count("pk"), fehlversuche=Count("pk", filter=Q(erfolgreich=False)),
        tokens_ein=Sum("tokens_ein", default=0), tokens_aus=Sum("tokens_aus", default=0),
        dauer_ms=Sum("dauer_ms", default=0),
    ).order_by("verbrauch_zweck"))
    return zusammenfassen([{**{k: v for k, v in z.items() if k != "verbrauch_zweck"},
                            "zweck": z["verbrauch_zweck"]} for z in gruppen])


def anzeige(daten):
    return {**daten, "zeilen": [{**z, "name": Zweck(z["zweck"]).label if z["zweck"] in Zweck.values
                                else _("Weitere Zwecke")} for z in daten["zeilen"]]}
