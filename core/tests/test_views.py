from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_home_page_is_available(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acervo")
        self.assertContains(response, "開発基盤を準備しました")
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css")
        self.assertContains(response, "/static/vendor/htmx/htmx.min.js")
        self.assertNotContains(response, "cdn.jsdelivr.net")

    def test_health_check_includes_database(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
