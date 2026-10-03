from datetime import date

from django.test import TestCase, override_settings

from accounts.models import User
from management_portal.admin_warnings import get_administrator_warnings


@override_settings(
    ACERVO_ENROLLMENT_POLICY="school_cohort",
    ACERVO_SCHOOL_YEAR_START_MONTH=4,
    ACERVO_SCHOOL_YEAR_START_DAY=1,
    ACERVO_BASE_SCHOOL_YEAR=2026,
    ACERVO_BASE_FIRST_YEAR_COHORT=33,
)
class AdministratorWarningsTests(TestCase):
    def create_admin(self, username, cohort_number, *, is_active=True):
        return User.objects.create_user(
            username=username,
            password="SecurePassword123!",
            cohort_number=cohort_number,
            role=User.Role.ADMIN,
            is_active=is_active,
        )

    def test_strong_warning_when_no_current_enrolled_admin_exists(self):
        self.create_admin("graduate-admin", 30)
        self.create_admin("inactive-student-admin", 31, is_active=False)

        warnings = get_administrator_warnings(on_date=date(2027, 2, 1))

        self.assertTrue(warnings.no_current_enrolled_admin)

    def test_successor_warning_starts_60_days_before_school_year_change(self):
        self.create_admin("graduating-admin", 31)

        before_window = get_administrator_warnings(on_date=date(2027, 1, 30))
        in_window = get_administrator_warnings(on_date=date(2027, 1, 31))

        self.assertFalse(before_window.successor_required)
        self.assertTrue(in_window.successor_required)

    def test_successor_warning_is_not_shown_when_next_year_enrolled_admin_exists(self):
        self.create_admin("graduating-admin", 31)
        self.create_admin("successor-admin", 32)

        warnings = get_administrator_warnings(on_date=date(2027, 2, 1))

        self.assertFalse(warnings.no_current_enrolled_admin)
        self.assertFalse(warnings.successor_required)

    @override_settings(ACERVO_ENROLLMENT_POLICY="none")
    def test_warnings_are_not_used_when_school_cohort_policy_is_disabled(self):
        self.create_admin("admin-without-cohort", None)

        self.assertEqual(
            get_administrator_warnings(on_date=date(2027, 2, 1)),
            type(get_administrator_warnings(on_date=date(2027, 2, 1)))(),
        )
