from django.urls import path

from . import views

app_name = "specimens"

urlpatterns = [
    path("taxa/", views.taxon_search, name="taxon_search"),
    path("taxa/manual/", views.taxon_manual_create, name="taxon_manual_create"),
    path("taxa/adopt-external/", views.taxon_adopt_external, name="taxon_adopt_external"),
    path("specimens/", views.specimen_list, name="list"),
    path("specimens/<uuid:detail_uuid>/", views.specimen_detail, name="detail"),
    path("specimens/<uuid:detail_uuid>/label.pdf", views.specimen_label_pdf, name="label_pdf"),
    path(
        "specimens/<uuid:detail_uuid>/qr-label.pdf",
        views.specimen_qr_label_pdf,
        name="qr_label_pdf",
    ),
    path("specimens/<uuid:detail_uuid>/edit/", views.specimen_edit, name="edit"),
    path("specimens/<uuid:detail_uuid>/events/", views.specimen_event, name="event"),
    path("specimens/<uuid:detail_uuid>/photos/add/", views.specimen_photo_add, name="photo_add"),
    path("q/<uuid:token>/", views.qr_resolve, name="qr_resolve"),
    path("q/<uuid:token>/register/", views.register, name="register"),
    path("q/<uuid:token>/register/confirm/", views.register_confirm, name="register_confirm"),
    path(
        "q/<uuid:token>/register/photos/<int:index>/", views.temporary_photo, name="temporary_photo"
    ),
    path("specimens/<uuid:detail_uuid>/photos/<int:photo_id>/", views.photo, name="photo"),
]
