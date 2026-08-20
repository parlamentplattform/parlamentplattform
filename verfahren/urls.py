from django.urls import path

from verfahren import views, views_aktionen

app_name = "verfahren"
urlpatterns = [
    path("", views.index, name="index"),
    path("einbringen/", views_aktionen.einbringen, name="einbringen"),
    path("kategorien/", views_aktionen.kategorie_fokus, name="kategorien"),
    path(
        "kategorien/<slug:slug>/abonnieren/", views_aktionen.kategorie_abonnieren, name="kategorie_abonnieren"
    ),
    path("kategorien/<slug:slug>/", views_aktionen.kategorie_fokus, name="kategorie"),
    path("antrag/<int:pk>/", views.antrag_detail, name="antrag"),
    path("antrag/<int:pk>/unterstuetzen/", views_aktionen.unterstuetzen, name="unterstuetzen"),
    path("antrag/<int:pk>/favorisieren/", views_aktionen.favorisieren, name="favorisieren"),
    path("antrag/<int:pk>/kommentieren/", views_aktionen.kommentieren, name="kommentieren"),
    path("antrag/<int:pk>/abstimmen/", views_aktionen.abstimmen, name="abstimmen"),
    path("antrag/<int:pk>/export.json", views_aktionen.export_json, name="export"),
    path("antrag/<int:pk>/meine-stimme/", views_aktionen.eigene_stimme, name="eigene_stimme"),
    path("antrag/<int:pk>/vollzug/", views_aktionen.vollzug_eintragen, name="vollzug"),
    path("umsetzung/", views.umsetzung, name="umsetzung"),
    path("umsetzung.json", views.umsetzung_json, name="umsetzung_json"),
    path("gesund/", views.gesund, name="gesund"),
]
