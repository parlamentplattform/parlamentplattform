from django.urls import path

from anstoss import views

app_name = "anstoss"
urlpatterns = [
    path("anstoss/", views.senden, name="senden"),
    path("verwaltung/anstoesse/", views.verwaltung_liste, name="verwaltung"),
    path("verwaltung/anstoesse/<int:pk>/status/", views.status_setzen, name="status"),
    path("verwaltung/anstoesse/export.csv", views.export_csv, name="export_csv"),
    path("verwaltung/anstoesse/export.json", views.export_json, name="export_json"),
]
