"""URL-Konfiguration: bewusst flach und lesbar.

Der Django-Admin ist absichtlich nicht eingehängt: Verwaltung läuft über die
eigene, auditierte Mitgliederverwaltung unter /verwaltung/ (F-51).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("verfahren.urls")),
    path("", include("mitglieder.urls")),
    path("", include("uebersicht.urls")),
]
