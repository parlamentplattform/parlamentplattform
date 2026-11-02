from django.urls import path

from faktenbasis import verwaltung, views

app_name = "faktenbasis"
urlpatterns = [
    path("verwaltung/faktenbasis/", verwaltung.metadaten, name="verwaltung"),
    path("verwaltung/faktenbasis/norm/<int:pk>/dokumenttext/", verwaltung.dokumenttext, name="dokumenttext_abrufen"),
    path("zukunftswerkstatt/faktenbasis/", views.index, name="index"),
    path("zukunftswerkstatt/faktenbasis/norm/<int:pk>/", views.norm, name="norm"),
    path("zukunftswerkstatt/faktenbasis/import/<int:pk>/antwort.json", views.importantwort, name="importantwort"),
    path("zukunftswerkstatt/faktenbasis/text/<int:pk>/original.xml", views.textxml, name="textxml"),
]
