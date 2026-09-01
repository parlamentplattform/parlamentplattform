from django.urls import path

from mandatare import views

app_name = "mandatare"
urlpatterns = [
    path("mandatare/", views.liste, name="liste"),
    path("mandatare/<int:pk>/", views.detail, name="detail"),
    path("mandatare/<int:pk>/foto", views.foto, name="foto"),
    path("verwaltung/mandatare/", views.verwaltung, name="verwaltung"),
    path("verwaltung/mandatare/aktion/", views.verwaltung_aktion, name="verwaltung_aktion"),
]
