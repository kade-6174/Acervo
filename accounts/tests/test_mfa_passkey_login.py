"""Step 4C のパスワードレス・パスキーログイン統合テスト。

WebAuthn の署名を作るブラウザ／認証器境界だけを mock する。view、form、
session、login、レート制限、MFA記録およびリダイレクトは実処理を通す。
"""

import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from allauth.account.utils import user_pk_to_url_str
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from fido2.utils import websafe_encode

from accounts.models import User


class PasskeyLoginTests(TestCase):
    password = "SecurePassword123!"
    client_ip = "198.51.100.210"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="passkey-user", password=self.password, cohort_number=31
        )
        self.other = User.objects.create_user(
            username="passkey-other", password=self.password, cohort_number=31
        )
        self.key = Authenticator.objects.create(
            user=self.user, type=Authenticator.Type.WEBAUTHN, data={"name": "passkey"}
        )

    def credential(self, user=None, value="credential-json"):
        user = user or self.user
        handle = websafe_encode(user_pk_to_url_str(user).encode("utf-8"))
        return {"id": value, "response": {"userHandle": handle}}

    def post_login(self, credential, *, client=None, next_url="", xff=""):
        client = client or self.client
        url = reverse("mfa_login_webauthn")
        if next_url:
            url = f"{url}?next={next_url}"
        return client.post(
            url,
            {"credential": json.dumps(credential) if isinstance(credential, dict) else credential},
            HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
            HTTP_X_FORWARDED_FOR=xff,
        )

    def webauthn_success(self, *, passwordless=True):
        stack = ExitStack()
        stack.enter_context(
            patch("allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True)
        )
        stack.enter_context(
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=self.key,
            )
        )
        stack.enter_context(
            patch.object(
                Authenticator,
                "wrap",
                return_value=SimpleNamespace(is_passwordless=passwordless),
            )
        )
        return stack

    def test_login_button_is_associated_with_webauthn_form(self):
        response = self.client.get(reverse("account_login"))
        html = response.content.decode()

        self.assertRegex(
            html,
            r'<button(?=[^>]*id="passkey_login")(?=[^>]*form="mfa_login")[^>]*>',
        )

    @override_settings(ALLOWED_HOSTS=["testserver", "attacker.example"])
    def test_request_options_use_fixed_rp_and_required_verification(self):
        url = reverse("mfa_login_webauthn")
        self.assertRedirects(
            self.client.get(url), reverse("account_login"), fetch_redirect_response=False
        )
        for host, forwarded_host in (
            ("attacker.example", "proxy.example"),
            ("testserver", "evil.example"),
        ):
            with self.subTest(host=host):
                response = self.client.get(
                    url,
                    HTTP_ACCEPT="application/json",
                    HTTP_HOST=host,
                    HTTP_X_FORWARDED_HOST=forwarded_host,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["request_options"]["publicKey"]["rpId"], "localhost"
                )
                self.assertEqual(
                    response.json()["request_options"]["publicKey"]["userVerification"],
                    "required",
                )
                self.assertIn("mfa.webauthn.state", self.client.session)
                self.assertIn("no-store", response.headers["Cache-Control"])
        self.client.force_login(self.user)
        self.assertNotEqual(self.client.get(url, HTTP_ACCEPT="application/json").status_code, 500)
        for name in ("mfa_signup_webauthn", "mfa_trust"):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)
        self.assertEqual(self.client.get("/accounts/mfa/webauthn/signup/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/mfa/trust/").status_code, 404)

    def test_passwordless_success_creates_session_records_mfa_and_skips_extra_stage(self):
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        recovery = RecoveryCodes.activate(self.user).instance
        safe_next = reverse("core:health")
        with self.webauthn_success():
            response = self.post_login(self.credential(), next_url=safe_next)
        self.assertRedirects(response, safe_next, fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
        method = self.client.session["account_authentication_methods"][-1]
        self.assertEqual(method["method"], "mfa")
        self.assertEqual(method["type"], "webauthn")
        self.assertTrue(method["passwordless"])
        self.assertNotIn("reauthenticated", method)
        self.assertNotIn("account_login", self.client.session)
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)
        recovery.refresh_from_db()
        self.assertEqual(recovery.data["used_mask"], 0)

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_credential_must_be_passwordless_and_failures_do_not_clear_or_leak(self):
        for passwordless in (False, None):
            with (
                self.subTest(passwordless=passwordless),
                self.webauthn_success(passwordless=passwordless),
            ):
                response = self.post_login(
                    self.credential(value=f"secret-{passwordless}"), xff="203.0.113.10"
                )
            self.assertRedirects(response, reverse("account_login"), fetch_redirect_response=False)
            page = self.client.get(response["Location"])
            self.assertContains(page, "パスキーまたはセキュリティキーを確認できませんでした。")
            self.assertNotContains(page, f"secret-{passwordless}")
            self.assertNotIn(f"secret-{passwordless}", repr(dict(self.client.session)))
            self.assertNotIn(SESSION_KEY, self.client.session)
            with self.webauthn_success(passwordless=passwordless):
                limited = self.post_login(self.credential(value=f"limited-{passwordless}"))
            limited_page = self.client.get(limited["Location"])
            self.assertContains(
                limited_page, "試行回数が多すぎます。しばらく待ってからもう一度お試しください。"
            )
            cache.clear()

    def test_user_state_userhandle_and_unsafe_next_are_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.webauthn_success():
            inactive = self.post_login(self.credential())
        self.assertRedirects(inactive, reverse("account_inactive"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        def reject_other_user(user, credential):
            if user != self.user:
                raise ValidationError("コードが正しくありません。", code="incorrect_code")
            return self.key

        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=reject_other_user,
            ),
            patch.object(Authenticator, "wrap", return_value=SimpleNamespace(is_passwordless=True)),
        ):
            foreign = self.post_login(self.credential(self.other))
        self.assertRedirects(foreign, reverse("account_login"), fetch_redirect_response=False)
        malformed = self.post_login("{")
        self.assertRedirects(malformed, reverse("account_login"), fetch_redirect_response=False)
        incomplete = self.post_login({"id": "incomplete"})
        self.assertRedirects(incomplete, reverse("account_login"), fetch_redirect_response=False)
        unknown_handle = websafe_encode(b"not-a-user")
        with patch(
            "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
        ):
            unknown = self.post_login({"id": "unknown", "response": {"userHandle": unknown_handle}})
        self.assertRedirects(unknown, reverse("account_login"), fetch_redirect_response=False)
        for unsafe in ("https://attacker.example/", "//attacker.example/"):
            with self.subTest(next=unsafe), self.webauthn_success():
                response = self.post_login(self.credential(), next_url=unsafe)
            self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
            self.client.post(reverse("account_logout"))

        must_change = User.objects.create_user(
            username="passkey-must-change",
            password=self.password,
            cohort_number=31,
            must_change_password=True,
        )
        key = Authenticator.objects.create(
            user=must_change, type=Authenticator.Type.WEBAUTHN, data={"name": "must-change"}
        )
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=key,
            ),
            patch.object(Authenticator, "wrap", return_value=SimpleNamespace(is_passwordless=True)),
        ):
            self.post_login(self.credential(must_change))
        self.assertEqual(int(self.client.session[SESSION_KEY]), must_change.pk)
        self.assertRedirects(
            self.client.get(reverse("core:home")),
            reverse("account_change_password"),
            fetch_redirect_response=False,
        )

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_rate_limit_uses_dedicated_ip_and_hides_credential(self):
        failing = ValidationError("認証コードを確認できませんでした。", code="incorrect_code")
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=failing,
            ),
        ):
            first = self.post_login(self.credential(value="first-secret"), xff="203.0.113.1")
            second = self.post_login(self.credential(value="second-secret"), xff="203.0.113.2")
        self.assertRedirects(first, reverse("account_login"), fetch_redirect_response=False)
        page = self.client.get(second["Location"])
        self.assertContains(
            page, "試行回数が多すぎます。しばらく待ってからもう一度お試しください。"
        )
        self.assertNotContains(page, "second-secret")
        self.assertNotIn("second-secret", repr(dict(self.client.session)))
        self.assertNotIn(SESSION_KEY, self.client.session)

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "2/m/ip"})
    def test_passwordless_success_clears_prior_failure_count(self):
        failing = ValidationError("認証コードを確認できませんでした。", code="incorrect_code")
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=failing,
            ),
        ):
            self.post_login(self.credential(value="failed-once"))
        with self.webauthn_success():
            self.post_login(self.credential())
        self.client.post(reverse("account_logout"))
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=failing,
            ),
        ):
            after_success = self.post_login(self.credential(value="after-success"))
        self.assertRedirects(after_success, reverse("account_login"), fetch_redirect_response=False)
        self.assertContains(
            self.client.get(after_success["Location"]),
            "パスキーまたはセキュリティキーを確認できませんでした。",
        )

    def test_existing_password_totp_recovery_and_webauthn_flows_remain_available(self):
        """Step 4Bの経路を壊さず、既存の専用テストと併せて回帰を固定する。"""
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        recovery = RecoveryCodes.activate(self.user)
        password_login = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
        )
        self.assertEqual(password_login.status_code, 302, password_login.content.decode())
        code = format_hotp_value(
            hotp_value("JBSWY3DPEHPK3PXP", next(yield_hotp_counters_from_time()))
        )
        completed = self.client.post(
            reverse("mfa_authenticate"), {"code": code}, HTTP_X_ACERVO_CLIENT_IP=self.client_ip
        )
        self.assertRedirects(completed, reverse("core:home"), fetch_redirect_response=False)
        self.client.post(reverse("account_logout"))
        password_login = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
        )
        self.assertRedirects(
            password_login, reverse("mfa_authenticate"), fetch_redirect_response=False
        )
        recovered = self.client.post(
            reverse("mfa_authenticate"),
            {"code": recovery.get_unused_codes()[0]},
            HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
        )
        self.assertRedirects(recovered, reverse("core:home"), fetch_redirect_response=False)
        self.client.post(reverse("account_logout"))
        password_login = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
        )
        self.assertRedirects(
            password_login, reverse("mfa_authenticate"), fetch_redirect_response=False
        )
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=self.key,
            ),
            patch.object(
                Authenticator, "wrap", return_value=SimpleNamespace(is_passwordless=False)
            ),
        ):
            second_factor = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": '{"id":"second-factor"}'},
                HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
            )
        self.assertRedirects(second_factor, reverse("core:home"), fetch_redirect_response=False)
        self.client.force_login(self.user)
        session = self.client.session
        session["account_authentication_methods"] = [{"method": "password", "at": 1_000_000_000}]
        session.save()
        reauth_url = f"{reverse('mfa_reauthenticate_webauthn')}?next={reverse('core:health')}"
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=self.key,
            ),
            patch.object(
                Authenticator, "wrap", return_value=SimpleNamespace(is_passwordless=False)
            ),
        ):
            reauthenticated = self.client.post(
                reauth_url,
                {"credential": '{"id":"reauth"}'},
                HTTP_X_ACERVO_CLIENT_IP=self.client_ip,
            )
        self.assertRedirects(reauthenticated, reverse("core:health"), fetch_redirect_response=False)
