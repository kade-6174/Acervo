from django.contrib.auth import SESSION_KEY
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .test_authentication import CLIENT_IP_HEADER


class InitialPasswordChangeGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="initial-password-user",
            password="temporary-password-123",
            cohort_number=31,
            must_change_password=True,
        )
        self.client.force_login(self.user)

    def test_gate_blocks_direct_get_and_post_to_normal_view(self):
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(reverse("core:home"), **CLIENT_IP_HEADER)
                self.assertRedirects(
                    response,
                    reverse("account_change_password"),
                    fetch_redirect_response=False,
                )

    def test_health_check_is_allowed(self):
        response = self.client.get(reverse("core:health"), **CLIENT_IP_HEADER)

        self.assertEqual(response.status_code, 200)

    def test_login_next_cannot_bypass_gate(self):
        self.client.logout()
        response = self.client.post(
            f"{reverse('account_login')}?next={reverse('core:home')}",
            {"login": self.user.username, "password": "temporary-password-123"},
            follow=True,
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(response.redirect_chain[-1][0], reverse("account_change_password"))
        self.assertEqual(response.status_code, 200)

    def test_invalid_password_change_keeps_flag_and_session(self):
        response = self.client.post(
            reverse("account_change_password"),
            {
                "oldpassword": "wrong-password",
                "password1": "new-secure-password-123",
                "password2": "new-secure-password-123",
            },
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_successful_password_change_clears_flag_and_preserves_session(self):
        response = self.client.post(
            reverse("account_change_password"),
            {
                "oldpassword": "temporary-password-123",
                "password1": "new-secure-password-123",
                "password2": "new-secure-password-123",
            },
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("new-secure-password-123"))
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(
            self.client.get(reverse("core:home"), **CLIENT_IP_HEADER).status_code,
            200,
        )

    def test_logout_post_is_allowed_by_gate(self):
        response = self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)

        self.assertRedirects(response, reverse("account_login"), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
