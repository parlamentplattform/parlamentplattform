from django.urls import path

from faktenbasis import verwaltung, views

app_name = "faktenbasis"
urlpatterns = [
    path("verwaltung/faktenbasis/", verwaltung.metadaten, name="verwaltung"),
    path("verwaltung/faktenbasis/norm/<int:pk>/dokumenttext/", verwaltung.dokumenttext, name="dokumenttext_abrufen"),
    path("zukunftswerkstatt/faktenbasis/", views.index, name="index"),
    path("zukunftswerkstatt/faktenbasis/personal/", views.personal, name="personal"),
    path("zukunftswerkstatt/faktenbasis/personal/<int:pk>/", views.personal_detail, name="personal_detail"),
    path("zukunftswerkstatt/faktenbasis/personal/<int:pk>/nachweis.json", views.personal_nachweis, name="personal_nachweis"),
    path("zukunftswerkstatt/faktenbasis/norm/<int:pk>/", views.norm, name="norm"),
    path("zukunftswerkstatt/faktenbasis/import/<int:pk>/antwort.json", views.importantwort, name="importantwort"),
    path("zukunftswerkstatt/faktenbasis/text/<int:pk>/original.xml", views.textxml, name="textxml"),
]
