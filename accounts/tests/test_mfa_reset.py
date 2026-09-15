"""Phase 1C Step 6AのMFAリセットサービスのテスト。"""

from unittest.mock import patch

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.models import Authenticator
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase

from accounts.management_access import ManagementAccessReason, evaluate_management_access
from accounts.mfa_reset import MFAResetError, MFAResetErrorCode, reset_user_mfa_by_admin
from accounts.models import User
from audit.models import AuditLog


class MFAResetServiceTests(TestCase):
    def setUp(self):
        self.actor = self.create_user("actor", role=User.Role.ADMIN)
        self.add_authenticator(self.actor, Authenticator.Type.TOTP)
        self.target = self.create_user("target")
        self.other = self.create_user("other")
        self.factory = RequestFactory()

    @staticmethod
    def create_user(username, **extra_fields):
        return User.objects.create_user(
            username=username,
            password="SecurePassword123!",
            cohort_number=31,
            **extra_fields,
        )

    @staticmethod
    def add_authenticator(user, authenticator_type):
        return Authenticator.objects.create(
            user=user,
            type=authenticator_type,
            data={"test": True},
        )

    @staticmethod
    def create_session(user):
        client = Client()
        client.force_login(user)
        session = client.session
        session["test_marker"] = user.username
        session.save()
        return session.session_key

    def make_request(self, user):
        request = self.factory.get("/management/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = user
        return request

    def test_reset_deletes_all_target_authenticators_audits_and_invalidates_only_target_sessions(
        self,
    ):
        for authenticator_type in (
            Authenticator.Type.TOTP,
            Authenticator.Type.RECOVERY_CODES,
            Authenticator.Type.WEBAUTHN,
            Authenticator.Type.WEBAUTHN,
        ):
            self.add_authenticator(self.target, authenticator_type)
        self.add_authenticator(self.other, Authenticator.Type.TOTP)
        target_session = self.create_session(self.target)
        actor_session = self.create_session(self.actor)
        other_session = self.create_session(self.other)

        result = reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)

        self.assertEqual(result.target_user_id, self.target.pk)
        self.assertEqual(result.deleted_authenticator_count, 4)
        self.assertFalse(Authenticator.objects.filter(user=self.target).exists())
        self.assertTrue(Authenticator.objects.filter(user=self.other).exists())
        self.target.refresh_from_db()
        self.assertEqual(self.target.mfa_reset_at, result.reset_at)
        self.assertFalse(Session.objects.filter(session_key=target_session).exists())
        self.assertTrue(Session.objects.filter(session_key=actor_session).exists())
        self.assertTrue(Session.objects.filter(session_key=other_session).exists())

        audit = AuditLog.objects.get()
        self.assertEqual(audit.action, AuditLog.Action.ADMIN_MFA_RESET)
        self.assertEqual(audit.channel, AuditLog.Channel.MANAGEMENT_UI)
        self.assertEqual(audit.actor_id, self.actor.pk)
        self.assertEqual(audit.actor_username, self.actor.username)
        self.assertEqual(audit.target_id, self.target.pk)
        self.assertEqual(audit.target_username, self.target.username)
        self.assertNotIn("data", {field.name for field in AuditLog._meta.fields})

    def test_reset_invalidates_old_mfa_record_but_accepts_a_new_record_after_new_registration(self):
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        request = self.make_request(self.target)
        record_authentication(request, self.target, "mfa", type=Authenticator.Type.TOTP)
        self.assertEqual(
            evaluate_management_access(request).reason,
            ManagementAccessReason.NOT_ADMIN,
        )
        self.target.role = User.Role.ADMIN
        self.target.save(update_fields=["role"])
        self.assertEqual(evaluate_management_access(request).reason, ManagementAccessReason.ALLOWED)

        reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        self.assertEqual(
            evaluate_management_access(request).reason,
            ManagementAccessReason.SESSION_MFA_REQUIRED,
        )

        record_authentication(request, self.target, "mfa", type=Authenticator.Type.TOTP)
        self.assertEqual(evaluate_management_access(request).reason, ManagementAccessReason.ALLOWED)

    def test_expected_business_errors_leave_data_and_audit_unchanged(self):
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        cases = (
            ("actor-missing", 999_999, self.target.pk, MFAResetErrorCode.ACTOR_NOT_FOUND),
            ("target-missing", self.actor.pk, 999_999, MFAResetErrorCode.TARGET_NOT_FOUND),
            ("self", self.actor.pk, self.actor.pk, MFAResetErrorCode.SELF_RESET_NOT_ALLOWED),
        )
        for label, actor_id, target_id, expected_code in cases:
            with self.subTest(label=label):
                with self.assertRaises(MFAResetError) as raised:
                    reset_user_mfa_by_admin(actor_id=actor_id, target_user_id=target_id)
                self.assertEqual(raised.exception.code, expected_code)
                self.assertTrue(Authenticator.objects.filter(user=self.target).exists())
                self.assertEqual(AuditLog.objects.count(), 0)

        for label, changes, expected_code in (
            ("member", {"role": User.Role.MEMBER}, MFAResetErrorCode.ACTOR_NOT_ADMIN),
            ("inactive", {"is_active": False}, MFAResetErrorCode.ACTOR_INACTIVE),
            (
                "password-change",
                {"must_change_password": True},
                MFAResetErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED,
            ),
        ):
            with self.subTest(label=label):
                User.objects.filter(pk=self.actor.pk).update(**changes)
                with self.assertRaises(MFAResetError) as raised:
                    reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)
                self.assertEqual(raised.exception.code, expected_code)
                User.objects.filter(pk=self.actor.pk).update(
                    role=User.Role.ADMIN,
                    is_active=True,
                    must_change_password=False,
                )

        Authenticator.objects.filter(user=self.actor).delete()
        with self.assertRaises(MFAResetError) as raised:
            reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)
        self.assertEqual(raised.exception.code, MFAResetErrorCode.ACTOR_PRIMARY_MFA_REQUIRED)

    def test_target_without_authenticator_is_rejected_without_audit_or_timestamp(self):
        with self.assertRaises(MFAResetError) as raised:
            reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)

        self.assertEqual(raised.exception.code, MFAResetErrorCode.TARGET_HAS_NO_AUTHENTICATORS)
        self.target.refresh_from_db()
        self.assertIsNone(self.target.mfa_reset_at)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_normal_mfa_registration_and_authentication_do_not_set_reset_timestamp(self):
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        request = self.make_request(self.target)
        record_authentication(request, self.target, "mfa", type=Authenticator.Type.TOTP)

        self.target.refresh_from_db()

        self.assertIsNone(self.target.mfa_reset_at)

    def test_audit_failure_rolls_back_authenticators_timestamp_and_sessions(self):
        self.add_authenticator(self.target, Authenticator.Type.TOTP)
        target_session = self.create_session(self.target)

        with (
            patch(
                "accounts.mfa_reset.AuditLog.objects.create", side_effect=RuntimeError("failure")
            ),
            self.assertRaises(RuntimeError),
        ):
            reset_user_mfa_by_admin(actor_id=self.actor.pk, target_user_id=self.target.pk)

        self.assertTrue(Authenticator.objects.filter(user=self.target).exists())
        self.target.refresh_from_db()
        self.assertIsNone(self.target.mfa_reset_at)
        self.assertTrue(Session.objects.filter(session_key=target_session).exists())
        self.assertEqual(AuditLog.objects.count(), 0)


class AuditLogModelTests(TestCase):
    def test_existing_audit_log_cannot_be_updated_or_deleted_by_instance_operations(self):
        actor = User.objects.create_user(
            username="actor", password="SecurePassword123!", cohort_number=31
        )
        target = User.objects.create_user(
            username="target", password="SecurePassword123!", cohort_number=31
        )
        audit = AuditLog.objects.create(
            action=AuditLog.Action.ADMIN_MFA_RESET,
            channel=AuditLog.Channel.MANAGEMENT_UI,
            actor=actor,
            actor_username=actor.username,
            target=target,
            target_username=target.username,
        )

        audit.actor_username = "changed"
        with self.assertRaises(ValidationError):
            audit.save()
        with self.assertRaises(ValidationError):
            audit.delete()
        self.assertEqual(AuditLog.objects.get(pk=audit.pk).actor_username, actor.username)
