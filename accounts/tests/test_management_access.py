"""Phase 1C Step 5Aの管理アクセス判定ポリシーテスト。"""

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.models import Authenticator
from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from accounts.management_access import (
    ManagementAccessReason,
    evaluate_management_access,
    has_primary_mfa,
    has_session_mfa,
)
from accounts.models import User


class ManagementAccessPolicyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = self.create_user("admin", role=User.Role.ADMIN)

    def create_user(self, username, **extra_fields):
        return User.objects.create_user(username=username, cohort_number=31, **extra_fields)

    def make_request(self, user=None):
        request = self.factory.get("/management/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = user if user is not None else AnonymousUser()
        return request

    def add_authenticator(self, user, authenticator_type):
        return Authenticator.objects.create(
            user=user,
            type=authenticator_type,
            data={"test": True},
        )

    def record_mfa(self, request, authenticator_type, **extra_data):
        record_authentication(
            request,
            request.user,
            "mfa",
            type=authenticator_type,
            **extra_data,
        )

    def assert_reason(self, request, reason):
        decision = evaluate_management_access(request)
        self.assertEqual(decision.reason, reason)
        self.assertEqual(decision.allowed, reason is ManagementAccessReason.ALLOWED)

    def allow_admin(self, authenticator_type=Authenticator.Type.TOTP):
        authenticator = self.add_authenticator(self.admin, authenticator_type)
        request = self.make_request(self.admin)
        self.record_mfa(request, authenticator_type)
        self.assert_reason(request, ManagementAccessReason.ALLOWED)
        return request, authenticator

    def test_user_states_and_role_use_only_acervo_role(self):
        self.assert_reason(self.make_request(), ManagementAccessReason.UNAUTHENTICATED)

        inactive = self.create_user("inactive", role=User.Role.ADMIN, is_active=False)
        self.assert_reason(self.make_request(inactive), ManagementAccessReason.INACTIVE)

        for username, flags in (
            ("member", {}),
            ("staff-member", {"is_staff": True}),
            ("superuser-member", {"is_staff": True, "is_superuser": True}),
        ):
            with self.subTest(username=username):
                member = self.create_user(username, role=User.Role.MEMBER, **flags)
                self.assert_reason(self.make_request(member), ManagementAccessReason.NOT_ADMIN)

        must_change = self.create_user(
            "must-change",
            role=User.Role.ADMIN,
            must_change_password=True,
        )
        self.assert_reason(
            self.make_request(must_change),
            ManagementAccessReason.PASSWORD_CHANGE_REQUIRED,
        )
        self.assert_reason(
            self.make_request(self.admin),
            ManagementAccessReason.PRIMARY_MFA_REQUIRED,
        )

    def test_primary_mfa_definition(self):
        self.assertFalse(has_primary_mfa(self.admin))
        recovery = self.add_authenticator(self.admin, Authenticator.Type.RECOVERY_CODES)
        self.assertFalse(has_primary_mfa(self.admin))
        recovery.delete()

        totp = self.add_authenticator(self.admin, Authenticator.Type.TOTP)
        self.assertTrue(has_primary_mfa(self.admin))
        totp.delete()

        webauthn = self.add_authenticator(self.admin, Authenticator.Type.WEBAUTHN)
        self.assertTrue(has_primary_mfa(self.admin))
        totp = self.add_authenticator(self.admin, Authenticator.Type.TOTP)
        self.assertTrue(has_primary_mfa(self.admin))
        webauthn.delete()
        totp.delete()
        self.assertFalse(has_primary_mfa(self.admin))

    def test_supported_session_mfa_records_are_allowed_with_primary_mfa(self):
        self.add_authenticator(self.admin, Authenticator.Type.TOTP)
        cases = (
            ("totp", Authenticator.Type.TOTP, {}),
            ("webauthn-second-factor", Authenticator.Type.WEBAUTHN, {}),
            ("passwordless-webauthn", Authenticator.Type.WEBAUTHN, {"passwordless": True}),
            ("recovery-code", Authenticator.Type.RECOVERY_CODES, {}),
            ("mfa-reauthentication", Authenticator.Type.TOTP, {"reauthenticated": True}),
            (
                "webauthn-reauthentication",
                Authenticator.Type.WEBAUTHN,
                {"reauthenticated": True},
            ),
        )
        for label, authenticator_type, extra_data in cases:
            with self.subTest(label=label):
                request = self.make_request(self.admin)
                self.record_mfa(request, authenticator_type, **extra_data)
                self.assertTrue(has_session_mfa(request))
                self.assert_reason(request, ManagementAccessReason.ALLOWED)

    def test_password_unknown_incomplete_and_signup_records_are_rejected(self):
        self.add_authenticator(self.admin, Authenticator.Type.TOTP)
        cases = (
            ("password", {"method": "password"}),
            ("username", {"method": "username", "type": Authenticator.Type.TOTP}),
            ("unknown-method", {"method": "unknown", "type": Authenticator.Type.TOTP}),
            ("unknown-type", {"method": "mfa", "type": "unknown"}),
            ("signup", {"method": "mfa", "type": Authenticator.Type.WEBAUTHN, "signup": True}),
        )
        for label, record in cases:
            with self.subTest(label=label):
                request = self.make_request(self.admin)
                method = record.pop("method")
                record_authentication(request, request.user, method, **record)
                self.assertFalse(has_session_mfa(request))
                self.assert_reason(request, ManagementAccessReason.SESSION_MFA_REQUIRED)

        for label, record in (
            ("missing-method", {"at": 1.0, "type": Authenticator.Type.TOTP}),
            ("missing-type", {"at": 1.0, "method": "mfa"}),
            ("missing-timestamp", {"method": "mfa", "type": Authenticator.Type.TOTP}),
        ):
            with self.subTest(label=label):
                request = self.make_request(self.admin)
                request.session["account_authentication_methods"] = [record]
                self.assertFalse(has_session_mfa(request))
                self.assert_reason(request, ManagementAccessReason.SESSION_MFA_REQUIRED)

    def test_primary_and_session_mfa_are_both_required(self):
        request = self.make_request(self.admin)
        self.record_mfa(request, Authenticator.Type.RECOVERY_CODES)
        self.assert_reason(request, ManagementAccessReason.PRIMARY_MFA_REQUIRED)

        self.add_authenticator(self.admin, Authenticator.Type.WEBAUTHN)
        no_session_mfa = self.make_request(self.admin)
        record_authentication(no_session_mfa, self.admin, "password", username=self.admin.username)
        self.assert_reason(no_session_mfa, ManagementAccessReason.SESSION_MFA_REQUIRED)

        self.record_mfa(no_session_mfa, Authenticator.Type.WEBAUTHN, passwordless=True)
        self.assert_reason(no_session_mfa, ManagementAccessReason.ALLOWED)

    def test_database_state_changes_take_effect_on_next_evaluation(self):
        scenarios = (
            ("primary-mfa-deleted", "delete_mfa", ManagementAccessReason.PRIMARY_MFA_REQUIRED),
            ("demoted", "demote", ManagementAccessReason.NOT_ADMIN),
            ("inactive", "deactivate", ManagementAccessReason.INACTIVE),
            (
                "password-change-required",
                "require_password_change",
                ManagementAccessReason.PASSWORD_CHANGE_REQUIRED,
            ),
        )
        for label, mutation, expected_reason in scenarios:
            with self.subTest(label=label):
                user = self.create_user(f"state-{label}", role=User.Role.ADMIN)
                authenticator = self.add_authenticator(user, Authenticator.Type.TOTP)
                request = self.make_request(user)
                self.record_mfa(request, Authenticator.Type.TOTP)
                self.assert_reason(request, ManagementAccessReason.ALLOWED)

                if mutation == "delete_mfa":
                    authenticator.delete()
                elif mutation == "demote":
                    User.objects.filter(pk=user.pk).update(role=User.Role.MEMBER)
                elif mutation == "deactivate":
                    User.objects.filter(pk=user.pk).update(is_active=False)
                else:
                    User.objects.filter(pk=user.pk).update(must_change_password=True)

                self.assert_reason(request, expected_reason)

    def test_logout_and_new_user_session_do_not_inherit_mfa_record(self):
        request, _authenticator = self.allow_admin()
        logout(request)
        self.assert_reason(request, ManagementAccessReason.UNAUTHENTICATED)

        other_admin = self.create_user("other-admin", role=User.Role.ADMIN)
        self.add_authenticator(other_admin, Authenticator.Type.WEBAUTHN)
        new_session = self.make_request(other_admin)
        self.assertFalse(has_session_mfa(new_session))
        self.assert_reason(new_session, ManagementAccessReason.SESSION_MFA_REQUIRED)
