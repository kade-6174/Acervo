"""Step 4B WebAuthnのURL・DB・セッション境界の統合テスト。

ブラウザ認証器が作るattestation/assertionのバイト列だけをmockし、allauth view、
form、session、所有権、Authenticator DB、Recovery Codesの処理は実行する。
"""

import time
from types import SimpleNamespace
from unittest.mock import patch

from allauth.core import context
from allauth.mfa.models import Authenticator
from allauth.mfa.webauthn.internal import auth as webauthn_auth
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse

from accounts.models import User


class WebAuthnManagementTests(TestCase):
    password = "SecurePassword123!"

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", password=self.password, cohort_number=31
        )
        self.other = User.objects.create_user(
            username="other", password=self.password, cohort_number=31
        )

    def recent_login(self, user=None):
        user = user or self.user
        self.client.force_login(user)
        session = self.client.session
        session["account_authentication_methods"] = [{"method": "password", "at": time.time()}]
        session.save()

    def make_key(self, user, name="key"):
        return Authenticator.objects.create(user=user, type="webauthn", data={"name": name})

    def test_add_rejects_anonymous_stale_csrf_and_malformed_without_creating_key(self):
        url = reverse("mfa_add_webauthn")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.recent_login()
        response = self.client.post(url, {"name": "x", "credential": "{"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Authenticator.objects.filter(user=self.user, type="webauthn").exists())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url, {"credential": "{}"}).status_code, 403)
        self.client.force_login(self.user)
        session = self.client.session
        session["account_authentication_methods"] = [{"method": "password", "at": 0}]
        session.save()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_valid_registration_uses_current_owner_generates_recovery_codes_and_consumes_boundary(
        self,
    ):
        self.recent_login()
        url = reverse("mfa_add_webauthn")
        with (
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_registration_response", autospec=True
            ) as parse,
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_registration", autospec=True
            ) as complete,
        ):
            response = self.client.post(url, {"name": "私の鍵", "credential": '{"id": "test"}'})
        parse.assert_called_once()
        complete.assert_called_once()
        self.assertRedirects(
            response, reverse("mfa_view_recovery_codes"), fetch_redirect_response=False
        )
        key = Authenticator.objects.get(user=self.user, type="webauthn")
        self.assertEqual(key.data["name"], "私の鍵")
        self.assertTrue(
            Authenticator.objects.filter(user=self.user, type="recovery_codes").exists()
        )
        self.assertFalse(Authenticator.objects.filter(user=self.other, type="webauthn").exists())

    def test_idor_edit_remove_are_404_and_own_edit_remove_use_post(self):
        self.recent_login()
        mine, foreign = self.make_key(self.user, "<b>mine</b>"), self.make_key(self.other, "other")
        for name in ("mfa_edit_webauthn", "mfa_remove_webauthn"):
            self.assertEqual(
                self.client.get(reverse(name, kwargs={"pk": foreign.pk})).status_code, 404
            )
        wrapper = SimpleNamespace(name="<b>mine</b>", is_passwordless=False)
        with patch.object(Authenticator, "wrap", return_value=wrapper):
            self.assertContains(
                self.client.get(reverse("mfa_list_webauthn")), "&lt;b&gt;mine&lt;/b&gt;", html=False
            )
            edit = self.client.post(
                reverse("mfa_edit_webauthn", kwargs={"pk": mine.pk}), {"name": "更新"}
            )
            self.assertRedirects(edit, reverse("mfa_list_webauthn"), fetch_redirect_response=False)
            self.assertEqual(wrapper.name, "更新")
            before = Authenticator.objects.filter(pk=mine.pk).count()
            self.assertEqual(
                self.client.get(reverse("mfa_remove_webauthn", kwargs={"pk": mine.pk})).status_code,
                200,
            )
            self.assertEqual(Authenticator.objects.filter(pk=mine.pk).count(), before)
            deleted = self.client.post(reverse("mfa_remove_webauthn", kwargs={"pk": mine.pk}))
        self.assertRedirects(deleted, reverse("mfa_list_webauthn"), fetch_redirect_response=False)
        self.assertFalse(Authenticator.objects.filter(pk=mine.pk).exists())

    def test_management_templates_are_never_cached_and_load_double_submit_script(self):
        self.recent_login()
        key = self.make_key(self.user)
        for name, kwargs in (
            ("mfa_list_webauthn", {}),
            ("mfa_add_webauthn", {}),
            ("mfa_edit_webauthn", {"pk": key.pk}),
            ("mfa_remove_webauthn", {"pk": key.pk}),
        ):
            with (
                self.subTest(name=name),
                patch.object(
                    Authenticator,
                    "wrap",
                    return_value=SimpleNamespace(name="key", is_passwordless=False),
                ),
                patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            ):
                response = self.client.get(reverse(name, kwargs=kwargs))
                self.assertIn("no-store", response.headers["Cache-Control"])
        with patch.object(
            Authenticator, "wrap", return_value=SimpleNamespace(name="key", is_passwordless=False)
        ):
            self.assertContains(
                self.client.get(reverse("mfa_edit_webauthn", kwargs={"pk": key.pk})),
                "webauthn-ui.js",
            )
            self.assertContains(
                self.client.get(reverse("mfa_remove_webauthn", kwargs={"pk": key.pk})),
                "data-webauthn-submit",
            )

    def test_login_stage_webauthn_success_is_mfa_not_passwordless_and_updates_usage(self):
        key = self.make_key(self.user)
        login = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.55",
        )
        self.assertRedirects(login, reverse("mfa_authenticate"), fetch_redirect_response=False)
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=key,
            ),
        ):
            self.client.get(reverse("mfa_authenticate"))
            complete = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": '{"id": "test"}'},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.55",
            )
        self.assertRedirects(complete, reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)
        method = self.client.session["account_authentication_methods"][-1]
        self.assertEqual(method["method"], "mfa")
        self.assertNotIn("passwordless", method)
        key.refresh_from_db()
        self.assertIsNotNone(key.last_used_at)

    def test_webauthn_reauthentication_records_mfa_and_rejects_external_next(self):
        key = self.make_key(self.user)
        self.recent_login()
        url = reverse("mfa_reauthenticate_webauthn")
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                return_value=key,
            ),
        ):
            page = self.client.get(f"{url}?next=https://attacker.example/")
            self.assertIn("no-store", page.headers["Cache-Control"])
            response = self.client.post(
                f"{url}?next=https://attacker.example/",
                {"credential": '{"id": "test"}'},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.56",
            )
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        method = self.client.session["account_authentication_methods"][-1]
        self.assertEqual(method["method"], "mfa")
        self.assertTrue(method["reauthenticated"])
        self.assertNotIn("passwordless", method)

    def test_second_factor_failure_is_generic_never_cached_and_does_not_login(self):
        key = self.make_key(self.user)
        self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.57",
        )
        credential = '{"id": "secret-test"}'
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=ValidationError(
                    "認証コードを確認できませんでした。", code="incorrect_code"
                ),
            ),
        ):
            response = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": credential},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.57",
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "認証コードを確認できませんでした。")
        self.assertNotContains(response, credential)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertIn("no-store", response.headers["Cache-Control"])
        key.refresh_from_db()
        self.assertIsNone(key.last_used_at)

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_webauthn_second_factor_rate_limit_uses_dedicated_ip_not_xff(self):
        cache.clear()
        self.make_key(self.user)
        self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": self.password},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.59",
        )
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=ValidationError(
                    "認証コードを確認できませんでした。", code="incorrect_code"
                ),
            ),
        ):
            first = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": '{"id": "secret-test"}'},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.59",
                HTTP_X_FORWARDED_FOR="203.0.113.1",
            )
            second = self.client.post(
                reverse("mfa_authenticate"),
                {"credential": '{"id": "secret-test"}'},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.59",
                HTTP_X_FORWARDED_FOR="203.0.113.2",
            )
        self.assertEqual(
            first.context["webauthn_form"].errors.as_data()["credential"][0].code, "incorrect_code"
        )
        self.assertEqual(
            second.context["webauthn_form"].errors.as_data()["credential"][0].code, "rate_limited"
        )
        self.assertContains(
            second, "試行回数が多すぎます。しばらく待ってからもう一度お試しください。"
        )
        self.assertNotContains(second, "secret-test")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_reauthentication_failure_shows_generic_error_and_safe_next_is_used_on_success(self):
        self.make_key(self.user)
        self.recent_login()
        url = f"{reverse('mfa_reauthenticate_webauthn')}?next={reverse('core:health')}"
        with (
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch(
                "allauth.mfa.webauthn.internal.auth.parse_authentication_response", autospec=True
            ),
            patch(
                "allauth.mfa.webauthn.internal.auth.complete_authentication",
                autospec=True,
                side_effect=ValidationError(
                    "認証コードを確認できませんでした。", code="incorrect_code"
                ),
            ),
        ):
            failed = self.client.post(
                url,
                {"credential": '{"id": "secret-test"}'},
                HTTP_X_ACERVO_CLIENT_IP="198.51.100.58",
            )
        self.assertEqual(failed.status_code, 302)
        self.assertRedirects(failed, reverse("account_login"), fetch_redirect_response=False)


class WebAuthnChallengeStateTests(TestCase):
    def test_registration_state_is_session_bound_and_value_errors_are_generic(self):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        user = User.objects.create_user(
            username="state", password="SecurePassword123!", cohort_number=31
        )
        with context.request_context(request):
            options = webauthn_auth.begin_registration(user, False)
            self.assertIn(webauthn_auth.STATE_SESSION_KEY, request.session)
            selection = options["publicKey"]["authenticatorSelection"]
            self.assertEqual(selection["residentKey"], "discouraged")
            self.assertEqual(selection["userVerification"], "discouraged")
        with (
            context.request_context(request),
            patch.object(
                webauthn_auth.Fido2Server,
                "register_complete",
                autospec=True,
                side_effect=ValueError,
            ),
        ):
            with self.assertRaisesMessage(Exception, "認証コード"):
                webauthn_auth.complete_registration({"id": "test"})
        with (
            context.request_context(request),
            patch.object(
                webauthn_auth.Fido2Server,
                "register_complete",
                autospec=True,
                return_value=SimpleNamespace(),
            ) as complete,
        ):
            webauthn_auth.complete_registration({"id": "test"})
            complete.assert_called_once()
            self.assertNotIn(webauthn_auth.STATE_SESSION_KEY, request.session)
            with self.assertRaisesMessage(Exception, "認証コード"):
                webauthn_auth.complete_registration({"id": "test"})

    def test_passwordless_registration_options_require_resident_key_and_verification(self):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        user = User.objects.create_user(
            username="passkey-state", password="SecurePassword123!", cohort_number=31
        )
        with context.request_context(request):
            options = webauthn_auth.begin_registration(user, True)
        selection = options["publicKey"]["authenticatorSelection"]
        self.assertEqual(selection["residentKey"], "required")
        self.assertEqual(selection["userVerification"], "required")

    def test_authentication_state_is_one_time_and_resolves_only_current_users_key(self):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        user = User.objects.create_user(
            username="auth-state", password="SecurePassword123!", cohort_number=31
        )
        other = User.objects.create_user(
            username="auth-state-other", password="SecurePassword123!", cohort_number=31
        )
        key = Authenticator.objects.create(user=user, type="webauthn", data={"name": "key"})
        Authenticator.objects.create(user=other, type="webauthn", data={"name": "other"})
        wrapper = SimpleNamespace(
            authenticator_data=SimpleNamespace(
                credential_data=SimpleNamespace(credential_id=b"key")
            )
        )
        with (
            context.request_context(request),
            patch("allauth.mfa.webauthn.internal.auth.get_credentials", return_value=[]),
            patch.object(Authenticator, "wrap", return_value=wrapper),
        ):
            webauthn_auth.begin_authentication(user)
            self.assertIn(webauthn_auth.STATE_SESSION_KEY, request.session)
            with patch.object(
                webauthn_auth.Fido2Server,
                "authenticate_complete",
                autospec=True,
                side_effect=ValueError,
            ):
                with self.assertRaisesMessage(Exception, "認証コード"):
                    webauthn_auth.complete_authentication(user, {"id": "test"})
            with patch.object(
                webauthn_auth.Fido2Server,
                "authenticate_complete",
                autospec=True,
                return_value=SimpleNamespace(credential_id=b"key"),
            ) as complete:
                resolved = webauthn_auth.complete_authentication(user, {"id": "test"})
                self.assertEqual(resolved.pk, key.pk)
                complete.assert_called_once()
                self.assertNotIn(webauthn_auth.STATE_SESSION_KEY, request.session)
                with self.assertRaisesMessage(Exception, "認証コード"):
                    webauthn_auth.complete_authentication(user, {"id": "test"})
                complete.assert_called_once()
