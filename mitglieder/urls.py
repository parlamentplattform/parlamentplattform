from django.urls import path

from mitglieder import beitraege_views, einfuehrung, profil, verwaltung, views

app_name = "mitglieder"
urlpatterns = [
    path("mitgliedschaft/", views.mitgliedschaft, name="mitgliedschaft"),
    path("mitglied-werden/", views.registrieren, name="registrieren"),
    path("bestaetigen/<str:token>/", views.bestaetigen, name="bestaetigen"),
    path("willkommen/", views.willkommen, name="willkommen"),
    path("einfuehrung/<int:schritt>/", einfuehrung.einfuehrung, name="einfuehrung"),
    path("anmelden/", views.login_anfordern, name="login"),
    path("anmelden/<str:token>/", views.login_einloesen, name="login_einloesen"),
    path("abmelden/", views.abmelden, name="abmelden"),
    path("beitrag/", beitraege_views.beitrag, name="beitrag"),
    path("beitrag/gemeldet/", beitraege_views.beitrag_gemeldet, name="beitrag_gemeldet"),
    path("profil/", profil.profil, name="profil"),
    path("profil/sitzungen-beenden/", profil.sitzungen_beenden, name="profil_sitzungen_beenden"),
    path("profil/export.json", profil.export_json, name="profil_export"),
    path("profil/austritt/", profil.austritt, name="profil_austritt"),
    path("verwaltung/", verwaltung.liste, name="verwaltung"),
    path("verwaltung/beitraege/", beitraege_views.verwaltung_beitraege, name="verwaltung_beitraege"),
    path("verwaltung/beitraege/erinnern/", beitraege_views.beitrag_erinnern, name="beitrag_erinnern"),
    path("verwaltung/beitraege/auszug/", beitraege_views.auszug_hochladen, name="auszug_hochladen"),
    path("verwaltung/beitraege/abgleichen/", beitraege_views.verwaltung_abgleichen, name="verwaltung_abgleichen"),
    path("verwaltung/bank/koppeln/", beitraege_views.bank_koppeln, name="bank_koppeln"),
    path("verwaltung/bank/rueckkehr/", beitraege_views.bank_rueckkehr, name="bank_rueckkehr"),
    path("verwaltung/<int:pk>/", verwaltung.mitglied, name="verwaltung_mitglied"),
    path("adresse/einspruch/<str:token>/", verwaltung.adresswechsel_einspruch, name="adresswechsel_einspruch"),
]
