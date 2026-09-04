from django.urls import path

from gremien import views

app_name = "gremien"
urlpatterns = [
    path("gremien/", views.uebersicht, name="uebersicht"),
    path("gremien/mein/", views.mein, name="mein"),
    path("gremien/expertenrat/", views.expertenrat, name="expertenrat"),
    path("gremien/expertenrat/<int:antrag_id>/", views.fenster, name="fenster"),
    path("gremien/expertenrat/<int:antrag_id>/aktion/", views.fenster_aktion, name="fenster_aktion"),
    path("gremien/pruefung/", views.pruefung, name="pruefung"),
    path("gremien/beschluss/<int:beschluss_id>/stimme/", views.beschluss_stimme, name="beschluss_stimme"),
    path("gremien/koordination/", views.koordination, name="koordination"),
    path(
        "gremien/koordination/<int:pruefung_id>/aktion/",
        views.koordination_aktion,
        name="koordination_aktion",
    ),
    path("verwaltung/rollen/", views.rollen, name="rollen"),
    path("verwaltung/rollen/aktion/", views.rollen_aktion, name="rollen_aktion"),
]
