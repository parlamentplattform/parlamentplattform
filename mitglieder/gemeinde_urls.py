from django.urls import path

from mitglieder import gemeinde

app_name = "gemeinde"
urlpatterns = [
    path("", gemeinde.start, name="start"),
    path("anmelden/", gemeinde.anmelden, name="anmelden"),
    path("bestaetigen/<str:token>/", gemeinde.bestaetigen, name="bestaetigen"),
    path("konto/", gemeinde.konto, name="konto"),
    path("konto/export.json", gemeinde.export, name="export"),
]
