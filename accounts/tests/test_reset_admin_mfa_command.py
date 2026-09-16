"""Phase 1C Step 6Cの最後の管理者向けMFAリセットコマンド。"""

from io import StringIO
from unittest.mock import patch

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.mfa_reset import reset_admin_mfa_by_command
from accounts.models import User
from audit.models import AuditLog


class ResetAdminMFACommandTests(TestCase):
    password = "SecurePassword123!"
    totp_secret = "JBSWY3DPEHPK3PXP"
    client_ip = {"HTTP_X_ACERVO_CLIENT_IP": "198.51.100.249"}

    def setUp(self):
        cache.clear()
        self.target = self.create_user("last-admin", role=User.Role.ADMIN)
        self.add_authenticator(self.target, Authenticator.Type.TOTP)

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

    def run_command(self, username=None, confirmation=None):
        output = StringIO()
        stdin = StringIO("" if confirmation is None else f"{confirmation}\n")
        with patch("sys.stdin", stdin):
            call_command("reset_admin_mfa", username or self.target.username, stdout=output)
        return output.getvalue()

    @staticmethod
    def valid_totp(secret):
        return format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))

    def assert_unchanged(self):
        self.assertTrue(Authenticator.objects.filter(user=self.target).exists())
        self.target.refresh_from_db()
        self.assertIsNone(self.target.mfa_reset_at)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_last_admin_reset_deletes_all_authenticators_sessions_and_audits(self):
        self.add_authenticator(self.target, Authenticator.Type.RECOVERY_CODES)
        self.add_authenticator(self.target, Authenticator.Type.WEBAUTHN)
        self.add_authenticator(self.target, Authenticator.Type.WEBAUTHN)
        client = Client()
        client.force_login(self.target)
        session_key = client.session.session_key
        original_password = self.target.password
        output = self.run_command(confirmation=f"RESET {self.target.username}")

        self.assertIn(self.target.username, output)
        self.assertIn("削除した認証器: 4件", output)
        self.assertNotIn("test", output)
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.target.refresh_from_db()
        self.assertIsNotNone(self.target.mfa_reset_at)
        self.assertEqual(self.target.role, User.Role.ADMIN)
        self.assertTrue(self.target.is_active)
        self.assertFalse(self.target.must_change_password)
        self.assertEqual(self.target.password, original_password)
        audit = AuditLog.objects.get()
        self.assertEqual(audit.action, AuditLog.Action.COMMAND_MFA_RESET)
        self.assertEqual(audit.channel, AuditLog.Channel.MANAGEMENT_COMMAND)
        self.assertIsNone(audit.actor)
        self.assertEqual(audit.actor_username, "server-operator")
        self.assertEqual(audit.target, self.target)

    def test_bad_empty_or_eof_confirmation_changes_nothing(self):
        for confirmation in ("RESET wrong", "", None):
            with self.subTest(confirmation=confirmation), self.assertRaises(CommandError):
                self.run_command(confirmation=confirmation)
            self.assert_unchanged()

    def test_missing_member_inactive_and_no_authenticator_targets_are_rejected(self):
        cases = [
            ("missing", "missing"),
            ("member", self.create_user("member").username),
            (
                "inactive",
                self.create_user("inactive", role=User.Role.ADMIN, is_active=False).username,
            ),
        ]
        no_auth = self.create_user("no-auth", role=User.Role.ADMIN)
        cases.append(("no-auth", no_auth.username))
        for label, username in cases:
            with self.subTest(label=label), self.assertRaises(CommandError):
                self.run_command(username, f"RESET {username}")
        self.assert_unchanged()
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_recoverable_other_admin_requires_management_ui(self):
        other = self.create_user("other", role=User.Role.ADMIN)
        self.add_authenticator(other, Authenticator.Type.TOTP)
        with self.assertRaisesRegex(CommandError, "通常の管理画面"):
            self.run_command(confirmation=f"RESET {self.target.username}")
        self.assert_unchanged()

    def test_unrecoverable_other_admins_do_not_block_command(self):
        inactive = self.create_user("inactive", role=User.Role.ADMIN, is_active=False)
        changing = self.create_user("changing", role=User.Role.ADMIN, must_change_password=True)
        recovery_only = self.create_user("recovery", role=User.Role.ADMIN)
        self.add_authenticator(inactive, Authenticator.Type.TOTP)
        self.add_authenticator(changing, Authenticator.Type.TOTP)
        self.add_authenticator(recovery_only, Authenticator.Type.RECOVERY_CODES)
        self.run_command(confirmation=f"RESET {self.target.username}")
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_replay_and_audit_failure_do_not_create_second_audit_or_partial_reset(self):
        self.run_command(confirmation=f"RESET {self.target.username}")
        with self.assertRaises(CommandError):
            self.run_command(confirmation=f"RESET {self.target.username}")
        self.assertEqual(AuditLog.objects.count(), 1)

        target = self.create_user("rollback", role=User.Role.ADMIN)
        self.add_authenticator(target, Authenticator.Type.TOTP)
        rollback_client = Client()
        rollback_client.force_login(target)
        rollback_session_key = rollback_client.session.session_key
        with (
            patch(
                "accounts.mfa_reset.AuditLog.objects.create", side_effect=RuntimeError("failure")
            ),
            self.assertRaises(RuntimeError),
        ):
            reset_admin_mfa_by_command(target_username=target.username)
        self.assertTrue(Authenticator.objects.filter(user=target).exists())
        target.refresh_from_db()
        self.assertIsNone(target.mfa_reset_at)
        self.assertTrue(Session.objects.filter(session_key=rollback_session_key).exists())

    def test_reset_admin_can_login_but_requires_new_mfa_before_management_access(self):
        previous_password = self.target.password
        old_client = Client()
        old_client.force_login(self.target)
        old_session = old_client.session
        old_session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {"method": "mfa", "type": Authenticator.Type.TOTP, "at": 1}
        ]
        old_session.save()
        old_session_key = old_session.session_key

        self.run_command(confirmation=f"RESET {self.target.username}")
        self.target.refresh_from_db()
        self.assertEqual(self.target.password, previous_password)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())

        client = Client()
        login = client.post(
            reverse("account_login"),
            {"login": self.target.username, "password": self.password},
            **self.client_ip,
        )
        self.assertEqual(login.status_code, 302)
        denied = client.get(reverse("management:index"), **self.client_ip)
        self.assertRedirects(denied, reverse("mfa_index"), fetch_redirect_response=False)

        TOTP.activate(self.target, self.totp_secret)
        reauthentication = client.get(reverse("management:index"), **self.client_ip)
        self.assertTrue(
            reauthentication.headers["Location"].startswith(reverse("mfa_reauthenticate"))
        )
        completed = client.post(
            reauthentication.headers["Location"],
            {"code": self.valid_totp(self.totp_secret)},
            **self.client_ip,
        )
        self.assertRedirects(completed, reverse("management:index"), fetch_redirect_response=False)
        self.assertEqual(client.get(reverse("management:index"), **self.client_ip).status_code, 200)

    def test_command_preserves_required_password_change_and_non_secret_outputs(self):
        original_password = self.target.password
        self.target.must_change_password = True
        self.target.save(update_fields=["must_change_password"])
        output = self.run_command(confirmation=f"RESET {self.target.username}")
        self.target.refresh_from_db()
        self.assertTrue(self.target.must_change_password)
        self.assertEqual(self.target.password, original_password)
        self.assertNotIn("test", output)
        audit = AuditLog.objects.get()
        self.assertNotIn("test", audit.actor_username)
        self.assertNotIn("test", audit.target_username)
