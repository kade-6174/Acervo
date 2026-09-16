from datetime import date
from io import StringIO

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.enrollment import (
    EnrollmentStatus,
    cohort_standing_on,
    school_year_on,
    validate_cohort_for_date,
)
from accounts.models import User
from accounts.security import validate_enrollment_settings
from accounts.services import create_user_with_temporary_password


class EnrollmentSettingsTests(SimpleTestCase):
    def test_only_known_policies_are_accepted(self):
        validate_enrollment_settings("none", 4, 1, 2026, 31)
        validate_enrollment_settings("school_cohort", 4, 1, 2026, 31)
        with self.assertRaises(ImproperlyConfigured):
            validate_enrollment_settings("invalid", 4, 1, 2026, 31)

    @override_settings(
        ACERVO_ENROLLMENT_POLICY="school_cohort",
        ACERVO_SCHOOL_YEAR_START_MONTH=9,
        ACERVO_SCHOOL_YEAR_START_DAY=1,
        ACERVO_BASE_SCHOOL_YEAR=2030,
        ACERVO_BASE_THIRD_YEAR_COHORT=50,
    )
    def test_school_policy_uses_configured_boundary_and_baseline(self):
        self.assertEqual(school_year_on(date(2031, 8, 31)), 2030)
        self.assertEqual(school_year_on(date(2031, 9, 1)), 2031)
        self.assertEqual(cohort_standing_on(50, date(2031, 8, 31)).grade, 3)
        self.assertEqual(
            cohort_standing_on(50, date(2031, 9, 1)).status, EnrollmentStatus.GRADUATED
        )

    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    def test_none_policy_does_not_require_or_apply_cohort(self):
        validate_cohort_for_date(None, date(2026, 4, 1))
        validate_cohort_for_date(999, date(2026, 4, 1))
        self.assertEqual(
            cohort_standing_on(None, date(2026, 4, 1)).status,
            EnrollmentStatus.NOT_APPLICABLE,
        )


class EnrollmentPolicyUserTests(TestCase):
    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    def test_none_allows_member_admin_manager_and_service_without_cohort(self):
        member = User.objects.create_user(username="none-member")
        admin = User.objects.create_user(username="none-admin", role=User.Role.ADMIN)
        result = create_user_with_temporary_password(username="none-service")
        self.assertIsNone(member.cohort_number)
        self.assertIsNone(admin.cohort_number)
        self.assertIsNone(result.user.cohort_number)

    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    async def test_none_allows_async_manager_without_cohort(self):
        user = await User.objects.acreate_user(username="none-async")
        self.assertIsNone(user.cohort_number)

    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    def test_none_bootstrap_admin_does_not_require_cohort(self):
        output = StringIO()
        call_command("bootstrap_admin", username="none-bootstrap", stdout=output)
        self.assertIsNone(User.objects.get(username="none-bootstrap").cohort_number)

    @override_settings(ACERVO_ENROLLMENT_POLICY="school_cohort")
    def test_school_policy_rejects_missing_and_future_cohort(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(username="missing-cohort")
        with self.assertRaises(ValidationError):
            User.objects.create_user(username="future-cohort", cohort_number=999)

    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    def test_database_allows_null_but_rejects_non_positive_cohort(self):
        User(username="null-cohort").save(force_insert=True)
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                User(username=f"invalid-{value}", cohort_number=value).save(force_insert=True)
