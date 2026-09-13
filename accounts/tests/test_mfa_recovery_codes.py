"""Phase 1C Sub-step 3CのRecovery Codes表示・再生成フローの回帰テスト。"""

import time
from urllib.parse import parse_qs, urlparse

from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import TOTP
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User

AUTHENTICATION_METHODS_SESSION_KEY = "account_authentication_methods"
CACHE_CONTROL = "max-age=0, no-cache, no-store, must-revalidate, private"


class RecoveryCodesUserInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="recovery_codes_user",
            email="recovery-codes@example.com",
            password="SecurePassword123!",
            must_change_password=False,
            role=User.Role.MEMBER,
            cohort_number=31,
        )
        cls.must_change_user = User.objects.create_user(
            username="recovery_codes_must_change",
            email="recovery-codes-must-change@example.com",
            password="TemporaryPassword123!",
            must_change_password=True,
            role=User.Role.MEMBER,
            cohort_number=31,
        )

    def _login_with_recent_auth(self, user, client=None):
        client = client or self.client
        client.force_login(user)
        session = client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [{"method": "password", "at": time.time()}]
        session.save()

    def _login_with_stale_auth(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {"method": "password", "at": time.time() - 600}
        ]
        session.save()

    def _activate_recovery_codes(self, user=None):
        return RecoveryCodes.activate(user or self.user)

    def test_first_view_shows_ten_codes_once_with_local_save_controls_and_no_cache(self):
        """初回だけ平文10個とローカル保存用UIを返し、再訪では秘密値を返さない。"""
        self._login_with_recent_auth(self.user)
        codes = self._activate_recovery_codes().get_unused_codes()

        response = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mfa/recovery_codes/index.html")
        self.assertTrue(response.context["can_view_codes"])
        self.assertEqual(len(codes), 10)
        self.assertEqual(response.headers["Cache-Control"], CACHE_CONTROL)
        for code in codes:
            self.assertContains(response, code)
        for text in (
            "今回しか表示されません",
            "各コードは1回だけ使用できます",
            "安全な場所へ保存してください",
            "スクリーンショットは推奨しません",
            "すべてコピー",
            "ファイルとして保存",
            "安全な場所へ保存しました",
        ):
            self.assertContains(response, text)
        for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
            self.assertNotContains(response, forbidden)
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'typeof navigator.clipboard.writeText !== "function"')
        self.assertContains(response, "コードを手動で選択してコピーしてください")
        self.assertContains(response, "すべてのコードをコピーしました")
        self.assertContains(response, "ファイルの保存を開始しました")
        self.assertContains(response, "document.body.appendChild(link)")
        self.assertContains(response, "link.remove()")
        self.assertContains(response, "URL.revokeObjectURL")

        revisit = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertEqual(revisit.status_code, 200)
        self.assertFalse(revisit.context["can_view_codes"])
        self.assertEqual(revisit.headers["Cache-Control"], CACHE_CONTROL)
        for code in codes:
            self.assertNotContains(revisit, code)
        self.assertContains(revisit, "同じコードは再表示できません")
        self.assertNotContains(revisit, "すべてコピー")
        self.assertNotContains(revisit, "ファイルとして保存")

    def test_view_then_download_is_forbidden_and_download_then_view_cannot_repeat(self):
        """SHOW_ONCEの標準仕様どおり、表示・ダウンロードのどちらも一回だけにする。"""
        self._login_with_recent_auth(self.user)
        self._activate_recovery_codes()

        self.client.get(reverse("mfa_view_recovery_codes"))
        after_view = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(after_view.status_code, 403)

        download_user = User.objects.create_user(
            username="recovery_download_user",
            email="recovery-download@example.com",
            password="SecurePassword123!",
            must_change_password=False,
            role=User.Role.MEMBER,
            cohort_number=31,
        )
        self._login_with_recent_auth(download_user)
        download_codes = self._activate_recovery_codes(download_user).get_unused_codes()
        download = self.client.get(reverse("mfa_download_recovery_codes"))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["Cache-Control"], CACHE_CONTROL)
        self.assertEqual(
            download.headers["Content-Disposition"],
            'attachment; filename="recovery-codes.txt"',
        )
        for code in download_codes:
            self.assertIn(code, download.content.decode())
        self.assertEqual(self.client.get(reverse("mfa_download_recovery_codes")).status_code, 403)
        hidden = self.client.get(reverse("mfa_view_recovery_codes"))
        self.assertFalse(hidden.context["can_view_codes"])
        for code in download_codes:
            self.assertNotContains(hidden, code)

    def test_generate_confirmation_get_is_non_mutating_and_post_replaces_all_codes(self):
        """確認GETは変更せず、POSTはallauth標準の再生成で旧コードだけを無効化する。"""
        self._login_with_recent_auth(self.user)
        TOTP.activate(self.user, "JBSWY3DPEHPK3PXP")
        old_authenticator = self._activate_recovery_codes().instance
        old_codes = old_authenticator.wrap().get_unused_codes()
        generate_url = reverse("mfa_generate_recovery_codes")

        confirmation = self.client.get(generate_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertTemplateUsed(confirmation, "mfa/recovery_codes/generate.html")
        self.assertEqual(confirmation.headers["Cache-Control"], CACHE_CONTROL)
        self.assertEqual(confirmation.context["unused_code_count"], 10)
        for text in (
            "現在の未使用コードは",
            "既存の全コードは直ちに無効になります",
            "この操作は取り消せません",
            "TOTPの認証アプリ設定は無効になりません",
            "新しいコードも一度だけ表示されます",
            "既存コードを無効にして再生成",
            "キャンセル",
        ):
            self.assertContains(confirmation, text)
        self.assertContains(confirmation, 'id="generate-recovery-codes-form"')
        self.assertContains(confirmation, "submit.disabled = true")
        self.assertContains(confirmation, 'submit.textContent = "再生成しています"')
        old_authenticator.refresh_from_db()
        self.assertEqual(old_authenticator.wrap().get_unused_codes(), old_codes)

        generated = self.client.post(generate_url)
        self.assertRedirects(
            generated,
            reverse("mfa_view_recovery_codes"),
            fetch_redirect_response=False,
        )
        new_authenticator = Authenticator.objects.get(
            user=self.user, type=Authenticator.Type.RECOVERY_CODES
        )
        new_codes = new_authenticator.wrap().get_unused_codes()
        self.assertEqual(len(new_codes), 10)
        self.assertFalse(Authenticator.objects.filter(pk=old_authenticator.pk).exists())
        for old_code in old_codes:
            self.assertFalse(new_authenticator.wrap().validate_code(old_code))
        self.assertTrue(
            Authenticator.objects.filter(user=self.user, type=Authenticator.Type.TOTP).exists()
        )

    def test_recovery_codes_alone_cannot_generate_new_codes(self):
        """Recovery Codesだけでは再生成できず、既存の秘密値と閲覧状態を維持する。"""
        self._login_with_recent_auth(self.user)
        recovery_codes = self._activate_recovery_codes()
        plain_codes = recovery_codes.get_unused_codes()
        recovery_codes.mark_as_viewed()
        recovery_codes.instance.refresh_from_db()
        original_pk = recovery_codes.instance.pk
        original_data = dict(recovery_codes.instance.data)

        self.assertEqual(set(original_data), {"seed", "used_mask", "viewed_at"})
        self.assertFalse(
            Authenticator.objects.filter(user=self.user)
            .exclude(type=Authenticator.Type.RECOVERY_CODES)
            .exists()
        )

        response = self.client.post(reverse("mfa_generate_recovery_codes"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        authenticators = Authenticator.objects.filter(user=self.user)
        self.assertEqual(authenticators.count(), 1)
        unchanged = authenticators.get()
        self.assertEqual(unchanged.pk, original_pk)
        self.assertEqual(unchanged.data, original_data)
        for code in plain_codes:
            self.assertNotContains(response, code)

    def test_generate_post_requires_csrf_and_stale_reauthentication_does_not_replay_it(self):
        """CSRFと直近再認証を必須にし、再認証後も取消不能なPOSTを自動再送しない。"""
        csrf_client = Client(enforce_csrf_checks=True)
        self._login_with_recent_auth(self.user, client=csrf_client)
        recovery = self._activate_recovery_codes().instance
        original_data = dict(recovery.data)
        generate_url = reverse("mfa_generate_recovery_codes")
        csrf_client.get(generate_url)
        csrf_rejected = csrf_client.post(generate_url)
        self.assertEqual(csrf_rejected.status_code, 403)
        recovery.refresh_from_db()
        self.assertEqual(recovery.data, original_data)

        self._login_with_stale_auth(self.user)
        stale = self.client.post(generate_url)
        self.assertEqual(stale.status_code, 302)
        redirect = stale.headers["Location"]
        self.assertTrue(redirect.startswith(reverse("account_reauthenticate")))
        self.assertEqual(parse_qs(urlparse(redirect).query)["next"], [generate_url])
        recovery.refresh_from_db()
        self.assertEqual(recovery.data, original_data)

        reauthenticated = self.client.post(
            redirect,
            {"password": "SecurePassword123!"},
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.20",
        )
        self.assertRedirects(reauthenticated, generate_url, fetch_redirect_response=False)
        recovery.refresh_from_db()
        self.assertEqual(recovery.data, original_data)

    def test_recovery_code_urls_reject_anonymous_users_and_must_change_users(self):
        """匿名と初回パスワード未変更の利用者は、Recovery Codes操作を実行できない。"""
        urls = (
            "mfa_view_recovery_codes",
            "mfa_generate_recovery_codes",
            "mfa_download_recovery_codes",
        )
        for name in urls:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].startswith(reverse("account_login")))

        self._login_with_recent_auth(self.must_change_user)
        self._activate_recovery_codes(self.must_change_user)
        for name in urls:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response,
                    reverse("account_change_password"),
                    fetch_redirect_response=False,
                )
