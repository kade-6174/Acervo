from pathlib import Path

from allauth.account import app_settings
from allauth.core import context
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import NoReverseMatch, reverse

from accounts.adapters import AcervoMFAAdapter

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Phase1ConfigurationTests(SimpleTestCase):
    def test_only_supported_allauth_apps_are_enabled(self):
        self.assertIn("allauth", settings.INSTALLED_APPS)
        self.assertIn("allauth.account", settings.INSTALLED_APPS)
        self.assertIn("allauth.mfa", settings.INSTALLED_APPS)
        self.assertNotIn("allauth.socialaccount", settings.INSTALLED_APPS)

    def test_mfa_policy_is_explicit(self):
        self.assertEqual(
            settings.MFA_SUPPORTED_TYPES,
            ["recovery_codes", "totp"],
        )
        self.assertFalse(settings.MFA_PASSKEY_LOGIN_ENABLED)
        self.assertFalse(settings.MFA_PASSKEY_SIGNUP_ENABLED)
        self.assertEqual(settings.MFA_RECOVERY_CODE_COUNT, 10)
        self.assertTrue(settings.MFA_RECOVERY_CODES_SHOW_ONCE)
        self.assertFalse(settings.MFA_TRUST_ENABLED)
        self.assertEqual(settings.MFA_TOTP_ISSUER, "Acervo")
        self.assertFalse(settings.MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN)

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


class MFAKeyValidationTests(SimpleTestCase):
    VALID_KEY_1 = "0YFsuKhANUHwqSsmdjDwiT5GUQXzE7d1c5bUpFPJgy4="
    VALID_KEY_2 = "68HlXiUn1Ncg15LUJ9KreAQl6YpPtCV42ivaTBprlGs="
    INVALID_KEY = "not-a-valid-fernet-key-value"

    def test_valid_single_key(self):
        from accounts.security import validate_mfa_fernet_keys

        result = validate_mfa_fernet_keys(self.VALID_KEY_1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], self.VALID_KEY_1.encode("ascii"))

    def test_valid_multiple_keys_as_list_and_comma_string(self):
        from accounts.security import validate_mfa_fernet_keys

        result_list = validate_mfa_fernet_keys([self.VALID_KEY_1, self.VALID_KEY_2])
        self.assertEqual(len(result_list), 2)

        comma_str = f"{self.VALID_KEY_1},{self.VALID_KEY_2}"
        result_str = validate_mfa_fernet_keys(comma_str)
        self.assertEqual(len(result_str), 2)
        self.assertEqual(result_list, result_str)

    def test_missing_or_empty_keys_raise_error(self):
        from django.core.exceptions import ImproperlyConfigured

        from accounts.security import validate_mfa_fernet_keys

        for empty_val in (None, "", "   ", [], ["  "]):
            with self.subTest(empty_val=empty_val):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    validate_mfa_fernet_keys(empty_val)
                self.assertIn("ACERVO_MFA_FERNET_KEYS", str(ctx.exception))

    def test_invalid_key_raises_error_without_leaking_key(self):
        from django.core.exceptions import ImproperlyConfigured

        from accounts.security import validate_mfa_fernet_keys

        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_mfa_fernet_keys(self.INVALID_KEY)
        self.assertNotIn(self.INVALID_KEY, str(ctx.exception))
        self.assertIn("不正なFernet鍵", str(ctx.exception))

    def test_mixed_valid_and_invalid_keys_raise_error(self):
        from django.core.exceptions import ImproperlyConfigured

        from accounts.security import validate_mfa_fernet_keys

        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_mfa_fernet_keys([self.VALID_KEY_1, self.INVALID_KEY])
        self.assertNotIn(self.VALID_KEY_1, str(ctx.exception))
        self.assertNotIn(self.INVALID_KEY, str(ctx.exception))


class WebAuthnRPConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.adapter = AcervoMFAAdapter()
        self.request_factory = RequestFactory()

    @override_settings(ACERVO_PUBLIC_BASE_URL="https://PASSKEY.Example.ORG:8443/")
    def test_rp_id_comes_from_public_url_hostname_not_request_headers(self):
        direct_request = self.request_factory.get("/", HTTP_HOST="attacker.example.org")
        forwarded_request = self.request_factory.get(
            "/",
            HTTP_HOST="other.example.org",
            HTTP_X_FORWARDED_HOST="attacker.example.org",
            HTTP_X_FORWARDED_FOR="203.0.113.99",
        )

        for request in (direct_request, forwarded_request):
            with self.subTest(request=request.META):
                with context.request_context(request):
                    entity = self.adapter.get_public_key_credential_rp_entity()
                self.assertEqual(entity, {"id": "passkey.example.org", "name": "Acervo"})

    @override_settings(ACERVO_PUBLIC_BASE_URL="http://localhost:8000")
    def test_localhost_http_is_only_allowed_for_local_development(self):
        self.assertEqual(
            self.adapter.get_public_key_credential_rp_entity(),
            {"id": "localhost", "name": "Acervo"},
        )


class ProductionMFASettingsTests(SimpleTestCase):
    VALID_KEY = "0YFsuKhANUHwqSsmdjDwiT5GUQXzE7d1c5bUpFPJgy4="

    def _run_production_setup(self, extra_env=None):
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "DJANGO_SECRET_KEY": "a" * 64,
                "DJANGO_ALLOWED_HOSTS": "acervo.example.org",
                "POSTGRES_PASSWORD": "dummy-password",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://acervo.example.org",
                "ACERVO_PUBLIC_BASE_URL": "https://acervo.example.org",
                "ACERVO_MFA_FERNET_KEYS": self.VALID_KEY,
            }
        )
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_production_fails_when_fernet_keys_missing(self):
        result = self._run_production_setup({"ACERVO_MFA_FERNET_KEYS": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ACERVO_MFA_FERNET_KEYS", result.stderr)

    def test_production_fails_when_fernet_key_invalid(self):
        invalid_key = "invalid-fernet-key"
        result = self._run_production_setup({"ACERVO_MFA_FERNET_KEYS": invalid_key})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不正なFernet鍵", result.stderr)
        self.assertNotIn(invalid_key, result.stderr)

    def test_production_fails_when_insecure_origin_allowed(self):
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "DJANGO_SECRET_KEY": "a" * 64,
                "DJANGO_ALLOWED_HOSTS": "acervo.example.org",
                "POSTGRES_PASSWORD": "dummy-password",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://acervo.example.org",
                "ACERVO_PUBLIC_BASE_URL": "https://acervo.example.org",
                "ACERVO_MFA_FERNET_KEYS": self.VALID_KEY,
            }
        )
        script = (
            "import os\n"
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.production'\n"
            "from unittest.mock import patch\n"
            "from django.core.exceptions import ImproperlyConfigured\n"
            "with patch('config.settings.base.MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN', True):\n"
            "    try:\n"
            "        import config.settings.production\n"
            "    except ImproperlyConfigured as e:\n"
            "        assert 'MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN' in str(e)\n"
            "        print('SUCCESS_CAUGHT')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SUCCESS_CAUGHT", result.stdout)

    def test_production_succeeds_with_valid_fernet_key(self):
        result = self._run_production_setup()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_validates_public_origin_and_rp_id_boundary(self):
        invalid_cases = {
            "http://acervo.example.org": "httpsの公開URL",
            "https:///": "形式が不正",
            "https://user:password@acervo.example.org": "形式が不正",
            "https://acervo.example.org?query=value": "形式が不正",
            "https://acervo.example.org#fragment": "形式が不正",
            "https://acervo.example.org/subpath": "形式が不正",
            "https://192.0.2.10": "IPアドレス",
            "https://localhost": "localhost",
        }
        for public_url, message in invalid_cases.items():
            with self.subTest(public_url=public_url):
                result = self._run_production_setup({"ACERVO_PUBLIC_BASE_URL": public_url})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

        allowed_hosts_mismatch = self._run_production_setup(
            {"DJANGO_ALLOWED_HOSTS": "other.example.org"}
        )
        self.assertNotEqual(allowed_hosts_mismatch.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", allowed_hosts_mismatch.stderr)

        wildcard_only = self._run_production_setup({"DJANGO_ALLOWED_HOSTS": ".example.org"})
        self.assertNotEqual(wildcard_only.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", wildcard_only.stderr)

        csrf_mismatch = self._run_production_setup(
            {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://other.example.org"}
        )
        self.assertNotEqual(csrf_mismatch.returncode, 0)
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS", csrf_mismatch.stderr)

    def test_production_accepts_ported_public_origin_when_exactly_registered(self):
        result = self._run_production_setup(
            {
                "ACERVO_PUBLIC_BASE_URL": "https://acervo.example.org:8443",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://acervo.example.org:8443",
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
