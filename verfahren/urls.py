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
    path("antrag/<int:pk>/archiv.<slug:art>", views.archiv_export, name="archiv_export"),
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
    path("antrag/<int:pk>/beanstanden/", views_aktionen.beanstanden, name="beanstanden"),
    # Der Chat eines Antrags (FB-G1, G2)
    path("antrag/<int:pk>/chat/gelesen/", views_aktionen.chat_gelesen, name="chat_gelesen"),
    path("antrag/<int:pk>/beitrag/<int:beitrag_pk>/bearbeiten/", views_aktionen.beitrag_bearbeiten, name="beitrag_bearbeiten"),
    path("antrag/<int:pk>/beitrag/<int:beitrag_pk>/entfernen/", views_aktionen.beitrag_entfernen, name="beitrag_entfernen"),
    path("antrag/<int:pk>/beitrag/<int:beitrag_pk>/reagieren/", views_aktionen.reagieren, name="reagieren"),
    path("antrag/<int:pk>/beitrag/<int:beitrag_pk>/melden/", views_aktionen.melden, name="melden"),
    # Meine Gespräche (FB-G3): eigene Seite; das Panel holt sich dieselbe Liste per htmx
    path("gespraeche/", views.gespraeche, name="gespraeche"),
    path("antrag/<int:pk>/meine-stimme/", views_aktionen.eigene_stimme, name="eigene_stimme"),
    path("antrag/<int:pk>/vollzug/", views_aktionen.vollzug_eintragen, name="vollzug"),
    path("filter/anwenden/", views_aktionen.filter_anwenden, name="filter_anwenden"),
    path("filter/<int:pk>/waehlen/", views_aktionen.filter_waehlen, name="filter_waehlen"),
    path("filter/<int:pk>/loeschen/", views_aktionen.filter_loeschen, name="filter_loeschen"),
    path("filter/neutral/", views_aktionen.filter_neutral, name="filter_neutral"),
    path("filter/vorschau/", views_aktionen.filter_vorschau, name="filter_vorschau"),
    path("filter/favoriten/", views_aktionen.filter_favoriten, name="filter_favoriten"),
    path("filter/<int:pk>/umbenennen/", views_aktionen.filter_umbenennen, name="filter_umbenennen"),
    path("zukunftswerkstatt/", views.zukunftswerkstatt, name="zukunftswerkstatt"),
    path("rollen/", views.rollen, name="rollen"),
    path("partner/", views.partner, name="partner"),
    path("partner/paket/", views.partner_paket, name="partner_paket"),
    path("partner/<slug:sprache>/", views.partner_kurz, name="partner_kurz"),
    path(
        "staatssimulation/",
        RedirectView.as_view(pattern_name="verfahren:zukunftswerkstatt", permanent=True),
        name="staatssimulation",
    ),
    path("umsetzung/", views.umsetzung, name="umsetzung"),
    path("umsetzung.json", views.umsetzung_json, name="umsetzung_json"),
    path("gesund/", views.gesund, name="gesund"),
]
