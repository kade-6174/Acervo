"""Acervo全体のURL設定。"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("management/", include("management_portal.urls")),
    path("", include("core.urls")),
]
