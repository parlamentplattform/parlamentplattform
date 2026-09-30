from django.urls import path

from mandatare import views, views_live

app_name = "mandatare"
urlpatterns = [
    path("mandatare/", views.liste, name="liste"),
    path("mandatare/mein/", views.mein, name="mein"),
    path("mandatare/mein/<int:pk>/", views.mein_mandat, name="mein_mandat"),
    path("mandatare/mein/aktion/", views.mein_aktion, name="mein_aktion"),
    path("mandatare/wahlvorschlag/<int:antrag_pk>.md", views.wahlvorschlag, name="wahlvorschlag"),
    path(
        "mandatare/vertrauensfrage/<int:antrag_pk>/stellungnahme/",
        views.stellungnahme,
        name="stellungnahme",
    ),
    path("mandatare/<int:pk>/", views.detail, name="detail"),
    path("mandatare/<int:pk>/foto", views.foto, name="foto"),
    path("mandatare/<int:pk>/rechenschaft/", views.rechenschaft_mandat, name="rechenschaft_mandat"),
    path("mandatare/<int:pk>/berichte/", views.berichte, name="berichte"),
    path("mandatare/<int:pk>/live/", views_live.live, name="live"),
    path("mandatare/<int:pk>/live/<int:sitzung_pk>/beitrag/", views_live.live_beitrag, name="live_beitrag"),
    path(
        "mandatare/<int:pk>/live/<int:sitzung_pk>/beitrag/<int:beitrag_pk>/",
        views_live.live_beitrag_aktion,
        name="live_beitrag_aktion",
    ),
    path("mandatare/<int:pk>/vertrauensfrage/", views.vertrauensfrage_stellen, name="vertrauensfrage_stellen"),
    path("live/", views_live.live_uebersicht, name="live_uebersicht"),
    path("vertrauensfragen/", views.vertrauensfragen, name="vertrauensfragen"),
    path("rechenschaft/", views.rechenschaft, name="rechenschaft"),
    path("rechenschaft.json", views.rechenschaft_json, name="rechenschaft_json"),
    path("verwaltung/mandatare/", views.verwaltung, name="verwaltung"),
    path("verwaltung/mandatare/aktion/", views.verwaltung_aktion, name="verwaltung_aktion"),
]
