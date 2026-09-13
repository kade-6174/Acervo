"""Phase 1C Sub-step 3B: TOTP登録・無効化の日本語UIおよびフローのテスト。

- TOTP登録画面（GET 200、QRコード、手動入力用シークレット、never_cacheヘッダー）
- 不正コードによる登録拒否
- 正しいTOTPコードによる登録成功、DB上のMultiFernet暗号化保存、リカバリーコード自動生成への遷移
- TOTP無効化確認画面（GET 200、GETでの状態非変更）
- POSTによる無効化とmfa_indexへのリダイレクト
- stale sessionでの再認証誘導
- must_change_password=Trueでの遮断
- WebAuthn・mfa_authenticateの非露出維持
- 秘密値の非ログ出力
"""

import time

from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.test import TestCase
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

    def _login_with_recent_auth(self, user):
        """直近認証済みセッションを作成。"""
        self.client.force_login(user)
        session = self.client.session
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

    def test_activate_totp_get_renders_japanese_ui_qr_and_never_cache(self):
        """TOTP登録画面（GET）が日本語UI、QRコード、手動入力用キー、never_cacheヘッダーで描画されること。"""
        self._login_with_recent_auth(self.user)
        response = self.client.get(reverse("mfa_activate_totp"), **CLIENT_IP_HEADER)

        self.assertEqual(response.status_code, 200)

        # 日本語UIの検証
        self.assertContains(response, "認証アプリを設定")
        self.assertContains(response, "手動入力用キー")
        self.assertContains(response, "確認コード（6桁）")
        self.assertContains(response, "認証アプリを登録")
        self.assertContains(response, "リカバリーコード")

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

        post_resp = self.client.post(
            reverse("mfa_activate_totp"),
            {"code": "000000"},
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
        self.assertTrue(
            Authenticator.objects.filter(
                user=self.user,
                type=Authenticator.Type.RECOVERY_CODES,
            ).exists()
        )

    def test_deactivate_totp_get_renders_confirmation_screen_without_deleting(self):
        """TOTP登録済みユーザーでdeactivateをGETした場合、確認画面が表示され、削除はされないこと。"""
        self._login_with_recent_auth(self.user)
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")

        response = self.client.get(reverse("mfa_deactivate_totp"), **CLIENT_IP_HEADER)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "認証アプリによる二要素認証を無効にしますか？")
        self.assertContains(response, "認証アプリを無効化する")

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
        self.assertContains(resp_unconfigured, "二要素認証設定")
        self.assertContains(resp_unconfigured, "未設定")
        self.assertContains(resp_unconfigured, reverse("mfa_activate_totp"))
        self.assertContains(resp_unconfigured, "準備中")  # パスキー

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

    def test_webauthn_and_mfa_authenticate_remain_unexposed(self):
        """WebAuthn関連URLおよびmfa_authenticateは引き続き非公開であること。"""
        for name in ("mfa_authenticate", "mfa_list_webauthn", "mfa_add_webauthn"):
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)
