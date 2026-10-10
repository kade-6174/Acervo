from django.urls import path

from . import views

app_name = "management"

urlpatterns = [
    path("", views.index, name="index"),
    path("audit-logs/", views.audit_log_list, name="audit_log_list"),
    path("specimens/export.csv", views.specimen_csv_export, name="specimen_csv_export"),
    path("storage-locations/", views.storage_location_list, name="storage_location_list"),
    path(
        "storage-locations/<int:location_id>/edit/",
        views.storage_location_edit,
        name="storage_location_edit",
    ),
    path(
        "storage-locations/<int:location_id>/delete/",
        views.storage_location_delete,
        name="storage_location_delete",
    ),
    path("site-settings/", views.site_settings, name="site_settings"),
    path("specimens/", views.specimen_management_list, name="specimen_management_list"),
    path(
        "specimens/<uuid:detail_uuid>/invalidate/",
        views.specimen_invalidate,
        name="specimen_invalidate",
    ),
    path(
        "specimens/<uuid:detail_uuid>/delete/",
        views.specimen_delete,
        name="specimen_delete",
    ),
    path("qr-batches/", views.qr_batch_list, name="qr_batch_list"),
    path("qr-batches/<int:batch_id>/labels.pdf", views.qr_batch_pdf, name="qr_batch_pdf"),
    path("qr-batches/<int:batch_id>/labels/", views.qr_batch_labels, name="qr_batch_labels"),
    path(
        "qr-batches/<int:batch_id>/labels/<int:label_id>/retire/",
        views.qr_label_retire,
        name="qr_label_retire",
    ),
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
