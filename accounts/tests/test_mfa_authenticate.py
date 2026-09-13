"""Phase 1C Sub-step 3Dのログイン時MFAチャレンジ統合テスト。"""

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
from django.urls import NoReverseMatch, reverse

from accounts.models import User

AUTHENTICATION_METHODS_SESSION_KEY = "account_authentication_methods"
CLIENT_IP_HEADER = {"HTTP_X_ACERVO_CLIENT_IP": "198.51.100.10"}


class MFAAuthenticateTests(TestCase):
    password = "SecurePassword123!"
    totp_secret = "JBSWY3DPEHPK3PXP"

    def setUp(self):
        cache.clear()
        self.plain_user = self._user("plain-user")
        self.totp_user = self._user("totp-user")
        TOTP.activate(self.totp_user, self.totp_secret)
        self.recovery_codes = RecoveryCodes.activate(self.totp_user)
        self.recovery_only_user = self._user("recovery-only-user")
        RecoveryCodes.activate(self.recovery_only_user)

    def _user(self, username, *, must_change_password=False):
        return User.objects.create_user(
            username=username,
            password=self.password,
            cohort_number=31,
            must_change_password=must_change_password,
        )

    @staticmethod
    def _valid_totp(secret):
        return format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))

    @staticmethod
    def _invalid_totp(secret):
        valid_codes = {
            format_hotp_value(hotp_value(secret, counter))
            for counter in yield_hotp_counters_from_time()
        }
        for value in range(1_000_000):
            candidate = f"{value:06d}"
            if candidate not in valid_codes:
                return candidate
        raise AssertionError("有効なTOTP以外のコードを生成できませんでした。")

    def _start_login(self, user, *, client=None, next_url=""):
        client = client or self.client
        url = reverse("account_login")
        if next_url:
            url = f"{url}?next={next_url}"
        return client.post(
            url,
            {"login": user.username, "password": self.password},
            **CLIENT_IP_HEADER,
        )

    def test_webauthn_mfa_management_is_exposed_but_passwordless_stays_private(self):
        self.assertEqual(reverse("mfa_authenticate"), "/accounts/mfa/authenticate/")
        for name in ("mfa_list_webauthn", "mfa_add_webauthn", "mfa_reauthenticate_webauthn"):
            self.assertTrue(reverse(name).startswith("/accounts/mfa/webauthn/"))
        for name in (
            "mfa_trust",
            "mfa_login_webauthn",
            "mfa_signup_webauthn",
        ):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)
        for path in (
            "/accounts/mfa/trust/",
            "/accounts/mfa/webauthn/login/",
            "/accounts/mfa/webauthn/signup/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, **CLIENT_IP_HEADER).status_code, 404)

    def test_direct_access_without_login_stage_returns_to_login_and_is_never_cached(self):
        response = self.client.get(reverse("mfa_authenticate"), **CLIENT_IP_HEADER)
        self.assertRedirects(response, reverse("account_login"), fetch_redirect_response=False)
        self.assertEqual(
            response.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_plain_and_recovery_only_users_complete_password_login_without_mfa_stage(self):
        for user in (self.plain_user, self.recovery_only_user):
            with self.subTest(user=user.username):
                client = Client()
                response = self._start_login(user, client=client)
                self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
                self.assertEqual(int(client.session[SESSION_KEY]), user.pk)

    def test_totp_user_requires_challenge_then_correct_totp_completes_login(self):
        response = self._start_login(self.totp_user)
        self.assertRedirects(response, reverse("mfa_authenticate"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

        challenge = self.client.get(reverse("mfa_authenticate"), **CLIENT_IP_HEADER)
        self.assertEqual(challenge.status_code, 200)
        self.assertTemplateUsed(challenge, "mfa/authenticate.html")
        for text in ("二要素認証", "認証アプリ", "リカバリーコード", "確認してログイン"):
            self.assertContains(challenge, text)
        self.assertContains(challenge, 'autocomplete="one-time-code"')
        self.assertContains(challenge, 'inputmode="numeric"')
        self.assertContains(challenge, 'name="csrfmiddlewaretoken"')

        completed = self.client.post(
            reverse("mfa_authenticate"),
            {"code": self._valid_totp(self.totp_secret)},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(
            completed,
            reverse("core:home"),
            fetch_redirect_response=False,
        )
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.totp_user.pk)
        methods = self.client.session[AUTHENTICATION_METHODS_SESSION_KEY]
        self.assertEqual([method["method"] for method in methods], ["password", "mfa"])
        self.assertFalse(any("trust" in key for key in self.client.cookies))
        self.recovery_codes.instance.refresh_from_db()
        self.assertEqual(self.recovery_codes.instance.data["used_mask"], 0)

    def test_recovery_code_completes_login_once_and_wrong_code_neither_logs_in_nor_leaks(self):
        code = self.recovery_codes.get_unused_codes()[0]
        invalid = self._invalid_totp(self.totp_secret)
        self._start_login(self.totp_user)
        rejected = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "認証コードを確認できませんでした。")
        self.assertNotContains(rejected, invalid)
        self.assertNotIn(invalid, repr(dict(self.client.session)))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.recovery_codes.instance.refresh_from_db()
        self.assertEqual(self.recovery_codes.instance.data["used_mask"], 0)

        completed = self.client.post(
            reverse("mfa_authenticate"),
            {"code": code},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(completed, reverse("core:home"), fetch_redirect_response=False)
        self.recovery_codes.instance.refresh_from_db()
        self.assertEqual(len(RecoveryCodes(self.recovery_codes.instance).get_unused_codes()), 9)

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self._start_login(self.totp_user)
        reused = self.client.post(
            reverse("mfa_authenticate"),
            {"code": code},
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(reused.status_code, 200)
        self.assertContains(reused, "認証コードを確認できませんでした。")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_safe_next_is_preserved_and_external_next_is_rejected_after_mfa(self):
        safe = reverse("core:health")
        self._start_login(self.totp_user, next_url=safe)
        safe_response = self.client.post(
            reverse("mfa_authenticate"),
            {"code": self._valid_totp(self.totp_secret)},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(safe_response, safe, fetch_redirect_response=False)

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self._start_login(self.totp_user, next_url="https://attacker.example/path")
        external_response = self.client.post(
            reverse("mfa_authenticate"),
            {"code": self.recovery_codes.get_unused_codes()[0]},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(external_response, reverse("core:home"), fetch_redirect_response=False)

    def test_cancel_post_clears_partial_login_while_get_does_not(self):
        self._start_login(self.totp_user)
        before = dict(self.client.session)
        get_response = self.client.get(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertRedirects(get_response, reverse("account_login"), fetch_redirect_response=False)
        self.assertEqual(dict(self.client.session), before)

        post_response = self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertRedirects(post_response, reverse("account_login"), fetch_redirect_response=False)
        self.assertNotIn("account_login", self.client.session)
        self.assertRedirects(
            self.client.get(reverse("mfa_authenticate"), **CLIENT_IP_HEADER),
            reverse("account_login"),
            fetch_redirect_response=False,
        )

    def test_challenge_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        login_page = client.get(reverse("account_login"), **CLIENT_IP_HEADER)
        token = login_page.cookies["csrftoken"].value
        response = client.post(
            reverse("account_login"),
            {
                "login": self.totp_user.username,
                "password": self.password,
                "csrfmiddlewaretoken": token,
            },
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(response, reverse("mfa_authenticate"), fetch_redirect_response=False)
        self.assertEqual(
            client.post(
                reverse("mfa_authenticate"),
                {"code": self._valid_totp(self.totp_secret)},
                **CLIENT_IP_HEADER,
            ).status_code,
            403,
        )

    def test_inactive_user_does_not_enter_mfa_stage(self):
        self.totp_user.is_active = False
        self.totp_user.save(update_fields=["is_active"])
        response = self._start_login(self.totp_user)
        self.assertRedirects(response, reverse("account_inactive"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_must_change_password_is_enforced_after_mfa_completion(self):
        user = self._user("must-change-totp", must_change_password=True)
        TOTP.activate(user, self.totp_secret)
        self._start_login(user)
        completed = self.client.post(
            reverse("mfa_authenticate"),
            {"code": self._valid_totp(self.totp_secret)},
            **CLIENT_IP_HEADER,
        )
        self.assertRedirects(completed, reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)
        self.assertRedirects(
            self.client.get(reverse("core:home"), **CLIENT_IP_HEADER),
            reverse("account_change_password"),
            fetch_redirect_response=False,
        )

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_mfa_rate_limit_uses_dedicated_client_ip_and_hides_submitted_code(self):
        """MFA制限は専用IPだけで判定し、秘密の入力値を再表示しないこと。"""
        self._start_login(self.totp_user)
        invalid = self._invalid_totp(self.totp_secret)
        unused_codes_before = self.recovery_codes.get_unused_codes()
        first = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.20",
            HTTP_X_FORWARDED_FOR="203.0.113.1",
        )
        self.assertEqual(first.status_code, 200)
        first_error = first.context["form"].errors.as_data()["code"][0]
        self.assertEqual(first_error.code, "incorrect_code")
        self.assertNotContains(first, invalid)
        self.assertNotIn(invalid, repr(dict(self.client.session)))

        second = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.20",
            HTTP_X_FORWARDED_FOR="203.0.113.2",
        )
        self.assertEqual(second.status_code, 200)
        limited_error = second.context["form"].errors.as_data()["code"][0]
        self.assertEqual(limited_error.code, "rate_limited")
        self.assertContains(
            second,
            "試行回数が多すぎます。しばらく待ってからもう一度お試しください。",
        )
        self.assertNotContains(second, invalid)
        self.assertNotIn(invalid, repr(dict(self.client.session)))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.recovery_codes.instance.refresh_from_db()
        self.assertEqual(
            RecoveryCodes(self.recovery_codes.instance).get_unused_codes(), unused_codes_before
        )

        separate = Client()
        self._start_login(self.totp_user, client=separate)
        no_dedicated_header = separate.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            HTTP_X_FORWARDED_FOR="203.0.113.3",
        )
        self.assertEqual(no_dedicated_header.status_code, 403)

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "2/m/ip"})
    def test_successful_mfa_clears_failed_attempt_rate_limit(self):
        """allauth標準のclear_rl()により、成功後は失敗回数が解除されること。"""
        client_ip = "198.51.100.30"
        invalid = self._invalid_totp(self.totp_secret)
        self._start_login(self.totp_user)
        first_failure = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            HTTP_X_ACERVO_CLIENT_IP=client_ip,
        )
        self.assertEqual(
            first_failure.context["form"].errors.as_data()["code"][0].code, "incorrect_code"
        )

        success = self.client.post(
            reverse("mfa_authenticate"),
            {"code": self._valid_totp(self.totp_secret)},
            HTTP_X_ACERVO_CLIENT_IP=client_ip,
        )
        self.assertRedirects(success, reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.totp_user.pk)

        self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self._start_login(self.totp_user)
        later_failure = self.client.post(
            reverse("mfa_authenticate"),
            {"code": invalid},
            HTTP_X_ACERVO_CLIENT_IP=client_ip,
        )
        self.assertEqual(later_failure.status_code, 200)
        later_error = later_failure.context["form"].errors.as_data()["code"][0]
        self.assertEqual(later_error.code, "incorrect_code")
        self.assertNotIn(SESSION_KEY, self.client.session)
