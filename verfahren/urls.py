from django.urls import path

from verfahren import views

app_name = "verfahren"
urlpatterns = [
    path("", views.index, name="index"),
    path("antrag/<int:pk>/", views.antrag_detail, name="antrag"),
    path("gesund/", views.gesund, name="gesund"),
]
