from django.urls import path

from mandatare import gemeindehaushalt, gemeindeprojekte, gemeindesitzungsquellen, ratsinitiativen
from mitglieder import gemeinde

app_name = "gemeinde"
urlpatterns = [
    path("", gemeinde.start, name="start"),
    path("anmelden/", gemeinde.anmelden, name="anmelden"),
    path("bestaetigen/<str:token>/", gemeinde.bestaetigen, name="bestaetigen"),
    path("konto/", gemeinde.konto, name="konto"),
    path("konto/export.json", gemeinde.export, name="export"),
    path("ort/<str:kennziffer>/", gemeinde.ort, name="ort"),
    path("ort/<str:kennziffer>/haushalt/", gemeindehaushalt.liste, name="haushalt"),
    path("ort/<str:kennziffer>/projekte/", gemeindeprojekte.liste, name="projekte"),
    path("ort/<str:kennziffer>/projekte/<int:pk>/", gemeindeprojekte.detail, name="projekt"),
    path("ort/<str:kennziffer>/sitzungsunterlagen/", gemeindesitzungsquellen.liste, name="sitzungsquellen"),
    path("ort/<str:kennziffer>/ratsinitiativen/", ratsinitiativen.liste, name="ratsinitiativen"),
    path("ort/<str:kennziffer>/ratsinitiativen/<int:pk>/", ratsinitiativen.detail, name="ratsinitiative"),
]
