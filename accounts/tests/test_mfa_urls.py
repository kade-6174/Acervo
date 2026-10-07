"""MFA URLルーティングおよびアクセス制御のテスト。

- TOTP / Recovery Codes の管理、および再認証に必要な最小限のURLのみを公開
- 匿名ユーザーのログイン誘導
- InitialPasswordChangeMiddlewareによる未変更ユーザーの遮断
- WebAuthn・未公開URLの非露出とログイン時MFA認証URLの公開
- 直近認証タイムアウト時（stale session）の再認証誘導とNoReverseMatch防止
- GETリクエストでの状態変更防止
- Cache-Control / Pragma ヘッダーの実測
"""

import time
from urllib.parse import unquote

from allauth.mfa.models import Authenticator
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import User

AUTHENTICATION_METHODS_SESSION_KEY = "account_authentication_methods"


class MFAURLRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.normal_user = User.objects.create_user(
            username="normaluser",
            email="normal@example.com",
            password="SecurePassword123!",
            must_change_password=False,
            role=User.Role.MEMBER,
            cohort_number=31,
        )
        cls.must_change_user = User.objects.create_user(
            username="mustchangeuser",
            email="mustchange@example.com",
            password="TemporaryPassword123!",
            must_change_password=True,
            role=User.Role.MEMBER,
            cohort_number=31,
        )

    def setUp(self):
        self.exposed_mfa_url_names = [
            "mfa_index",
            "mfa_reauthenticate",
            "mfa_activate_totp",
            "mfa_deactivate_totp",
            "mfa_view_recovery_codes",
            "mfa_generate_recovery_codes",
            "mfa_download_recovery_codes",
        ]
        self.all_exposed_url_names = ["account_reauthenticate"] + self.exposed_mfa_url_names

    def _login_with_recent_auth(self, user):
        """直近認証済みセッション（did_recently_authenticate=True）を持つクライアント状態を作る。"""
        self.client.force_login(user)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [{"method": "password", "at": time.time()}]
        session.save()

    def _login_with_stale_auth(self, user, age_seconds=600):
        """タイムアウト済みセッション（did_recently_authenticate=False）を持つクライアント状態を作る。"""
        self.client.force_login(user)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {"method": "password", "at": time.time() - age_seconds}
        ]
        session.save()

    def test_required_url_names_reverse_successfully(self):
        """必要なallauth MFAおよび再認証URL nameが期待通りのパスに解決されること。"""
        expected_mappings = {
            "account_reauthenticate": "/accounts/reauthenticate/",
            "mfa_index": "/accounts/mfa/",
            "mfa_reauthenticate": "/accounts/mfa/reauthenticate/",
            "mfa_authenticate": "/accounts/mfa/authenticate/",
            "mfa_activate_totp": "/accounts/mfa/totp/activate/",
            "mfa_deactivate_totp": "/accounts/mfa/totp/deactivate/",
            "mfa_view_recovery_codes": "/accounts/mfa/recovery-codes/",
            "mfa_generate_recovery_codes": "/accounts/mfa/recovery-codes/generate/",
            "mfa_download_recovery_codes": "/accounts/mfa/recovery-codes/download/",
        }
        for name, expected_path in expected_mappings.items():
            with self.subTest(name=name):
                self.assertEqual(reverse(name), expected_path)

    def test_webauthn_management_and_passwordless_names_are_exposed(self):
        """Step 4Cでpasswordless入口を明示公開すること。"""
        for name in (
            "mfa_list_webauthn",
            "mfa_add_webauthn",
            "mfa_reauthenticate_webauthn",
            "mfa_login_webauthn",
        ):
            self.assertTrue(reverse(name).startswith("/accounts/mfa/webauthn/"))
        unexposed_names = [
            "mfa_trust",
            "mfa_signup_webauthn",
        ]
        for name in unexposed_names:
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)

    def test_signup_path_returns_404(self):
        """未公開のパスへ直接アクセスした場合は404を返すこと。"""
        self._login_with_recent_auth(self.normal_user)
        unexposed_paths = [
            "/accounts/mfa/trust/",
            "/accounts/mfa/webauthn/signup/",
        ]
        for path in unexposed_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_anonymous_user_redirected_to_login(self):
        """匿名ユーザーがMFA URLへアクセスした場合、ログイン画面へリダイレクトされること。"""
        login_url = reverse("account_login")
        for name in self.all_exposed_url_names:
            target_url = reverse(name)
            with self.subTest(name=name):
                response = self.client.get(target_url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].startswith(login_url))
                self.assertIn(f"next={target_url}", unquote(response.headers["Location"]))

    def test_must_change_password_user_redirected_to_password_change(self):
        """must_change_password=TrueのユーザーはMFA/再認証URLへアクセスできず、
        password_changeへ送られること。
        """
        self._login_with_recent_auth(self.must_change_user)
        change_password_url = reverse("account_change_password")
        for name in self.all_exposed_url_names:
            target_url = reverse(name)
            with self.subTest(name=name):
                response = self.client.get(target_url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], change_password_url)

    def test_must_change_password_user_cannot_bypass_gate_with_post(self):
        """初回パスワード変更前は状態変更POSTも遮断され、Authenticatorを変更しないこと。"""
        from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
        from allauth.mfa.totp.internal.auth import TOTP

        TOTP.activate(self.must_change_user, "JBSWY3DPEHPK3PXP")
        recovery_codes = RecoveryCodes.activate(self.must_change_user).instance
        original_recovery_data = dict(recovery_codes.data)
        self._login_with_recent_auth(self.must_change_user)

        for name in ("mfa_deactivate_totp", "mfa_generate_recovery_codes"):
            with self.subTest(name=name):
                response = self.client.post(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.headers["Location"],
                    reverse("account_change_password"),
                )

        self.assertTrue(
            Authenticator.objects.filter(
                user=self.must_change_user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )
        recovery_codes.refresh_from_db()
        self.assertEqual(recovery_codes.data, original_recovery_data)

    def test_authenticated_user_can_access_mfa_urls(self):
        """通常認証済みユーザーが公開URLにアクセス可能なこと。"""
        self._login_with_recent_auth(self.normal_user)

        # account_reauthenticate: 200 OK
        resp = self.client.get(reverse("account_reauthenticate"))
        self.assertEqual(resp.status_code, 200)

        # mfa_index: 200 OK
        resp = self.client.get(reverse("mfa_index"))
        self.assertEqual(resp.status_code, 200)

        # mfa_reauthenticate: MFA未登録時は利用不可のため、account_reauthenticateへリダイレクト
        resp = self.client.get(reverse("mfa_reauthenticate"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], reverse("account_reauthenticate"))

        # mfa_activate_totp: TOTP未登録時は200 OK
        resp = self.client.get(reverse("mfa_activate_totp"))
        self.assertEqual(resp.status_code, 200)

        # mfa_deactivate_totp: TOTP未登録時はAuthenticatorが存在しないため404
        resp = self.client.get(reverse("mfa_deactivate_totp"))
        self.assertEqual(resp.status_code, 404)

        # mfa_generate_recovery_codes: 200 OK (確認画面)
        resp = self.client.get(reverse("mfa_generate_recovery_codes"))
        self.assertEqual(resp.status_code, 200)

        # mfa_view_recovery_codes: 未作成時は404
        resp = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(resp.status_code, 404)

        # mfa_download_recovery_codes: 未作成時は404
        resp = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(resp.status_code, 404)

        # 登録画面は、選択後にサーバーから方式に対応したchallengeを取得する。
        webauthn_add = self.client.get(reverse("mfa_add_webauthn"))
        self.assertEqual(webauthn_add.status_code, 200)
        self.assertEqual(
            webauthn_add.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )
        self.assertContains(webauthn_add, 'name="passwordless"')
        self.assertContains(webauthn_add, 'id="id_passwordless" checked')
        self.assertContains(
            webauthn_add,
            reverse("mfa_webauthn_registration_options"),
        )
        self.assertContains(
            webauthn_add, "秘密鍵や生体情報がこのサイトへ送信・保存されることはありません"
        )

    def test_authenticated_user_with_authenticators_can_access_views(self):
        """Authenticator登録済みユーザーが各管理URLに正常にアクセスできること。"""
        self._login_with_recent_auth(self.normal_user)

        # TOTP Authenticator を作成
        from allauth.mfa.totp.internal.auth import TOTP

        TOTP.activate(self.normal_user, "JBSWY3DPEHPK3PXP")

        # TOTP設定済みの場合、mfa_deactivate_totp は 200 OK
        resp = self.client.get(reverse("mfa_deactivate_totp"))
        self.assertEqual(resp.status_code, 200)

        # TOTP設定済みの場合、mfa_reauthenticate は 200 OK
        resp_reauth = self.client.get(reverse("mfa_reauthenticate"))
        self.assertEqual(resp_reauth.status_code, 200)

        # RecoveryCodes Authenticator を作成
        from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes

        recovery_codes = RecoveryCodes.activate(self.normal_user)
        plaintext_codes = recovery_codes.get_unused_codes()

        # 1回目のアクセス: まだ閲覧されていないためダウンロード可能 (200 OK)
        resp_download = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(resp_download.status_code, 200)
        self.assertEqual(resp_download.headers.get("Content-Type"), "text/plain")
        self.assertIn("attachment", resp_download.headers.get("Content-Disposition", ""))

        # DownloadRecoveryCodesView の Cache-Control ヘッダー実測
        # (DownloadRecoveryCodesView には @method_decorator(never_cache) が付与されている)
        download_cache_control = resp_download.headers.get("Cache-Control")
        self.assertIsNotNone(download_cache_control)
        self.assertIn("max-age=0", download_cache_control)
        self.assertIn("no-cache", download_cache_control)
        self.assertIn("no-store", download_cache_control)

        # 2回目のアクセス: SHOW_ONCE=True のため、再ダウンロードは 403 PermissionDenied
        resp_download_again = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(resp_download_again.status_code, 403)

        # 一度閲覧後の mfa_view_recovery_codes は 200 OK だがコードはマスキングされる
        resp_view = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(resp_view.status_code, 200)
        self.assertFalse(resp_view.context["can_view_codes"])
        self.assertTrue(all(code == "****" for code in resp_view.context["unused_codes"]))
        for code in plaintext_codes:
            self.assertNotContains(resp_view, code)
        recovery_codes.instance.refresh_from_db()
        self.assertIn("viewed_at", recovery_codes.instance.data)

    def test_stale_session_redirects_to_reauthenticate_without_no_reverse_match(self):
        """直近認証タイムアウト（stale session）の状態で保護操作をPOSTした際、
        NoReverseMatchにならず正常にaccount_reauthenticateへリダイレクトされること。
        """
        # 1. パスワードのみのユーザー（TOTP未登録）でRecoveryCodes再生成をPOST
        self._login_with_stale_auth(self.normal_user, age_seconds=600)
        resp_password_only = self.client.post(reverse("mfa_generate_recovery_codes"))
        self.assertEqual(resp_password_only.status_code, 302)
        self.assertTrue(
            resp_password_only.headers["Location"].startswith(reverse("account_reauthenticate"))
        )

        # 2. TOTP有効済みユーザーでTOTP無効化をPOST
        from allauth.mfa.totp.internal.auth import TOTP

        TOTP.activate(self.normal_user, "JBSWY3DPEHPK3PXP")

        # セッションを再度stale状態にする
        self._login_with_stale_auth(self.normal_user, age_seconds=600)
        resp_totp_user = self.client.post(reverse("mfa_deactivate_totp"))
        # allauthはget_reauthentication_methodsで候補を列挙し、先頭（パスワード再認証）へ誘導
        self.assertEqual(resp_totp_user.status_code, 302)
        self.assertTrue(
            resp_totp_user.headers["Location"].startswith(reverse("account_reauthenticate"))
        )
        self.assertTrue(
            Authenticator.objects.filter(
                user=self.normal_user,
                type=Authenticator.Type.TOTP,
            ).exists()
        )

        # パスワード再認証画面はMFA再認証を代替手段として列挙する
        password_reauth = self.client.get(resp_totp_user.headers["Location"])
        self.assertEqual(password_reauth.status_code, 200)
        password_alternatives = {
            alternative["id"]
            for alternative in password_reauth.context["reauthentication_alternatives"]
        }
        self.assertIn("mfa_reauthenticate", password_alternatives)

        # MFA再認証画面もパスワード再認証を代替手段として列挙する
        mfa_reauth = self.client.get(reverse("mfa_reauthenticate"))
        self.assertEqual(mfa_reauth.status_code, 200)
        mfa_alternatives = {
            alternative["id"] for alternative in mfa_reauth.context["reauthentication_alternatives"]
        }
        self.assertIn("reauthenticate", mfa_alternatives)

    def test_no_state_change_on_get(self):
        """GETリクエストによって状態変更（Authenticatorの生成・削除等）が発生しないこと。"""
        self._login_with_recent_auth(self.normal_user)
        initial_count = Authenticator.objects.filter(user=self.normal_user).count()

        for name in self.all_exposed_url_names:
            self.client.get(reverse(name))

        current_count = Authenticator.objects.filter(user=self.normal_user).count()
        self.assertEqual(initial_count, current_count)

    def test_cache_control_headers_inspection(self):
        """TOTP登録画面やRecovery Codes画面のCache-Controlヘッダーの状態を実測・検証する。"""
        self._login_with_recent_auth(self.normal_user)

        # 1. mfa_index
        resp_index = self.client.get(reverse("mfa_index"))
        self.assertEqual(resp_index.status_code, 200)
        self.assertEqual(
            resp_index.headers.get("Cache-Control"),
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

        # 2. mfa_activate_totp (TOTP secretが表示される画面: never_cache適用済み)
        resp_totp = self.client.get(reverse("mfa_activate_totp"))
        self.assertEqual(resp_totp.status_code, 200)
        totp_cache_control = resp_totp.headers.get("Cache-Control")
        self.assertIsNotNone(totp_cache_control)
        self.assertIn("max-age=0", totp_cache_control)
        self.assertIn("no-cache", totp_cache_control)
        self.assertIn("no-store", totp_cache_control)
        self.assertIn("must-revalidate", totp_cache_control)

        # 3. mfa_generate_recovery_codes
        resp_gen = self.client.get(reverse("mfa_generate_recovery_codes"))
        self.assertEqual(resp_gen.status_code, 200)
        self.assertEqual(
            resp_gen.headers.get("Cache-Control"),
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

        # 4. mfa_view_recovery_codes
        # (初回表示時: Recovery Codesが表示される最重要画面: never_cache適用済み)
        from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes

        recovery_codes = RecoveryCodes.activate(self.normal_user)
        initial_codes = recovery_codes.get_unused_codes()
        resp_rc_view = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(resp_rc_view.status_code, 200)
        self.assertTrue(resp_rc_view.context["can_view_codes"])
        for code in initial_codes:
            self.assertContains(resp_rc_view, code)
        rc_cache_control = resp_rc_view.headers.get("Cache-Control")
        self.assertIsNotNone(rc_cache_control)
        self.assertIn("max-age=0", rc_cache_control)
        self.assertIn("no-cache", rc_cache_control)
        self.assertIn("no-store", rc_cache_control)
        self.assertIn("must-revalidate", rc_cache_control)

        second_rc_view = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(second_rc_view.status_code, 200)
        self.assertFalse(second_rc_view.context["can_view_codes"])
        for code in initial_codes:
            self.assertNotContains(second_rc_view, code)

        # 5. mfa_download_recovery_codes (allauth標準でnever_cache適用済み)
        # SHOW_ONCE=True のため未閲覧の別ユーザーでダウンロードを実行
        dl_user = User.objects.create_user(
            username="cache_dl_user",
            email="cache_dl@example.com",
            password="SecurePassword123!",
            must_change_password=False,
            role=User.Role.MEMBER,
            cohort_number=31,
        )
        self._login_with_recent_auth(dl_user)
        RecoveryCodes.activate(dl_user)
        resp_rc_download = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(resp_rc_download.status_code, 200)
        dl_cache_control = resp_rc_download.headers.get("Cache-Control")
        self.assertIsNotNone(dl_cache_control)
        self.assertIn("max-age=0", dl_cache_control)
        self.assertIn("no-cache", dl_cache_control)
        self.assertIn("no-store", dl_cache_control)
        self.assertIn("must-revalidate", dl_cache_control)
