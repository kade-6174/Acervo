"""Step 5Cのallauth認証フローと管理者MFAゲートの統合テスト。"""

import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from fido2.utils import websafe_encode

from accounts.models import User

CLIENT_IP_HEADER = {"HTTP_X_ACERVO_CLIENT_IP": "198.51.100.230"}


class ManagementFlowIntegrationTests(TestCase):
    password = "SecurePassword123!"
    totp_secret = "JBSWY3DPEHPK3PXP"

    def setUp(self):
        cache.clear()

    def create_user(self, username, **extra_fields):
        return User.objects.create_user(
            username=username,
            password=self.password,
            cohort_number=extra_fields.pop("cohort_number", 31),
            **extra_fields,
        )

    def start_password_login(self, user, *, client=None, next_url="/management/"):
        client = client or self.client
        return client.post(
            f"{reverse('account_login')}?next={next_url}",
            {"login": user.username, "password": self.password},
            **CLIENT_IP_HEADER,
        )

    @staticmethod
    def valid_totp(secret):
        return format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))

    @staticmethod
    def invalid_totp(secret):
        valid_codes = {
            format_hotp_value(hotp_value(secret, counter))
            for counter in yield_hotp_counters_from_time()
        }
        for value in range(1_000_000):
            candidate = f"{value:06d}"
            if candidate not in valid_codes:
                return candidate
        raise AssertionError("無効なTOTPを生成できませんでした。")

    def complete_totp_login(self, user, *, client=None):
        client = client or self.client
        response = self.start_password_login(user, client=client)
        self.assertRedirects(
            response,
            reverse("mfa_authenticate"),
            fetch_redirect_response=False,
        )
        response = client.post(
            reverse("mfa_authenticate"),
            {"code": self.valid_totp(self.totp_secret)},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(
            response,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        return response

    def create_totp_admin(self, username, **extra_fields):
        admin = self.create_user(username, role=User.Role.ADMIN, **extra_fields)
        TOTP.activate(admin, self.totp_secret)
        return admin

    @staticmethod
    def credential(user, value="credential-json"):
        handle = websafe_encode(user_pk_to_url_str(user).encode("utf-8"))
        return {"id": value, "response": {"userHandle": handle}}

    @staticmethod
    def webauthn_success(key, *, passwordless):
        stack = ExitStack()
        stack.enter_context(
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[])
        )
        stack.enter_context(
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response",
                autospec=True,
            )
        )
        stack.enter_context(
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=key,
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

    def assert_management_allowed(self, client=None):
        client = client or self.client
        response = client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        return response

    def test_password_and_totp_login_reaches_management_without_extra_loop(self):
        admin = self.create_totp_admin("totp-admin")

        self.complete_totp_login(admin)

        self.assertEqual(int(self.client.session[SESSION_KEY]), admin.pk)
        self.assert_management_allowed()
        methods = self.client.session["account_authentication_methods"]
        self.assertEqual([method["method"] for method in methods], ["password", "mfa"])

    def test_recovery_code_login_reaches_management_consumes_once_and_does_not_leak(self):
        admin = self.create_totp_admin("recovery-admin")
        recovery = RecoveryCodes.activate(admin)
        code = recovery.get_unused_codes()[0]
        self.start_password_login(admin)

        completed = self.client.post(
            reverse("mfa_authenticate"),
            {"code": code},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(
            completed,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assert_management_allowed()
        recovery.instance.refresh_from_db()
        self.assertEqual(len(RecoveryCodes(recovery.instance).get_unused_codes()), 9)
        self.assertNotIn(code, completed.content.decode())
        self.assertNotIn(code, repr(dict(self.client.session)))
        self.assertNotIn(self.password, repr(dict(self.client.session)))

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.start_password_login(admin)
        reused = self.client.post(
            reverse("mfa_authenticate"),
            {"code": code},
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(reused.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotContains(reused, code)
        self.assertNotEqual(
            self.client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

    def test_recovery_only_admin_is_not_primary_mfa_configured(self):
        admin = self.create_user("recovery-only-admin", role=User.Role.ADMIN)
        RecoveryCodes.activate(admin)

        logged_in = self.start_password_login(admin)

        self.assertRedirects(
            logged_in,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        denied = self.client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        self.assertRedirects(denied, reverse("mfa_index"), fetch_redirect_response=False)
        self.assertIn("no-store", denied.headers["Cache-Control"])

    def test_password_stage_failure_cancel_and_rate_limit_never_reach_management(self):
        admin = self.create_totp_admin("failed-mfa-admin")
        invalid = self.invalid_totp(self.totp_secret)
        self.start_password_login(admin)

        failed = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(failed.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotContains(failed, invalid)
        self.assertNotIn(invalid, repr(dict(self.client.session)))
        self.assertNotEqual(
            self.client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

        cancelled = self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertRedirects(cancelled, reverse("account_login"), fetch_redirect_response=False)
        self.assertNotIn("account_login", self.client.session)

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_mfa_rate_limit_keeps_admin_unauthenticated(self):
        admin = self.create_totp_admin("limited-mfa-admin")
        invalid = self.invalid_totp(self.totp_secret)
        self.start_password_login(admin)
        self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            **CLIENT_IP_HEADER,
        )

        limited = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(limited.status_code, 200)
        self.assertContains(
            limited,
            "試行回数が多すぎます。しばらく待ってからもう一度お試しください。",
        )
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotContains(limited, invalid)
        self.assertNotEqual(
            self.client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

    def test_passwordless_passkey_login_reaches_management_without_extra_mfa(self):
        admin = self.create_user("passkey-admin", role=User.Role.ADMIN)
        key = Authenticator.objects.create(
            user=admin,
            type=Authenticator.Type.WEBAUTHN,
            data={"name": "management-passkey"},
        )
        credential = json.dumps(self.credential(admin))

        with self.webauthn_success(key, passwordless=True):
            completed = self.client.post(
                f"{reverse('mfa_login_webauthn')}?next={reverse('management:index')}",
                {"credential": credential},
                **CLIENT_IP_HEADER,
            )

        self.assertRedirects(
            completed,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assert_management_allowed()
        method = self.client.session["account_authentication_methods"][-1]
        self.assertEqual(method["type"], Authenticator.Type.WEBAUTHN)
        self.assertTrue(method["passwordless"])

    def test_password_and_webauthn_second_factor_reaches_management(self):
        admin = self.create_user("webauthn-second-factor-admin", role=User.Role.ADMIN)
        key = Authenticator.objects.create(
            user=admin,
            type=Authenticator.Type.WEBAUTHN,
            data={"name": "second-factor-passkey"},
        )
        started = self.start_password_login(admin)
        self.assertRedirects(
            started,
            reverse("mfa_authenticate"),
            fetch_redirect_response=False,
        )

        with self.webauthn_success(key, passwordless=False):
            completed = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": '{"id":"second-factor"}'},
                **CLIENT_IP_HEADER,
            )

        self.assertRedirects(
            completed,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assert_management_allowed()
        method = self.client.session["account_authentication_methods"][-1]
        self.assertEqual(method["type"], Authenticator.Type.WEBAUTHN)
        self.assertNotIn("passwordless", method)

    def test_password_only_session_with_primary_mfa_is_denied_until_reauthenticated(self):
        admin = self.create_totp_admin("password-only-admin")

        started = self.start_password_login(admin)

        self.assertRedirects(
            started,
            reverse("mfa_authenticate"),
            fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)
        denied = self.client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        self.assertRedirects(
            denied,
            f"{reverse('account_login')}?next=%2Fmanagement%2F",
            fetch_redirect_response=False,
        )

    def test_totp_and_webauthn_reauthentication_return_to_management_with_get(self):
        totp_admin = self.create_totp_admin("totp-reauth-admin")
        self.client.force_login(totp_admin)
        denied = self.client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        completed = self.client.post(
            denied.headers["Location"],
            {"code": self.valid_totp(self.totp_secret)},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(
            completed,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assert_management_allowed()

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        webauthn_admin = self.create_user("webauthn-reauth-admin", role=User.Role.ADMIN)
        key = Authenticator.objects.create(
            user=webauthn_admin,
            type=Authenticator.Type.WEBAUTHN,
            data={"name": "reauth-passkey"},
        )
        self.client.force_login(webauthn_admin)
        denied = self.client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        self.assertTrue(
            denied.headers["Location"].startswith(reverse("mfa_reauthenticate_webauthn"))
        )
        with self.webauthn_success(key, passwordless=False):
            completed = self.client.post(
                denied.headers["Location"],
                {"credential": '{"id":"reauth"}'},
                **CLIENT_IP_HEADER,
            )
        self.assertRedirects(
            completed,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assert_management_allowed()

    def test_logout_new_session_and_cookie_loss_cannot_reuse_mfa_record(self):
        admin = self.create_totp_admin("session-lifecycle-admin")
        cookie_admin = self.create_totp_admin("cookie-loss-admin")
        self.complete_totp_login(cookie_admin)
        self.assert_management_allowed()

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertNotEqual(
            self.client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

        fresh_client = Client()
        self.assertNotEqual(
            fresh_client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

        self.complete_totp_login(admin)
        self.client.cookies.clear()
        self.assertNotEqual(
            self.client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
            200,
        )

    def test_database_changes_take_effect_on_the_next_request(self):
        scenarios = (
            ("demoted", {"role": User.Role.MEMBER}, None),
            ("inactive", {"is_active": False}, None),
            (
                "password-change",
                {"must_change_password": True},
                reverse("account_change_password"),
            ),
            ("primary-removed", {}, reverse("mfa_index")),
        )
        for label, changes, expected_location in scenarios:
            with self.subTest(label=label):
                client = Client()
                admin = self.create_totp_admin(f"dynamic-{label}")
                self.complete_totp_login(admin, client=client)
                self.assert_management_allowed(client)
                if label == "primary-removed":
                    Authenticator.objects.filter(
                        user=admin,
                        type=Authenticator.Type.TOTP,
                    ).delete()
                else:
                    User.objects.filter(pk=admin.pk).update(**changes)

                response = client.get(reverse("management:index"), **CLIENT_IP_HEADER)

                self.assertNotEqual(response.status_code, 200)
                if expected_location:
                    self.assertEqual(response.headers["Location"], expected_location)
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_member_variants_are_denied_and_graduate_admin_policy_is_unchanged(self):
        members = (
            self.create_user("staff-member", is_staff=True),
            self.create_user("superuser-member", is_staff=True, is_superuser=True),
            self.create_user("graduate-member", cohort_number=30),
        )
        for member in members:
            with self.subTest(username=member.username):
                client = Client()
                logged_in = self.start_password_login(member, client=client)
                self.assertRedirects(
                    logged_in,
                    reverse("management:index"),
                    fetch_redirect_response=False,
                )
                self.assertEqual(
                    client.get(reverse("management:index"), **CLIENT_IP_HEADER).status_code,
                    403,
                )

        graduate_admin = self.create_totp_admin("graduate-admin", cohort_number=30)
        self.complete_totp_login(graduate_admin)
        self.assert_management_allowed()

    def test_missing_reauthentication_method_fails_closed_without_500(self):
        admin = self.create_totp_admin("missing-reauth-method-admin")
        self.client.force_login(admin)
        adapter = Mock()
        adapter.get_reauthentication_methods.return_value = [
            {"id": "reauthenticate", "url": reverse("account_reauthenticate")},
            {"unexpected": "value"},
        ]

        with patch("management_portal.middleware.get_adapter", return_value=adapter):
            response = self.client.post(
                "/management/?next=//attacker.example/",
                {"password": "must-not-be-saved", "code": "must-not-be-saved"},
                **CLIENT_IP_HEADER,
            )

        self.assertRedirects(response, reverse("mfa_index"), fetch_redirect_response=False)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("must-not-be-saved", repr(dict(self.client.session)))
        guidance = self.client.get(reverse("mfa_index"), **CLIENT_IP_HEADER)
        self.assertContains(
            guidance,
            "管理機能を利用するには、パスキーまたはTOTPで再認証してください。",
        )
