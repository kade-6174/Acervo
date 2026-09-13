from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import User


class BootstrapAdminCommandTests(TestCase):
    def test_command_creates_only_application_admin_and_prints_password_once(self):
        output = StringIO()

        call_command(
            "bootstrap_admin",
            username="initial-admin",
            cohort_number=31,
            stdout=output,
        )

        user = User.objects.get(username="initial-admin")
        temporary_password = output.getvalue().strip().removeprefix("一時パスワード: ")
        self.assertTrue(temporary_password)
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(temporary_password))

    def test_existing_username_is_not_modified_and_no_secret_is_printed(self):
        user = User.objects.create_user(
            username="existing-user",
            password="existing-password-123",
            cohort_number=31,
        )
        original_password_hash = user.password
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_admin",
                username=user.username,
                cohort_number=30,
                stdout=output,
            )

        user.refresh_from_db()
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(user.password, original_password_hash)
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertEqual(user.cohort_number, 31)

    def test_existing_active_admin_prevents_additional_admin(self):
        existing_admin = User.objects.create_user(
            username="existing-admin",
            password="existing-password-123",
            cohort_number=31,
            role=User.Role.ADMIN,
        )
        original_password_hash = existing_admin.password
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_admin",
                username="additional-admin",
                cohort_number=31,
                stdout=output,
            )

        existing_admin.refresh_from_db()
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(existing_admin.password, original_password_hash)
        self.assertFalse(User.objects.filter(username="additional-admin").exists())

    def test_invalid_cohort_prints_no_secret_and_creates_nothing(self):
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command(
                "bootstrap_admin",
                username="invalid-admin",
                cohort_number=0,
                stdout=output,
            )

        self.assertEqual(output.getvalue(), "")
        self.assertFalse(User.objects.filter(username="invalid-admin").exists())
