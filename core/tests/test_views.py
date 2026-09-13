from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class HomeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="home-user", cohort_number=31)

    def test_home_page_is_available(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acervo")
        self.assertContains(response, "開発基盤を準備しました")
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css")
        self.assertContains(response, "/static/vendor/htmx/htmx.min.js")
        self.assertNotContains(response, "cdn.jsdelivr.net")

    def test_home_page_requires_login(self):
        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:home')}",
            fetch_redirect_response=False,
        )

    def test_health_check_includes_database(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
