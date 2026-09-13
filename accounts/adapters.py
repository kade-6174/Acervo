from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class AcervoAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

    def get_password_change_redirect_url(self, request):
        return reverse("core:home")
