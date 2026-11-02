from django.urls import path

from faktenbasis import views

app_name = "faktenbasis"
urlpatterns = [
    path("zukunftswerkstatt/faktenbasis/", views.index, name="index"),
    path("zukunftswerkstatt/faktenbasis/norm/<int:pk>/", views.norm, name="norm"),
    path("zukunftswerkstatt/faktenbasis/import/<int:pk>/antwort.json", views.importantwort, name="importantwort"),
]
