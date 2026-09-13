from pathlib import Path

from allauth.account import app_settings
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Phase1BConfigurationTests(SimpleTestCase):
    def test_only_phase_1b_allauth_apps_are_enabled(self):
        self.assertIn("allauth", settings.INSTALLED_APPS)
        self.assertIn("allauth.account", settings.INSTALLED_APPS)
        self.assertNotIn("allauth.mfa", settings.INSTALLED_APPS)
        self.assertNotIn("allauth.socialaccount", settings.INSTALLED_APPS)

    def test_authentication_policy_is_explicit(self):
        self.assertEqual(settings.ACCOUNT_LOGIN_METHODS, {"username"})
        self.assertEqual(settings.ACCOUNT_SIGNUP_FIELDS, ["username*", "password1*"])
        self.assertEqual(settings.ACCOUNT_EMAIL_VERIFICATION, "none")
        self.assertFalse(settings.ACCOUNT_LOGIN_BY_CODE_ENABLED)
        self.assertFalse(settings.ACCOUNT_LOGOUT_ON_GET)
        self.assertEqual(
            settings.ALLAUTH_TRUSTED_CLIENT_IP_HEADER,
            "X-Acervo-Client-IP",
        )
        self.assertEqual(settings.ALLAUTH_TRUSTED_PROXY_COUNT, 0)
        self.assertEqual(
            settings.SESSION_ENGINE,
            "django.contrib.sessions.backends.db",
        )
        self.assertEqual(app_settings.RATE_LIMITS["login"], "30/m/ip")
        self.assertEqual(app_settings.RATE_LIMITS["login_failed"], "10/m/ip,5/300s/key")

    def test_email_reset_and_login_code_urls_are_not_exposed(self):
        for view_name in ("account_reset_password", "account_request_login_code"):
            with self.subTest(view_name=view_name), self.assertRaises(NoReverseMatch):
                reverse(view_name)

    def test_password_gate_middleware_order(self):
        authentication_index = settings.MIDDLEWARE.index(
            "django.contrib.auth.middleware.AuthenticationMiddleware"
        )
        allauth_index = settings.MIDDLEWARE.index("allauth.account.middleware.AccountMiddleware")
        gate_index = settings.MIDDLEWARE.index(
            "accounts.middleware.InitialPasswordChangeMiddleware"
        )

        self.assertLess(authentication_index, allauth_index)
        self.assertLess(allauth_index, gate_index)

    def test_caddy_uses_listener_specific_client_ip_trust(self):
        caddyfile = (PROJECT_ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")

        self.assertIn("servers :8080", caddyfile)
        self.assertIn("trusted_proxies static private_ranges", caddyfile)
        self.assertIn("trusted_proxies_strict", caddyfile)
        self.assertIn("client_ip_headers CF-Connecting-IP", caddyfile)
        self.assertEqual(caddyfile.count("header_up X-Acervo-Client-IP {client_ip}"), 2)

    def test_tunnel_listener_is_not_published_to_host(self):
        production_compose = (PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8")
        cloudflare_compose = (PROJECT_ROOT / "compose.cloudflare.yaml").read_text(encoding="utf-8")

        self.assertNotIn('"8080:8080"', production_compose)
        self.assertNotIn('"8080:8080"', cloudflare_compose)
