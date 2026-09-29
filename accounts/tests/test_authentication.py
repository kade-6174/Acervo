from unittest.mock import patch

from allauth.account.adapter import get_adapter
from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import User

CLIENT_IP = "198.51.100.10"
CLIENT_IP_HEADER = {"HTTP_X_ACERVO_CLIENT_IP": CLIENT_IP}


class AuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="login-user",
            password="correct-password-123",
            cohort_number=31,
        )

    def test_login_page_only_contains_username_and_password_fields(self):
        response = self.client.get(reverse("account_login"), **CLIENT_IP_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="login"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'name="email"')
        self.assertNotContains(response, 'name="remember"')
        self.assertNotContains(response, "パスワードをお忘れ")
        self.assertNotContains(response, "新規登録")

    def test_login_page_hides_the_navigation_login_link(self):
        response = self.client.get(reverse("account_login"), **CLIENT_IP_HEADER)

        self.assertNotContains(
            response,
            f'<a class="btn btn-outline-primary" href="{reverse("account_login")}">ログイン</a>',
            html=True,
        )

    def test_username_password_login_succeeds_without_email(self):
        self.assertEqual(self.user.email, "")

        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": "correct-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": "wrong-password"},
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": "correct-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(
            response,
            reverse("account_inactive"),
            fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("account_login"),
            {"login": self.user.username, "password": "correct-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(ALLAUTH_TRUSTED_CLIENT_IP_HEADER=None)
    def test_direct_development_login_uses_remote_addr_without_csrf_rejection(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("account_login"))
        token = page.cookies["csrftoken"].value

        response = client.post(
            reverse("account_login"),
            {
                "csrfmiddlewaretoken": token,
                "login": self.user.username,
                "password": "correct-password-123",
            },
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)

    def test_external_next_url_is_rejected(self):
        response = self.client.post(
            f"{reverse('account_login')}?next=https://attacker.example/path",
            {"login": self.user.username, "password": "correct-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)

    def test_safe_internal_next_url_is_used(self):
        response = self.client.post(
            f"{reverse('account_login')}?next={reverse('core:health')}",
            {"login": self.user.username, "password": "correct-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(response, reverse("core:health"), fetch_redirect_response=False)

    def test_signup_get_and_post_do_not_create_user(self):
        initial_count = User.objects.count()

        get_response = self.client.get(reverse("account_signup"), **CLIENT_IP_HEADER)
        post_response = self.client.post(
            reverse("account_signup"),
            {"username": "self-signup", "password1": "new-password-123"},
            **CLIENT_IP_HEADER,
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(User.objects.count(), initial_count)
        self.assertFalse(User.objects.filter(username="self-signup").exists())

    def test_logout_get_does_not_end_session_but_post_does(self):
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertEqual(get_response.status_code, 200)
        self.assertIn(SESSION_KEY, self.client.session)

        post_response = self.client.post(reverse("account_logout"), **CLIENT_IP_HEADER)
        self.assertRedirects(
            post_response,
            reverse("account_login"),
            fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(ACCOUNT_RATE_LIMITS={"login": "2/s/ip", "login_failed": "100/m/ip"})
    def test_repeated_login_attempts_return_429_and_expire(self):
        login_url = reverse("account_login")
        data = {"login": "missing-user", "password": "wrong-password"}

        with patch("allauth.core.internal.ratelimit.time.time", return_value=1_000):
            self.assertEqual(
                self.client.post(login_url, data, **CLIENT_IP_HEADER).status_code,
                200,
            )
            self.assertEqual(
                self.client.post(login_url, data, **CLIENT_IP_HEADER).status_code,
                200,
            )
            self.assertEqual(
                self.client.post(login_url, data, **CLIENT_IP_HEADER).status_code,
                429,
            )

        with patch("allauth.core.internal.ratelimit.time.time", return_value=1_002):
            self.assertEqual(
                self.client.post(login_url, data, **CLIENT_IP_HEADER).status_code,
                200,
            )


class ClientIpTrustTests(TestCase):
    def test_only_dedicated_client_ip_header_is_used(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_ACERVO_CLIENT_IP="198.51.100.20",
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )

        self.assertEqual(get_adapter().get_client_ip(request), "198.51.100.20")

    def test_forwarded_for_is_not_a_fallback(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )

        with self.assertRaises(PermissionDenied):
            get_adapter().get_client_ip(request)
