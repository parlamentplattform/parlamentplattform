"""Die Karte „Fachliste“ für das Profil (GP-009): Das Mitglied erklärt dort selbst seine Einwilligung,
öffentlich auf der Fachliste geführt zu werden (§ 6 Abs 7, § 8 Abs 4), und nimmt sie zurück, solange es
nicht auf der Liste geführt wird (der Widerruf der Namensnennung am Eintrag ist offen, E-10.8).

Einbinden mit `{% load gremien_profil %}{% fachliste_einwilligung %}`."""

from django import template

register = template.Library()


@register.inclusion_tag("gremien/_fachliste_einwilligung.html", takes_context=True)
def fachliste_einwilligung(context):
    from gremien.models import Fachliste, FachlistenEinwilligung
    from gremien.views import _fachliste_waehlbar

    nutzer = context.get("user")
    if nutzer is None and context.get("request") is not None:
        nutzer = context["request"].user
    if nutzer is None or not nutzer.is_authenticated:
        return {"zeigen": False}
    # Dieselbe Bedingung wie am Endpunkt: Wer dort abgewiesen würde (Gemeindekonto, pausiert,
    # Testkonto), bekommt die Karte nicht gezeigt.
    if not _fachliste_waehlbar().filter(pk=nutzer.pk).exists():
        return {"zeigen": False}
    return {
        "zeigen": True,
        "erklaert": FachlistenEinwilligung.liegt_vor(nutzer),
        "eintrag": Fachliste.objects.filter(mitglied=nutzer).first(),
        "csrf_token": context.get("csrf_token"),
    }
