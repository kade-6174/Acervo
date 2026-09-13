from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from accounts.services import (
    create_user_with_temporary_password,
    reissue_temporary_password,
)

from .test_authentication import CLIENT_IP_HEADER


class UserProvisioningServiceTests(TestCase):
    def test_create_user_hashes_one_time_password_and_requires_change(self):
        result = create_user_with_temporary_password(
            username="provisioned-user",
            cohort_number=31,
            role=User.Role.MEMBER,
        )

        result.user.refresh_from_db()
        self.assertTrue(result.user.check_password(result.temporary_password))
        self.assertNotEqual(result.user.password, result.temporary_password)
        self.assertTrue(result.user.must_change_password)
        self.assertNotIn("temporary_password", {field.name for field in User._meta.fields})

    @patch(
        "accounts.services.password_validation.validate_password",
        side_effect=[ValidationError("不適合"), None],
    )
    @patch("accounts.services.secrets.token_urlsafe", side_effect=["rejected", "accepted"])
    def test_password_generation_retries_after_validator_rejection(
        self, token_urlsafe, validate_password
    ):
        result = create_user_with_temporary_password(
            username="retry-user",
            cohort_number=31,
        )

        self.assertEqual(result.temporary_password, "accepted")
        self.assertEqual(token_urlsafe.call_count, 2)
        self.assertEqual(validate_password.call_count, 2)

    def test_invalid_user_creation_is_rolled_back(self):
        with self.assertRaises(ValidationError):
            create_user_with_temporary_password(
                username="invalid-role-user",
                cohort_number=31,
                role="owner",
            )

        self.assertFalse(User.objects.filter(username="invalid-role-user").exists())

    def test_reissue_replaces_password_sets_flag_and_invalidates_existing_session(self):
        user = User.objects.create_user(
            username="reissue-user",
            password="old-password-123",
            cohort_number=31,
        )
        existing_session = Client()
        self.assertTrue(existing_session.login(username=user.username, password="old-password-123"))

        result = reissue_temporary_password(user_id=user.pk)

        user.refresh_from_db()
        self.assertFalse(user.check_password("old-password-123"))
        self.assertTrue(user.check_password(result.temporary_password))
        self.assertTrue(user.must_change_password)
        response = existing_session.get(reverse("core:home"), **CLIENT_IP_HEADER)
        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('core:home')}",
            fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, existing_session.session)
