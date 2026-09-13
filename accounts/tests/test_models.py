from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User


class UserModelTests(TestCase):
    def test_username_is_unique(self):
        User.objects.create_user(username="unique-user", cohort_number=31)

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="unique-user", cohort_number=31)

    def test_role_defaults_to_member(self):
        user = User.objects.create_user(username="member-user", cohort_number=31)

        self.assertEqual(user.role, User.Role.MEMBER)

    def test_invalid_role_is_rejected(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                username="invalid-role",
                cohort_number=31,
                role="owner",
            )

    def test_database_rejects_invalid_role_without_model_validation(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User(username="database-invalid-role", cohort_number=31, role="owner").save(
                force_insert=True
            )

    def test_non_positive_cohort_number_is_rejected(self):
        for cohort_number in (0, -1):
            with self.subTest(cohort_number=cohort_number), self.assertRaises(ValidationError):
                User.objects.create_user(
                    username=f"invalid-cohort-{cohort_number}",
                    cohort_number=cohort_number,
                )

    def test_database_rejects_non_positive_cohort_number_without_model_validation(self):
        for cohort_number in (0, -1):
            with self.subTest(cohort_number=cohort_number):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    User(
                        username=f"database-invalid-cohort-{cohort_number}",
                        cohort_number=cohort_number,
                    ).save(force_insert=True)

    @patch("accounts.models.timezone.localdate")
    def test_future_cohort_is_rejected_on_creation(self, localdate):
        localdate.return_value = date(2026, 4, 1)

        with self.assertRaisesMessage(ValidationError, "未入学相当"):
            User.objects.create_user(username="future-user", cohort_number=34)

    def test_inactive_user_is_preserved(self):
        user = User.objects.create_user(
            username="inactive-user",
            cohort_number=31,
            is_active=False,
        )

        self.assertFalse(user.is_active)

    def test_manager_creates_regular_user(self):
        user = User.objects.create_user(
            username="regular-user",
            password="test-password-123",
            cohort_number=31,
        )

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("test-password-123"))

    async def test_async_manager_creates_regular_user(self):
        user = await User.objects.acreate_user(
            username="async-regular-user",
            password="test-password-123",
            cohort_number=31,
        )

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("test-password-123"))

    async def test_async_manager_rejects_invalid_role(self):
        with self.assertRaises(ValidationError):
            await User.objects.acreate_user(
                username="async-invalid-role",
                cohort_number=31,
                role="owner",
            )

    @patch("accounts.models.timezone.localdate")
    async def test_async_manager_rejects_future_cohort(self, localdate):
        localdate.return_value = date(2026, 4, 1)

        with self.assertRaisesMessage(ValidationError, "未入学相当"):
            await User.objects.acreate_user(
                username="async-future-user",
                cohort_number=34,
            )

    def test_manager_creates_superuser(self):
        user = User.objects.create_superuser(
            username="root-user",
            password="test-password-123",
            cohort_number=31,
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("test-password-123"))
