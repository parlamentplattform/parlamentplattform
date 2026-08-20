"""Die Einführung nach der E-Mail-Bestätigung (F-53): drei ruhige Schritte.

1. Lebensbereiche finden (Favoriten wählen — freiwillig, mit Ast-Wirkung),
2. die erste Abstimmung verstehen (Pseudonym, Prüfcode, Fristen),
3. einen Antrag einbringen lernen (Ähnlichkeitshinweis).
Danach der Abschluss: der Mitgliedsbeitrag (Willkommensseite mit QR-Code).

Grundsätze: jederzeit überspringbar (§ 2 Abs 6 — nichts wird erzwungen),
ohne JavaScript, zweisprachig, mit stillen Grafiken im Plattform-Stil.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from plattform_core import Phase
from verfahren.models import Antrag, Kategorie

SCHRITTE = (1, 2, 3)


@login_required
def einfuehrung(request, schritt: int):
    if schritt not in SCHRITTE:
        raise Http404
    kontext = {"schritt": schritt, "schritte": SCHRITTE}
    if schritt == 1:
        wurzel = Kategorie.objects.filter(aktiv=True, eltern=None).order_by("reihenfolge").first()
        abonniert = set(request.user.kategorie_abos.values_list("kategorie_id", flat=True))
        kontext["saeulen"] = [
            {"k": s, "abonniert": s.pk in abonniert}
            for s in (wurzel.kinder.filter(aktiv=True).order_by("reihenfolge") if wurzel else [])
        ]
        kontext["gewaehlt"] = len(abonniert)
    elif schritt == 2:
        kontext["abstimmung"] = (
            Antrag.objects.filter(phase=Phase.ABSTIMMUNG.value)
            .order_by("-hervorgehoben", "phase_beginn")
            .first()
        )
    return render(request, "mitglieder/einfuehrung.html", kontext)
