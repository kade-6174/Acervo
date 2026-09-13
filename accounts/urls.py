from allauth.account import views
from django.urls import include, path

urlpatterns = [
    path("login/", views.login, name="account_login"),
    path("logout/", views.logout, name="account_logout"),
    path("inactive/", views.account_inactive, name="account_inactive"),
    path("signup/", views.signup, name="account_signup"),
    path("password/change/", views.password_change, name="account_change_password"),
    path("reauthenticate/", views.reauthenticate, name="account_reauthenticate"),
    path("mfa/", include("accounts.mfa_urls")),
]
