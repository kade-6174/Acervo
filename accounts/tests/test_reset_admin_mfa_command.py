"""Phase 1C Step 6Cの最後の管理者向けMFAリセットコマンド。"""

from io import StringIO
from unittest.mock import patch

from allauth.mfa.models import Authenticator
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase

from accounts.mfa_reset import reset_admin_mfa_by_command
from accounts.models import User
from audit.models import AuditLog


class ResetAdminMFACommandTests(TestCase):
    password = "SecurePassword123!"

    def setUp(self):
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
