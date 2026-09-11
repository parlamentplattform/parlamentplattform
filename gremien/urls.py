from django.urls import path

from gremien import views

app_name = "gremien"
urlpatterns = [
    path("gremien/", views.uebersicht, name="uebersicht"),
    path("gremien/mein/", views.mein, name="mein"),
    path("gremien/fachliste/", views.fachliste, name="fachliste"),
    path("gremien/auslosung/<int:antrag_id>/", views.auslosung, name="auslosung"),
    path("gremien/expertenrat/", views.expertenrat, name="expertenrat"),
    path("gremien/expertenrat/<int:antrag_id>/", views.fenster, name="fenster"),
    path("gremien/expertenrat/<int:antrag_id>/aktion/", views.fenster_aktion, name="fenster_aktion"),
    path("gremien/pruefung/", views.pruefung, name="pruefung"),
    path("gremien/beschluesse/", views.beschluesse_oeffentlich, name="beschluesse"),
    path("gremien/beschluss/<slug:nummer>/", views.beschluss_oeffentlich, name="beschluss"),
    path("gremien/beschluss/<int:beschluss_id>/stimme/", views.beschluss_stimme, name="beschluss_stimme"),
    path("gremien/integritaet/", views.integritaet, name="integritaet"),
    path("gremien/integritaet/beschluss/", views.integritaet_beschluss, name="integritaet_beschluss"),
    path("gremien/integritaet/regelpruefung/", views.integritaet_regelpruefung, name="integritaet_regelpruefung"),
    path("gremien/integritaet/aussetzung/<int:aussetzung_id>/schiedsgericht/", views.integritaet_schiedsgericht, name="integritaet_schiedsgericht"),
    path("gremien/koordination/", views.koordination, name="koordination"),
    path("gremien/koordination/beschluss/", views.koordination_beschluss, name="koordination_beschluss"),
    path("gremien/koordination/hinweis/<int:hinweis_id>/", views.koordination_hinweis, name="koordination_hinweis"),
    path("gremien/koordination/test/<int:test_id>/", views.koordination_test, name="koordination_test"),
    path("gremien/ueberlastung/melden/", views.ueberlastung_melden, name="ueberlastung_melden"),
    path("gremien/rat/<slug:gremium>/", views.rat, name="rat"),
    path("gremien/rat/<slug:gremium>/beschluss/", views.rat_beschluss, name="rat_beschluss"),
    path("gremien/beschluss/<int:beschluss_id>/umsetzung/", views.beschluss_umsetzung, name="beschluss_umsetzung"),
    path("gremien/protokoll/<slug:gremium>/<int:jahr>.json", views.protokoll, name="protokoll"),
    path("gremien/integritaet/bericht/<int:jahr>/", views.integritaet_bericht, name="integritaet_bericht"),
    path("verwaltung/rollen/", views.rollen, name="rollen"),
    path("verwaltung/rollen/aktion/", views.rollen_aktion, name="rollen_aktion"),
]
