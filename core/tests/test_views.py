from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User


class HomeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="home-user", cohort_number=33)

    def test_home_page_is_available(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acervo")
        self.assertContains(response, "QRコードを読み取る")
        self.assertContains(response, reverse("core:qr_scan"))
        self.assertContains(response, reverse("core:manifest"))
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css")
        self.assertContains(response, "/static/vendor/htmx/htmx.min.js")
        self.assertNotContains(response, "cdn.jsdelivr.net")

    @override_settings(ACERVO_SITE_NAME="標本管理テスト")
    def test_manifest_uses_configured_name_and_self_hosted_icons(self):
        response = self.client.get(reverse("core:manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertIn("no-store", response["Cache-Control"])
        manifest = response.json()
        self.assertEqual(manifest["name"], "標本管理テスト")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual([icon["sizes"] for icon in manifest["icons"]], ["192x192", "512x512"])
        self.assertTrue(all(icon["src"].startswith("/static/pwa/") for icon in manifest["icons"]))

    def test_service_worker_is_root_scoped_and_never_cached(self):
        response = self.client.get(reverse("core:service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn(b"STATIC_SET.has(url.pathname)", response.content)
        self.assertNotIn(b"cache.put(request", response.content)

    def test_scanner_requires_current_membership(self):
        url = reverse("core:qr_scan")
        self.assertRedirects(
            self.client.get(url),
            f"{reverse('account_login')}?next={url}",
            fetch_redirect_response=False,
        )
        self.user.cohort_number = 33
        self.user.save(update_fields=["cohort_number"])
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "カメラを起動")
        self.user.cohort_number = 30
        self.user.save(update_fields=["cohort_number"])
        self.assertEqual(self.client.get(url).status_code, 404)

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
