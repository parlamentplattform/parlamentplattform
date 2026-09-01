from django.urls import path

from parameter import views

app_name = "parameter"
urlpatterns = [
    path("parameter/", views.liste, name="liste"),
    path("parameter.json", views.export_json, name="export"),
    path("verwaltung/parameter/", views.verwaltung, name="verwaltung"),
    path("verwaltung/parameter/aktion/", views.verwaltung_aktion, name="verwaltung_aktion"),
]
