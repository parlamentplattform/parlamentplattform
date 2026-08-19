"""URL-Konfiguration: bewusst flach und lesbar."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("verfahren.urls")),
    path("", include("mitglieder.urls")),
    path("verwaltung/", admin.site.urls),
]
