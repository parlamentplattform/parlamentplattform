from django.urls import path

from mitglieder import einfuehrung, verwaltung, views

app_name = "mitglieder"
urlpatterns = [
    path("mitglied-werden/", views.registrieren, name="registrieren"),
    path("bestaetigen/<str:token>/", views.bestaetigen, name="bestaetigen"),
    path("willkommen/", views.willkommen, name="willkommen"),
    path("einfuehrung/<int:schritt>/", einfuehrung.einfuehrung, name="einfuehrung"),
    path("anmelden/", views.login_anfordern, name="login"),
    path("anmelden/<str:token>/", views.login_einloesen, name="login_einloesen"),
    path("abmelden/", views.abmelden, name="abmelden"),
    path("verwaltung/", verwaltung.liste, name="verwaltung"),
    path("verwaltung/<int:pk>/", verwaltung.mitglied, name="verwaltung_mitglied"),
]
