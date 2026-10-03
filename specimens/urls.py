from django.urls import path

from . import views

app_name = "specimens"

urlpatterns = [
    path("q/<uuid:token>/", views.qr_resolve, name="qr_resolve"),
]
