from django.urls import path

from uebersicht import views

app_name = "uebersicht"
urlpatterns = [
    path("uebersicht/", views.index, name="index"),
]
