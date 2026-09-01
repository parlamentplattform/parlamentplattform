"""URL-Konfiguration: bewusst flach und lesbar.

Der Django-Admin ist absichtlich nicht eingehängt: Verwaltung läuft über die
eigene, auditierte Mitgliederverwaltung unter /verwaltung/ (F-51).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("verfahren.urls")),
    path("", include("mitglieder.urls")),
    path("", include("uebersicht.urls")),
    path("", include("anstoss.urls")),  # das begleitende Feedback-Widget (F-69)
    path("", include("mandatare.urls")),  # die Mandatar-Steuerung, Stufe M1 (F-71)
    path("", include("gremien.urls")),  # die Gremien-Werkstatt, Ring 0a (F-66/F-67)
    path("", include("parameter.urls")),  # das Parameterregister, Ring 0b (F-68)
    path("i18n/", include("django.conf.urls.i18n")),  # Sprachumschalter (F-33), ohne JavaScript
]
