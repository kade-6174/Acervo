from unittest.mock import patch

from allauth.mfa.models import Authenticator
from django.test import TestCase

from accounts.models import User
from accounts.user_administration import (
    UserAdministrationError,
    UserAdministrationErrorCode,
    create_user_by_admin,
    reissue_temporary_password_by_admin,
    update_user_administration_by_admin,
)
from audit.models import AuditLog


class UserAdministrationServiceTests(TestCase):
    def setUp(self):
        self.actor = self.create_user("actor", role=User.Role.ADMIN)
        self.add_primary_mfa(self.actor)
        self.target = self.create_user("target")

    @staticmethod
    def create_user(username, **extra_fields):
        return User.objects.create_user(
            username=username,
            password="test-password-123",
            cohort_number=31,
            **extra_fields,
        )

    @staticmethod
    def add_primary_mfa(user):
        return Authenticator.objects.create(
            user=user,
            type=Authenticator.Type.TOTP,
            data={"test": True},
        )

    def update(self, **overrides):
        arguments = {
            "actor_id": self.actor.pk,
            "target_user_id": self.target.pk,
            "role": User.Role.ADMIN,
            "is_active": True,
        }
        arguments.update(overrides)
        return update_user_administration_by_admin(**arguments)

    def assert_target_unchanged(self):
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.MEMBER)
        self.assertTrue(self.target.is_active)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_promotes_user_and_records_non_secret_audit_log(self):
        result = self.update()

        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ADMIN)
        self.assertTrue(result.role_changed)
        self.assertFalse(result.active_state_changed)
        audit = AuditLog.objects.get()
        self.assertEqual(audit.action, AuditLog.Action.USER_ROLE_CHANGED)
        self.assertEqual(audit.actor, self.actor)
        self.assertEqual(audit.target, self.target)
        self.assertNotIn("password", audit.actor_username)
        self.assertNotIn("password", audit.target_username)

    def test_changes_active_state_and_audits_each_changed_field(self):
        result = self.update(role=User.Role.ADMIN, is_active=False)

        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.ADMIN)
        self.assertFalse(self.target.is_active)
        self.assertTrue(result.role_changed)
        self.assertTrue(result.active_state_changed)
        self.assertEqual(
            set(AuditLog.objects.values_list("action", flat=True)),
            {
                AuditLog.Action.USER_ROLE_CHANGED,
                AuditLog.Action.USER_ACTIVE_STATE_CHANGED,
            },
        )

    def test_noop_does_not_create_audit_log(self):
        result = self.update(role=User.Role.MEMBER, is_active=True)

        self.assertFalse(result.role_changed)
        self.assertFalse(result.active_state_changed)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_last_active_admin_cannot_be_demoted_or_deactivated(self):
        for role, is_active in ((User.Role.MEMBER, True), (User.Role.ADMIN, False)):
            with self.subTest(role=role, is_active=is_active):
                with self.assertRaisesRegex(UserAdministrationError, "last_active_admin_required"):
                    update_user_administration_by_admin(
                        actor_id=self.actor.pk,
                        target_user_id=self.actor.pk,
                        role=role,
                        is_active=is_active,
                    )
                self.actor.refresh_from_db()
                self.assertEqual(self.actor.role, User.Role.ADMIN)
                self.assertTrue(self.actor.is_active)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_invalid_input_is_rejected(self):
        cases = (
            ("role", {"role": "owner"}, UserAdministrationErrorCode.INVALID_ROLE),
            ("active", {"is_active": 1}, UserAdministrationErrorCode.INVALID_ACTIVE_STATE),
        )
        for label, overrides, expected_code in cases:
            with self.subTest(label=label):
                with self.assertRaises(UserAdministrationError) as raised:
                    self.update(**overrides)
                self.assertEqual(raised.exception.code, expected_code)
                self.assert_target_unchanged()

    def test_actor_state_is_rechecked(self):
        cases = (
            ("inactive", {"is_active": False}, UserAdministrationErrorCode.ACTOR_INACTIVE),
            ("member", {"role": User.Role.MEMBER}, UserAdministrationErrorCode.ACTOR_NOT_ADMIN),
            (
                "password-change",
                {"must_change_password": True},
                UserAdministrationErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED,
            ),
        )
        for label, changes, expected_code in cases:
            with self.subTest(label=label):
                User.objects.filter(pk=self.actor.pk).update(**changes)
                with self.assertRaises(UserAdministrationError) as raised:
                    self.update()
                self.assertEqual(raised.exception.code, expected_code)
                self.assert_target_unchanged()
                User.objects.filter(pk=self.actor.pk).update(
                    is_active=True,
                    role=User.Role.ADMIN,
                    must_change_password=False,
                )

    def test_actor_requires_primary_mfa(self):
        Authenticator.objects.filter(user=self.actor).delete()

        with self.assertRaises(UserAdministrationError) as raised:
            self.update()

        self.assertEqual(
            raised.exception.code, UserAdministrationErrorCode.ACTOR_PRIMARY_MFA_REQUIRED
        )
        self.assert_target_unchanged()

    def test_audit_failure_rolls_back_user_change(self):
        with (
            patch(
                "accounts.user_administration.AuditLog.objects.create",
                side_effect=RuntimeError("audit failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "audit failure"),
        ):
            self.update()

        self.assert_target_unchanged()

    def test_admin_creates_user_and_audits_without_temporary_password(self):
        result = create_user_by_admin(
            actor_id=self.actor.pk,
            username="new-user",
            cohort_number=32,
            role=User.Role.MEMBER,
        )

        result.user.refresh_from_db()
        self.assertTrue(result.user.check_password(result.temporary_password))
        self.assertTrue(result.user.must_change_password)
        audit = AuditLog.objects.get()
        self.assertEqual(audit.action, AuditLog.Action.USER_CREATED)
        self.assertEqual(audit.actor, self.actor)
        self.assertEqual(audit.target, result.user)
        self.assertNotIn(result.temporary_password, audit.actor_username)
        self.assertNotIn(result.temporary_password, audit.target_username)

    def test_admin_reissues_another_users_password_and_audits_without_secret(self):
        result = reissue_temporary_password_by_admin(
            actor_id=self.actor.pk,
            target_user_id=self.target.pk,
        )

        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(result.temporary_password))
        self.assertTrue(self.target.must_change_password)
        audit = AuditLog.objects.get()
        self.assertEqual(audit.action, AuditLog.Action.USER_PASSWORD_REISSUED)
        self.assertEqual(audit.actor, self.actor)
        self.assertEqual(audit.target, self.target)
        self.assertNotIn(result.temporary_password, audit.actor_username)
        self.assertNotIn(result.temporary_password, audit.target_username)

    def test_admin_cannot_reissue_own_password_from_management(self):
        with self.assertRaises(UserAdministrationError) as raised:
            reissue_temporary_password_by_admin(
                actor_id=self.actor.pk,
                target_user_id=self.actor.pk,
            )

        self.assertEqual(
            raised.exception.code,
            UserAdministrationErrorCode.SELF_PASSWORD_REISSUE_NOT_ALLOWED,
        )
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_password_reissue_audit_failure_rolls_back_password_change(self):
        old_password_hash = self.target.password
        with (
            patch(
                "accounts.user_administration.AuditLog.objects.create",
                side_effect=RuntimeError("audit failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "audit failure"),
        ):
            reissue_temporary_password_by_admin(
                actor_id=self.actor.pk,
                target_user_id=self.target.pk,
            )

        self.target.refresh_from_db()
        self.assertEqual(self.target.password, old_password_hash)
