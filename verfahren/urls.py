from django.urls import path
from django.views.generic import RedirectView

from verfahren import views, views_aktionen

app_name = "verfahren"
urlpatterns = [
    path("", views.index, name="index"),
    path("parlament/", views.parlament, name="parlament"),
    path("einbringen/", views_aktionen.einbringen, name="einbringen"),
    path("kategorien/", views_aktionen.kategorie_weiter, name="kategorien"),
    path(
        "kategorien/<slug:slug>/abonnieren/", views_aktionen.kategorie_abonnieren, name="kategorie_abonnieren"
    ),
    path("kategorien/<slug:slug>/", views_aktionen.kategorie_weiter, name="kategorie"),
    path("antrag/<int:pk>/", views.antrag_detail, name="antrag"),
    path("antrag/<int:pk>/unterstuetzen/", views_aktionen.unterstuetzen, name="unterstuetzen"),
    path("antrag/<int:pk>/favorisieren/", views_aktionen.favorisieren, name="favorisieren"),
    path("antrag/<int:pk>/kommentieren/", views_aktionen.kommentieren, name="kommentieren"),
    path("antrag/<int:pk>/abstimmen/", views_aktionen.abstimmen, name="abstimmen"),
    path("antrag/<int:pk>/bewerben/", views_aktionen.bewerben, name="bewerben"),
    path(
        "antrag/<int:pk>/bewerbung-zurueckziehen/",
        views_aktionen.bewerbung_zurueckziehen,
        name="bewerbung_zurueckziehen",
    ),
    path(
        "antrag/<int:pk>/zustimmen/<int:bewerbung_pk>/",
        views_aktionen.kandidatur_zustimmen,
        name="kandidatur_zustimmen",
    ),
    path("antrag/<int:pk>/export.json", views_aktionen.export_json, name="export"),
    path("antrag/<int:pk>/meine-stimme/", views_aktionen.eigene_stimme, name="eigene_stimme"),
    path("antrag/<int:pk>/vollzug/", views_aktionen.vollzug_eintragen, name="vollzug"),
    path("filter/anwenden/", views_aktionen.filter_anwenden, name="filter_anwenden"),
    path("filter/<int:pk>/waehlen/", views_aktionen.filter_waehlen, name="filter_waehlen"),
    path("filter/<int:pk>/loeschen/", views_aktionen.filter_loeschen, name="filter_loeschen"),
    path("filter/neutral/", views_aktionen.filter_neutral, name="filter_neutral"),
    path("zukunftswerkstatt/", views.zukunftswerkstatt, name="zukunftswerkstatt"),
    path("partner/", views.partner, name="partner"),
    path(
        "staatssimulation/",
        RedirectView.as_view(pattern_name="verfahren:zukunftswerkstatt", permanent=True),
        name="staatssimulation",
    ),
    path("umsetzung/", views.umsetzung, name="umsetzung"),
    path("umsetzung.json", views.umsetzung_json, name="umsetzung_json"),
    path("gesund/", views.gesund, name="gesund"),
]
