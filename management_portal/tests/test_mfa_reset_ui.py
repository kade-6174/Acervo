"""Phase 1C Step 6Bの別管理者MFAリセット画面テスト。"""

import time
from types import SimpleNamespace
from unittest.mock import patch

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog


class MFAResetUITests(TestCase):
    password = "SecurePassword123!"

    def setUp(self):
        self.actor = self.create_user("actor", role=User.Role.ADMIN)
        self.target = self.create_user("target")
        self.add_authenticator(self.actor, Authenticator.Type.TOTP)
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        self.login_as_recently_reauthenticated_mfa_admin(self.actor)

    def create_user(self, username, **extra):
        return User.objects.create_user(
            username=username,
            password=self.password,
            cohort_number=extra.pop("cohort_number", 31),
            **extra,
        )

    @staticmethod
    def add_authenticator(user, authenticator_type):
        return Authenticator.objects.create(user=user, type=authenticator_type, data={"test": True})

    def login_as_recently_reauthenticated_mfa_admin(self, user, client=None, *, age=0):
        client = client or self.client
        client.force_login(user)
        session = client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {
                "method": "mfa",
                "type": Authenticator.Type.TOTP,
                "reauthenticated": True,
                "at": time.time() - age,
            }
        ]
        session.save()
        return client

    @property
    def search_url(self):
        return reverse("management:mfa_reset_search")

    @property
    def confirm_url(self):
        return reverse("management:mfa_reset_confirm", args=[self.target.pk])

    def valid_post(self, **overrides):
        data = {"confirmed": "on", "username": self.target.username}
        data.update(overrides)
        return self.client.post(self.confirm_url, data)

    def assert_unchanged(self):
        self.assertTrue(Authenticator.objects.filter(user=self.target).exists())
        self.target.refresh_from_db()
        self.assertIsNone(self.target.mfa_reset_at)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_only_allowed_admin_reaches_search_and_confirm(self):
        self.assertEqual(self.client.get(self.search_url).status_code, 200)
        self.assertEqual(self.client.get(self.confirm_url).status_code, 200)

    def test_anonymous_member_and_staff_or_superuser_member_are_rejected(self):
        cases = [
            ("anonymous", Client()),
            ("member", Client()),
            ("staff-member", Client()),
            ("superuser-member", Client()),
        ]
        member = self.create_user("member")
        staff = self.create_user("staff", is_staff=True)
        superuser = self.create_user("superuser", is_superuser=True)
        for label, client in cases:
            with self.subTest(label=label):
                if label == "member":
                    client.force_login(member)
                elif label == "staff-member":
                    client.force_login(staff)
                elif label == "superuser-member":
                    client.force_login(superuser)
                response = client.get(self.confirm_url)
                self.assertNotEqual(response.status_code, 200)
        self.assert_unchanged()

    def test_exact_username_search_and_missing_user_are_safe(self):
        found = self.client.get(self.search_url, {"username": self.target.username})
        self.assertContains(found, self.target.username)
        self.assertContains(found, "TOTP")
        missing = self.client.get(self.search_url, {"username": "tar"})
        self.assertContains(missing, "一致する利用者は見つかりませんでした。")
        self.assert_unchanged()

    def test_get_does_not_change_data_and_never_caches(self):
        response = self.client.get(self.confirm_url)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assert_unchanged()

    def test_post_without_csrf_is_403_and_does_not_reset(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.login_as_recently_reauthenticated_mfa_admin(self.actor, csrf_client)
        csrf_client.get(self.confirm_url)
        response = csrf_client.post(
            self.confirm_url,
            {"confirmed": "on", "username": self.target.username},
        )
        self.assertEqual(response.status_code, 403)
        self.assert_unchanged()

    def test_missing_confirmation_or_wrong_username_does_not_reset(self):
        self.client.post(self.confirm_url, {"username": self.target.username})
        self.assert_unchanged()
        self.client.post(self.confirm_url, {"confirmed": "on", "username": "wrong"})
        self.assert_unchanged()

    def test_username_changed_after_get_does_not_reset(self):
        self.client.get(self.confirm_url)
        User.objects.filter(pk=self.target.pk).update(username="renamed")
        self.valid_post()
        self.assert_unchanged()

    def test_self_reset_is_rejected_without_change(self):
        url = reverse("management:mfa_reset_confirm", args=[self.actor.pk])
        response = self.client.post(url, {"confirmed": "on", "username": self.actor.username})
        self.assertContains(response, "自分自身のMFA")
        self.assertTrue(Authenticator.objects.filter(user=self.actor).exists())
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_stale_post_redirects_to_mfa_reauthentication_without_saving_or_replaying_body(self):
        self.login_as_recently_reauthenticated_mfa_admin(self.actor, age=10_000)
        response = self.client.post(
            f"{self.confirm_url}?next=//attacker.example/",
            {"confirmed": "on", "username": self.target.username},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(reverse("mfa_reauthenticate")))
        self.assertIn("next=%2Fmanagement%2Fusers%2F", response.headers["Location"])
        self.assertNotIn("attacker", response.headers["Location"])
        self.assertNotIn("username", self.client.session)
        self.assert_unchanged()

    def test_totp_reauthentication_return_target_get_and_requires_second_post(self):
        self.login_as_recently_reauthenticated_mfa_admin(self.actor, age=10_000)
        self.valid_post()
        # allauth完了後のセッション状態を再現。POST本文はこの状態に含めない。
        self.login_as_recently_reauthenticated_mfa_admin(self.actor)
        returned = self.client.get(self.confirm_url)
        self.assertEqual(returned.status_code, 200)
        self.assert_unchanged()
        self.valid_post()
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())

    def test_webauthn_reauthentication_record_is_accepted(self):
        self.login_as_recently_reauthenticated_mfa_admin(self.actor)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY][-1]["type"] = Authenticator.Type.WEBAUTHN
        session.save()
        response = self.valid_post()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_no_mfa_reauthentication_method_fails_closed(self):
        self.login_as_recently_reauthenticated_mfa_admin(self.actor, age=10_000)
        adapter = SimpleNamespace(get_reauthentication_methods=lambda _user: [])
        with patch("management_portal.views.get_adapter", return_value=adapter):
            response = self.valid_post()
        self.assertRedirects(response, self.search_url, fetch_redirect_response=False)
        self.assert_unchanged()

    def test_success_invalidates_only_target_session_updates_timestamp_and_audits_once(self):
        self.add_authenticator(self.target, Authenticator.Type.WEBAUTHN)
        self.add_authenticator(self.target, Authenticator.Type.RECOVERY_CODES)
        target_client = Client()
        target_client.force_login(self.target)
        target_key = target_client.session.session_key
        actor_key = self.client.session.session_key
        response = self.valid_post()
        self.assertRedirects(response, self.confirm_url, fetch_redirect_response=False)
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())
        self.target.refresh_from_db()
        self.assertIsNotNone(self.target.mfa_reset_at)
        self.assertFalse(Session.objects.filter(session_key=target_key).exists())
        self.assertTrue(Session.objects.filter(session_key=actor_key).exists())
        self.assertEqual(AuditLog.objects.count(), 1)
        replay = self.valid_post()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_member_admin_inactive_and_graduate_can_be_reset_by_other_admin(self):
        for username, extra in (
            ("member-target", {}),
            ("admin-target", {"role": User.Role.ADMIN}),
            ("inactive-target", {"is_active": False}),
            ("graduate-target", {"cohort_number": 1}),
        ):
            with self.subTest(username=username):
                target = self.create_user(username, **extra)
                self.add_authenticator(target, Authenticator.Type.TOTP)
                url = reverse("management:mfa_reset_confirm", args=[target.pk])
                response = self.client.post(url, {"confirmed": "on", "username": username})
                self.assertEqual(response.status_code, 302)
                self.assertFalse(Authenticator.objects.filter(user=target).exists())

    def test_actor_state_rechecked_at_post_and_no_secret_is_rendered(self):
        self.actor.role = User.Role.MEMBER
        self.actor.save(update_fields=["role"])
        response = self.valid_post()
        self.assertEqual(response.status_code, 403)
        self.assert_unchanged()
        User.objects.filter(pk=self.actor.pk).update(role=User.Role.ADMIN)
        page = self.client.get(self.confirm_url)
        self.assertNotContains(page, "test")
        self.assertNotContains(page, "credential")

    def test_actor_primary_mfa_removed_before_post_is_rejected(self):
        Authenticator.objects.filter(user=self.actor).delete()
        response = self.valid_post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(reverse("mfa_index")))
        self.assert_unchanged()
