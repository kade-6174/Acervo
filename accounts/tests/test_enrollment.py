from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from accounts.enrollment import (
    CohortStanding,
    EnrollmentStatus,
    cohort_standing_on,
    school_year_on,
    third_year_cohort_for_school_year,
    validate_cohort_for_date,
)


class EnrollmentTests(SimpleTestCase):
    def test_school_year_changes_on_april_first(self):
        self.assertEqual(school_year_on(date(2027, 3, 31)), 2026)
        self.assertEqual(school_year_on(date(2027, 4, 1)), 2027)

    def test_third_year_cohort_uses_approved_baseline(self):
        self.assertEqual(third_year_cohort_for_school_year(2026), 31)
        self.assertEqual(third_year_cohort_for_school_year(2027), 32)

    def test_cohort_standing_changes_at_school_year_boundary(self):
        self.assertEqual(
            cohort_standing_on(31, date(2027, 3, 31)),
            CohortStanding(EnrollmentStatus.ENROLLED, 3),
        )
        self.assertEqual(
            cohort_standing_on(31, date(2027, 4, 1)),
            CohortStanding(EnrollmentStatus.GRADUATED, None),
        )

    def test_each_enrollment_standing(self):
        on_date = date(2026, 4, 1)

        self.assertEqual(
            cohort_standing_on(33, on_date),
            CohortStanding(EnrollmentStatus.ENROLLED, 1),
        )
        self.assertEqual(
            cohort_standing_on(32, on_date),
            CohortStanding(EnrollmentStatus.ENROLLED, 2),
        )
        self.assertEqual(
            cohort_standing_on(31, on_date),
            CohortStanding(EnrollmentStatus.ENROLLED, 3),
        )
        self.assertEqual(
            cohort_standing_on(30, on_date),
            CohortStanding(EnrollmentStatus.GRADUATED, None),
        )

    def test_future_cohort_is_rejected_for_explicit_date(self):
        with self.assertRaisesMessage(ValidationError, "未入学相当"):
            validate_cohort_for_date(34, date(2026, 4, 1))
