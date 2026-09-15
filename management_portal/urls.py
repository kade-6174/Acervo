from django.urls import path

from . import views

app_name = "management"

urlpatterns = [
    path("", views.index, name="index"),
    path("mfa-reset/", views.mfa_reset_search, name="mfa_reset_search"),
    path(
        "users/<int:user_id>/mfa-reset/",
        views.mfa_reset_confirm,
        name="mfa_reset_confirm",
    ),
]
