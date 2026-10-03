from django.urls import path

from . import views

app_name = "specimens"

urlpatterns = [
    path("q/<uuid:token>/", views.qr_resolve, name="qr_resolve"),
    path("q/<uuid:token>/register/", views.register, name="register"),
    path("q/<uuid:token>/register/confirm/", views.register_confirm, name="register_confirm"),
    path(
        "q/<uuid:token>/register/photos/<int:index>/", views.temporary_photo, name="temporary_photo"
    ),
    path("specimens/<uuid:detail_uuid>/photos/<int:photo_id>/", views.photo, name="photo"),
]
