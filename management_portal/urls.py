from django.urls import path

from . import views

app_name = "management"

urlpatterns = [
    path("", views.index, name="index"),
    path("audit-logs/", views.audit_log_list, name="audit_log_list"),
    path("specimens/export.csv", views.specimen_csv_export, name="specimen_csv_export"),
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:user_id>/", views.user_edit, name="user_edit"),
    path(
        "users/<int:user_id>/password-reissue/",
        views.user_password_reissue,
        name="user_password_reissue",
    ),
    path("mfa-reset/", views.mfa_reset_search, name="mfa_reset_search"),
    path(
        "users/<int:user_id>/mfa-reset/",
        views.mfa_reset_confirm,
        name="mfa_reset_confirm",
    ),
]
