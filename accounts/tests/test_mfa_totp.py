"""Phase 1C Sub-step 3B: TOTP登録・無効化の日本語UIおよびフローのテスト。

- TOTP登録画面（GET 200、QRコード、手動入力用シークレット、never_cacheヘッダー）
- 不正コードによる登録拒否
- 正しいTOTPコードによる登録成功、DB上のMultiFernet暗号化保存、リカバリーコード自動生成への遷移
- TOTP無効化確認画面（GET 200、GETでの状態非変更）
- POSTによる無効化とmfa_indexへのリダイレクト
- stale sessionでの再認証誘導
- must_change_password=Trueでの遮断
- WebAuthnの非露出維持
- 秘密値の非ログ出力
"""

import time

from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from accounts.models import User

AUTHENTICATION_METHODS_SESSION_KEY = "account_authentication_methods"
CLIENT_IP_HEADER = {"HTTP_X_ACERVO_CLIENT_IP": "198.51.100.10"}


class TOTPUserInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="totp_test_user",
            email="totp_test@example.com",
            password="SecurePassword123!",
            must_change_password=False,
            role=User.Role.MEMBER,
            cohort_number=31,
        )
        cls.must_change_user = User.objects.create_user(
            username="must_change_totp_user",
            email="must_change_totp@example.com",
            password="TemporaryPassword123!",
            must_change_password=True,
            role=User.Role.MEMBER,
            cohort_number=31,
        )

    def _login_with_recent_auth(self, user, client=None):
        """直近認証済みセッションを作成。"""
        client = client or self.client
        client.force_login(user)
        session = client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [{"method": "password", "at": time.time()}]
        session.save()

    def _login_with_stale_auth(self, user, age_seconds=600):
        """タイムアウト済みセッションを作成。"""
        self.client.force_login(user)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {"method": "password", "at": time.time() - age_seconds}
        ]
        session.save()

    @staticmethod
    def _invalid_totp_code(secret):
        """現在の許容時間窓では必ず不正となる6桁コードを返す。"""
        valid_codes = {
            format_hotp_value(hotp_value(secret, counter))
            for counter in yield_hotp_counters_from_time()
        }
        return next(
            f"{candidate:06d}"
            for candidate in range(1_000_000)
            if f"{candidate:06d}" not in valid_codes
        )

    def test_activate_totp_get_renders_japanese_ui_qr_and_never_cache(self):
        """TOTP登録画面（GET）が日本語UI、QRコード、手動入力用キー、never_cacheヘッダーで描画されること。"""
        self._login_with_recent_auth(self.user)
        response = self.client.get(reverse("mfa_activate_totp"), **CLIENT_IP_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mfa/totp/activate_form.html")

        # 日本語UIの検証
        self.assertContains(response, "認証アプリを設定")
        self.assertContains(response, "手動入力用キー")
        self.assertContains(response, "確認コード（6桁）")
        self.assertContains(response, "認証アプリを登録")
        self.assertContains(response, "リカバリーコード")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        # QRコード（data URI）がimgタグに含まれること
        self.assertContains(response, "data:image/svg+xml;base64,")

        # フォームのコンテキストにsecretが存在し、画面に手動入力用キーが表示されること
        secret = response.context["form"].secret
        self.assertTrue(bool(secret))
        self.assertContains(response, secret)

        # Cache-Controlヘッダーが適切にキャッシュ無効化（no-store）されていること
        cache_control = response.headers.get("Cache-Control")
        self.assertIsNotNone(cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("no-cache", cache_control)
        self.assertIn("must-revalidate", cache_control)

    def test_activate_totp_post_invalid_code_fails(self):
        """不正なTOTPコードをPOSTした場合、登録されずエラーメッセージが表示されること。"""
        self._login_with_recent_auth(self.user)

        # まずGETしてセッションにsecretを確立
        get_resp = self.client.get(reverse("mfa_activate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(get_resp.status_code, 200)

        secret = get_resp.context["form"].secret
        invalid_code = self._invalid_totp_code(secret)

        post_resp = self.client.post(
            reverse("mfa_activate_totp"),
            {"code": invalid_code},
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, "is-invalid")

        # AuthenticatorがDBに作成されていないこと
        self.assertFalse(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    def test_activate_totp_post_valid_code_succeeds_and_encrypts_secret(self):
        """正しいTOTPコードをPOSTした場合、登録が成功し、DB上で暗号化され、リカバリーコード画面へ遷移すること。"""
        self._login_with_recent_auth(self.user)

        # GETしてセッションにsecretを確立
        get_resp = self.client.get(reverse("mfa_activate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(get_resp.status_code, 200)
        plain_secret = get_resp.context["form"].secret

        # 有効なTOTPコードを算出
        current_counter = next(yield_hotp_counters_from_time())
        valid_code = format_hotp_value(hotp_value(plain_secret, current_counter))

        # 正しいコードをPOST
        post_resp = self.client.post(
            reverse("mfa_activate_totp"),
            {"code": valid_code},
            **CLIENT_IP_HEADER,
        )
        # 初回TOTP有効化後はリカバリーコード画面へリダイレクトされる
        self.assertEqual(post_resp.status_code, 302)
        self.assertEqual(post_resp.headers["Location"], reverse("mfa_view_recovery_codes"))

        # DBにTOTP Authenticatorが作成されたことを確認
        authenticator = Authenticator.objects.get(
            user=self.user,
            type=Authenticator.Type.TOTP,
        )
        stored_secret = authenticator.data.get("secret")

        # DB上では平文ではなく暗号化されていること
        self.assertNotEqual(stored_secret, plain_secret)
        self.assertNotIn(plain_secret, stored_secret)

        # AcervoMFAAdapter経由で正しく復号できること
        adapter = get_adapter()
        decrypted_secret = adapter.decrypt(stored_secret)
        self.assertEqual(decrypted_secret, plain_secret)

        # リカバリーコード Authenticatorも自動生成されていること
        recovery_authenticator = Authenticator.objects.get(
            user=self.user,
            type=Authenticator.Type.RECOVERY_CODES,
        )
        self.assertEqual(set(recovery_authenticator.data), {"seed", "used_mask"})
        self.assertNotIn("codes", recovery_authenticator.data)
        self.assertNotIn("migrated_codes", recovery_authenticator.data)
        self.assertNotEqual(adapter.decrypt(recovery_authenticator.data["seed"]), "")

    def test_totp_state_changes_require_csrf_token(self):
        """TOTP登録・無効化のPOSTがCSRF tokenなしでは拒否され、状態を変えないこと。"""
        csrf_client = Client(enforce_csrf_checks=True)
        self._login_with_recent_auth(self.user, client=csrf_client)

        activate_url = reverse("mfa_activate_totp")
        get_response = csrf_client.get(activate_url, **CLIENT_IP_HEADER)
        self.assertEqual(get_response.status_code, 200)
        activate_response = csrf_client.post(
            activate_url,
            {"code": "000000"},
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(activate_response.status_code, 403)
        self.assertFalse(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        deactivate_response = csrf_client.post(
            reverse("mfa_deactivate_totp"),
            **CLIENT_IP_HEADER,
        )
        self.assertEqual(deactivate_response.status_code, 403)
        self.assertTrue(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    @override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "1/m/ip"})
    def test_totp_rate_limit_uses_only_acervo_client_ip_header(self):
        """TOTP確認のIP判定は専用ヘッダーだけを使い、X-Forwarded-Forを信用しないこと。"""
        cache.clear()
        self.addCleanup(cache.clear)
        self._login_with_recent_auth(self.user)
        activate_url = reverse("mfa_activate_totp")
        get_response = self.client.get(activate_url)
        self.assertEqual(get_response.status_code, 200)
        invalid_code = self._invalid_totp_code(get_response.context["form"].secret)

        no_header_response = self.client.post(activate_url, {"code": invalid_code})
        self.assertEqual(no_header_response.status_code, 403)

        xff_only_response = self.client.post(
            activate_url,
            {"code": invalid_code},
            HTTP_X_FORWARDED_FOR="203.0.113.1",
        )
        self.assertEqual(xff_only_response.status_code, 403)

        first_response = self.client.post(
            activate_url,
            {"code": invalid_code},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.10",
            HTTP_X_FORWARDED_FOR="203.0.113.1",
        )
        self.assertEqual(first_response.status_code, 200)
        first_error = first_response.context["form"].errors.as_data()["code"][0]
        self.assertEqual(first_error.code, "incorrect_code")

        limited_response = self.client.post(
            activate_url,
            {"code": invalid_code},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.10",
            HTTP_X_FORWARDED_FOR="203.0.113.250",
        )
        self.assertEqual(limited_response.status_code, 200)
        limited_error = limited_response.context["form"].errors.as_data()["code"][0]
        self.assertEqual(limited_error.code, "rate_limited")

        other_ip_response = self.client.post(
            activate_url,
            {"code": invalid_code},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.11",
            HTTP_X_FORWARDED_FOR="203.0.113.250",
        )
        self.assertEqual(other_ip_response.status_code, 200)
        other_ip_error = other_ip_response.context["form"].errors.as_data()["code"][0]
        self.assertEqual(other_ip_error.code, "incorrect_code")
        self.assertFalse(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    def test_stale_totp_user_cannot_regenerate_recovery_codes(self):
        """stale sessionではRecovery Codes再生成前に再認証を要求し、既存seedを保持すること。"""
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        recovery_codes = RecoveryCodes.activate(self.user).instance
        original_data = dict(recovery_codes.data)
        self._login_with_stale_auth(self.user, age_seconds=600)

        response = self.client.post(
            reverse("mfa_generate_recovery_codes"),
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(reverse("account_reauthenticate")))
        recovery_codes.refresh_from_db()
        self.assertEqual(recovery_codes.data, original_data)

    def test_deactivate_totp_get_renders_confirmation_screen_without_deleting(self):
        """TOTP登録済みユーザーでdeactivateをGETした場合、確認画面が表示され、削除はされないこと。"""
        self._login_with_recent_auth(self.user)
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")

        response = self.client.get(reverse("mfa_deactivate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mfa/totp/deactivate_form.html")
        self.assertContains(response, "認証アプリによる二要素認証を無効にしますか？")
        self.assertContains(response, "認証アプリを無効化する")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        # GETだけではAuthenticatorは削除されない
        self.assertTrue(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    def test_deactivate_totp_post_deactivates_and_redirects_to_mfa_index(self):
        """POSTで無効化を実行するとTOTPが削除され、mfa_indexへリダイレクトされること。"""
        self._login_with_recent_auth(self.user)
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")

        response = self.client.post(reverse("mfa_deactivate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("mfa_index"))

        # Authenticatorが削除されたことを確認
        self.assertFalse(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    def test_deactivate_totp_stale_session_redirects_to_reauthenticate(self):
        """stale sessionでdeactivateをPOSTした場合、
        削除されずreauthenticateへリダイレクトされること。
        """
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        self._login_with_stale_auth(self.user, age_seconds=600)

        response = self.client.post(reverse("mfa_deactivate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(reverse("account_reauthenticate")))

        # Authenticatorは削除されていないこと
        self.assertTrue(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

    def test_mfa_index_renders_japanese_ui_and_reflects_totp_status(self):
        """mfa_index画面でTOTPの未設定/設定済み状態が正しく表示されること。"""
        self._login_with_recent_auth(self.user)

        # 1. 未設定状態
        resp_unconfigured = self.client.get(reverse("mfa_index"), **CLIENT_IP_HEADER)
        self.assertEqual(resp_unconfigured.status_code, 200)
        self.assertTemplateUsed(resp_unconfigured, "mfa/index.html")
        self.assertContains(resp_unconfigured, "二要素認証設定")
        self.assertContains(resp_unconfigured, "未設定")
        self.assertContains(resp_unconfigured, reverse("mfa_activate_totp"))
        self.assertContains(resp_unconfigured, "パスキー / セキュリティキー")
        self.assertContains(resp_unconfigured, "管理する")

        # 2. 設定済み状態
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        resp_configured = self.client.get(reverse("mfa_index"), **CLIENT_IP_HEADER)
        self.assertEqual(resp_configured.status_code, 200)
        self.assertContains(resp_configured, "設定済み")
        self.assertContains(resp_configured, reverse("mfa_deactivate_totp"))

    def test_must_change_password_user_blocked_from_all_mfa_urls(self):
        """must_change_password=TrueのユーザーはMFA画面へ到達できずpassword_changeへ送られること。"""
        self._login_with_recent_auth(self.must_change_user)
        for url_name in ("mfa_index", "mfa_activate_totp", "mfa_deactivate_totp"):
            with self.subTest(url_name=url_name):
                resp = self.client.get(reverse(url_name), **CLIENT_IP_HEADER)
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp.headers["Location"], reverse("account_change_password"))

    def test_passwordless_webauthn_urls_remain_unexposed(self):
        """Step 4Bでは管理URLのみ公開し、passwordless URLは非公開であること。"""
        for name in ("mfa_login_webauthn", "mfa_signup_webauthn"):
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)
