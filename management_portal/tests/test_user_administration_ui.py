import time

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog


class UserAdministrationUITests(TestCase):
    password = "SecurePassword123!"

    def setUp(self):
        self.actor = self.create_user("actor", role=User.Role.ADMIN)
        self.target = self.create_user("target")
        self.add_primary_mfa(self.actor)
        self.login_as_recently_reauthenticated_admin(self.actor)

    def create_user(self, username, **extra):
        return User.objects.create_user(
            username=username,
            password=self.password,
            cohort_number=extra.pop("cohort_number", 31),
            **extra,
        )

    @staticmethod
    def add_primary_mfa(user):
        return Authenticator.objects.create(
            user=user, type=Authenticator.Type.TOTP, data={"test": True}
        )

    def login_as_recently_reauthenticated_admin(self, user, client=None, *, age=0):
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
    def list_url(self):
        return reverse("management:user_list")

    @property
    def edit_url(self):
        return reverse("management:user_edit", args=[self.target.pk])

    @property
    def create_url(self):
        return reverse("management:user_create")

    @property
    def reissue_url(self):
        return reverse("management:user_password_reissue", args=[self.target.pk])

    @property
    def audit_log_url(self):
        return reverse("management:audit_log_list")

    def post_data(self, **overrides):
        data = {
            "role": User.Role.ADMIN,
            "is_active": "on",
            "confirmed": "on",
            "username": self.target.username,
        }
        data.update(overrides)
        return data

    def assert_target_unchanged(self):
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.MEMBER)
        self.assertTrue(self.target.is_active)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_list_and_edit_are_available_only_to_management_authorized_admin(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.target.username)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.get(self.edit_url).status_code, 200)

        member = self.create_user("member")
        member_client = Client()
        member_client.force_login(member)
        self.assertEqual(member_client.get(self.list_url).status_code, 403)
        self.assertEqual(member_client.post(self.edit_url, self.post_data()).status_code, 403)
        self.assert_target_unchanged()

    def test_get_and_invalid_post_do_not_change_user(self):
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self.post_data(confirmed="", username="wrong"))

        self.assert_target_unchanged()

    def test_post_requires_csrf_and_recent_mfa_reauthentication(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.login_as_recently_reauthenticated_admin(self.actor, csrf_client)
        csrf_client.get(self.edit_url)
        response = csrf_client.post(self.edit_url, self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assert_target_unchanged()

        self.login_as_recently_reauthenticated_admin(self.actor, age=10_000)
        stale = self.client.post(self.edit_url, self.post_data())
        self.assertEqual(stale.status_code, 302)
        self.assertTrue(stale.headers["Location"].startswith(reverse("mfa_reauthenticate")))
        self.assert_target_unchanged()

    def test_success_updates_user_and_redirects_without_replaying_post(self):
        response = self.client.post(self.edit_url, self.post_data())

        self.assertRedirects(response, self.edit_url, fetch_redirect_response=False)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ADMIN)
        self.assertEqual(AuditLog.objects.count(), 1)
        page = self.client.get(self.edit_url)
        self.assertContains(page, "設定を更新しました。")
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_last_active_admin_is_protected(self):
        actor_url = reverse("management:user_edit", args=[self.actor.pk])
        response = self.client.post(
            actor_url,
            {
                "role": User.Role.MEMBER,
                "is_active": "on",
                "confirmed": "on",
                "username": self.actor.username,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "最後の有効な管理者")
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.role, User.Role.ADMIN)
        self.assertTrue(self.actor.is_active)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_no_secret_input_is_rendered_or_saved_in_messages(self):
        response = self.client.post(
            self.edit_url,
            self.post_data(username="not-the-target", credential="secret", password="secret"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "credential")
        self.assertNotContains(response, "secret")
        self.assert_target_unchanged()

    def test_admin_can_create_user_and_only_response_contains_temporary_password(self):
        response = self.client.post(
            self.create_url,
            {
                "username": "created-user",
                "cohort_number": 31,
                "role": User.Role.MEMBER,
                "confirmed": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="created-user")
        temporary_password = response.context["temporary_password"]
        self.assertTrue(created.check_password(temporary_password))
        self.assertTrue(created.must_change_password)
        self.assertContains(response, temporary_password)
        self.assertIn("no-store", response.headers["Cache-Control"])
        audit = AuditLog.objects.get(action=AuditLog.Action.USER_CREATED)
        self.assertEqual(audit.target, created)
        self.assertNotIn(temporary_password, audit.actor_username)
        self.assertNotIn(temporary_password, audit.target_username)

    def test_create_post_requires_management_access_and_recent_mfa(self):
        member = self.create_user("member")
        member_client = Client()
        member_client.force_login(member)
        self.assertEqual(
            member_client.post(
                self.create_url,
                {"username": "not-created", "role": User.Role.MEMBER, "confirmed": "on"},
            ).status_code,
            403,
        )

        self.login_as_recently_reauthenticated_admin(self.actor, age=10_000)
        response = self.client.post(
            self.create_url,
            {"username": "not-created", "role": User.Role.MEMBER, "confirmed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(reverse("mfa_reauthenticate")))
        self.assertFalse(User.objects.filter(username="not-created").exists())

    def test_admin_can_reissue_another_users_password_without_auditing_secret(self):
        response = self.client.post(
            self.reissue_url,
            {"confirmed": "on", "username": self.target.username},
        )

        self.assertEqual(response.status_code, 200)
        temporary_password = response.context["temporary_password"]
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(temporary_password))
        self.assertTrue(self.target.must_change_password)
        self.assertIn("no-store", response.headers["Cache-Control"])
        audit = AuditLog.objects.get(action=AuditLog.Action.USER_PASSWORD_REISSUED)
        self.assertNotIn(temporary_password, audit.actor_username)
        self.assertNotIn(temporary_password, audit.target_username)

    def test_cannot_reissue_own_password_or_reissue_without_confirmation(self):
        own_url = reverse("management:user_password_reissue", args=[self.actor.pk])
        response = self.client.post(
            own_url,
            {"confirmed": "on", "username": self.actor.username},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "自分自身の一時パスワード")
        self.assertEqual(AuditLog.objects.count(), 0)

        response = self.client.post(self.reissue_url, {"username": self.target.username})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_audit_log_is_admin_only_and_never_renders_secret_values(self):
        AuditLog.objects.create(
            action=AuditLog.Action.USER_CREATED,
            channel=AuditLog.Channel.MANAGEMENT_UI,
            actor=self.actor,
            actor_username=self.actor.username,
            target=self.target,
            target_username=self.target.username,
        )

        page = self.client.get(self.audit_log_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "利用者作成")
        self.assertContains(page, self.actor.username)
        self.assertNotContains(page, "SecurePassword123!")
        self.assertIn("no-store", page.headers["Cache-Control"])

        member = self.create_user("member")
        member_client = Client()
        member_client.force_login(member)
        self.assertEqual(member_client.get(self.audit_log_url).status_code, 403)
