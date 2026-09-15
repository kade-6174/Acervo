from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from management_portal.middleware import ManagementAccessMiddleware

CLIENT_IP_HEADER = {"HTTP_X_ACERVO_CLIENT_IP": "198.51.100.220"}


class ManagementPortalTests(TestCase):
    def create_user(self, username, **extra_fields):
        return User.objects.create_user(
            username=username,
            password="test-password-123",
            cohort_number=extra_fields.pop("cohort_number", 31),
            **extra_fields,
        )

    def add_authenticator(self, user, authenticator_type):
        return Authenticator.objects.create(
            user=user,
            type=authenticator_type,
            data={"test": True},
        )

    def record_mfa(self, user, authenticator_type, **extra_data):
        session = self.client.session
        request = RequestFactory().get("/")
        request.session = session
        request.user = user
        record_authentication(
            request,
            user,
            "mfa",
            type=authenticator_type,
            **extra_data,
        )
        session.save()

    def assert_never_cached(self, response):
        cache_control = response.headers["Cache-Control"]
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("private", cache_control)

    def login_allowed_admin(self, username="allowed-admin", session_type=Authenticator.Type.TOTP):
        user = self.create_user(username, role=User.Role.ADMIN)
        authenticator = self.add_authenticator(user, Authenticator.Type.TOTP)
        self.client.force_login(user)
        self.record_mfa(user, session_type)
        return user, authenticator

    def test_anonymous_redirect_is_internal_keeps_next_and_is_never_cached(self):
        response = self.client.get(reverse("management:index"))

        self.assertEqual(response.status_code, 302)
        location = urlparse(response.headers["Location"])
        self.assertEqual(
            (location.scheme, location.netloc, location.path), ("", "", "/accounts/login/")
        )
        self.assertEqual(parse_qs(location.query)["next"], ["/management/"])
        self.assert_never_cached(response)

        for query in ("next=//attacker.example/", "next=https%3A%2F%2Fattacker.example%2F"):
            with self.subTest(query=query):
                attempted = self.client.get(f"/management/?{query}")
                parsed = urlparse(attempted.headers["Location"])
                self.assertEqual(
                    (parsed.scheme, parsed.netloc, parsed.path), ("", "", "/accounts/login/")
                )
                self.assertTrue(parse_qs(parsed.query)["next"][0].startswith("/management/"))

    def test_members_are_forbidden_for_every_method_and_direct_subpath(self):
        members = (
            self.create_user("member", role=User.Role.MEMBER),
            self.create_user("staff-member", role=User.Role.MEMBER, is_staff=True),
            self.create_user(
                "superuser-member",
                role=User.Role.MEMBER,
                is_staff=True,
                is_superuser=True,
            ),
            self.create_user("graduate-member", role=User.Role.MEMBER, cohort_number=30),
        )
        for member in members:
            with self.subTest(username=member.username):
                self.client.force_login(member)
                for method in ("get", "post", "put", "patch", "delete"):
                    response = getattr(self.client, method)("/management/future/")
                    self.assertEqual(response.status_code, 403)
                    self.assert_never_cached(response)
                page = self.client.get(reverse("management:index"))
                self.assertContains(
                    page, "この管理画面を利用する権限がありません。", status_code=403
                )
                self.assertNotContains(page, "MFA", status_code=403)
                self.assertNotContains(page, "管理者一覧", status_code=403)
                self.assertNotContains(page, "パスキー", status_code=403)
                self.assertEqual(self.client.get("/management").status_code, 403)

    def test_denied_post_does_not_call_view_or_store_body(self):
        member = self.create_user("post-member", role=User.Role.MEMBER)
        request = RequestFactory().post(
            "/management/future/",
            {"sensitive-input": "must-not-be-replayed"},
        )
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = member
        request._messages = FallbackStorage(request)
        get_response = Mock(return_value=HttpResponse("view executed"))

        response = ManagementAccessMiddleware(get_response)(request)

        self.assertEqual(response.status_code, 403)
        get_response.assert_not_called()
        self.assertNotIn("must-not-be-replayed", repr(dict(request.session)))
        self.assertNotIn("account_reauthentication_state", request.session)

    def test_initial_password_change_redirects_without_loop(self):
        admin = self.create_user(
            "initial-password-admin",
            role=User.Role.ADMIN,
            must_change_password=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("management:index"))

        self.assertRedirects(
            response,
            reverse("account_change_password"),
            fetch_redirect_response=False,
        )
        self.assert_never_cached(response)
        self.assertEqual(self.client.get(reverse("account_change_password")).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse("mfa_index")),
            reverse("account_change_password"),
            fetch_redirect_response=False,
        )

    def test_missing_primary_mfa_redirects_with_japanese_guidance(self):
        admin = self.create_user("no-primary-admin", role=User.Role.ADMIN)
        self.client.force_login(admin)

        response = self.client.get(reverse("management:index"))

        self.assertRedirects(response, reverse("mfa_index"), fetch_redirect_response=False)
        self.assert_never_cached(response)
        guidance = self.client.get(reverse("mfa_index"))
        self.assertContains(
            guidance,
            "管理機能を利用するには、パスキーまたはTOTPの設定が必要です。",
        )

        recovery_only = self.create_user("recovery-only-admin", role=User.Role.ADMIN)
        self.add_authenticator(recovery_only, Authenticator.Type.RECOVERY_CODES)
        self.client.force_login(recovery_only)
        self.assertRedirects(
            self.client.get(reverse("management:index")),
            reverse("mfa_index"),
            fetch_redirect_response=False,
        )

    def test_registering_primary_mfa_advances_to_matching_mfa_reauthentication(self):
        for label, authenticator_type, expected_url in (
            ("totp", Authenticator.Type.TOTP, reverse("mfa_reauthenticate")),
            ("webauthn", Authenticator.Type.WEBAUTHN, reverse("mfa_reauthenticate_webauthn")),
        ):
            with self.subTest(label=label):
                admin = self.create_user(f"registered-{label}", role=User.Role.ADMIN)
                self.client.force_login(admin)
                self.assertRedirects(
                    self.client.get(reverse("management:index")),
                    reverse("mfa_index"),
                    fetch_redirect_response=False,
                )
                self.add_authenticator(admin, authenticator_type)

                response = self.client.get(reverse("management:index"))

                parsed = urlparse(response.headers["Location"])
                self.assertEqual(parsed.path, expected_url)
                self.assertEqual(parse_qs(parsed.query)["next"], ["/management/"])
                self.assert_never_cached(response)
                self.client.logout()

    def test_session_mfa_redirect_is_safe_and_does_not_replay_post(self):
        admin = self.create_user("session-required-admin", role=User.Role.ADMIN)
        self.add_authenticator(admin, Authenticator.Type.TOTP)
        self.client.force_login(admin)

        response = self.client.post(
            "/management/?next=//attacker.example/",
            {"operation": "must-not-be-replayed"},
        )

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.headers["Location"])
        self.assertEqual(
            (parsed.scheme, parsed.netloc, parsed.path), ("", "", reverse("mfa_reauthenticate"))
        )
        self.assertEqual(
            parse_qs(parsed.query)["next"],
            ["/management/?next=//attacker.example/"],
        )
        self.assertNotIn("must-not-be-replayed", repr(dict(self.client.session)))
        self.assertNotIn("account_reauthentication_state", self.client.session)
        self.assert_never_cached(response)

        self.record_mfa(admin, Authenticator.Type.TOTP, reauthenticated=True)
        resumed = self.client.get(parse_qs(parsed.query)["next"][0])
        self.assertEqual(resumed.status_code, 200)
        self.assertNotContains(resumed, "must-not-be-replayed")

    def test_totp_reauthentication_returns_to_management_with_get(self):
        admin = self.create_user("totp-reauth-admin", role=User.Role.ADMIN)
        secret = "JBSWY3DPEHPK3PXP"
        TOTP.activate(admin, secret)
        self.client.force_login(admin)
        denied = self.client.get(reverse("management:index"), **CLIENT_IP_HEADER)
        code = format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))

        reauthenticated = self.client.post(
            denied.headers["Location"],
            {"code": code},
            **CLIENT_IP_HEADER,
        )

        self.assertRedirects(
            reauthenticated,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.get(
                reauthenticated.headers["Location"],
                **CLIENT_IP_HEADER,
            ).status_code,
            200,
        )

    def test_supported_session_mfa_records_allow_management_top(self):
        cases = (
            ("totp", Authenticator.Type.TOTP, {}),
            ("webauthn-second-factor", Authenticator.Type.WEBAUTHN, {}),
            ("passwordless-passkey", Authenticator.Type.WEBAUTHN, {"passwordless": True}),
            ("recovery-code", Authenticator.Type.RECOVERY_CODES, {}),
            ("mfa-reauthentication", Authenticator.Type.TOTP, {"reauthenticated": True}),
        )
        for label, session_type, extra_data in cases:
            with self.subTest(label=label):
                admin = self.create_user(f"allowed-{label}", role=User.Role.ADMIN)
                self.add_authenticator(admin, Authenticator.Type.TOTP)
                self.client.force_login(admin)
                self.record_mfa(admin, session_type, **extra_data)

                response = self.client.get(reverse("management:index"))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, admin.username)
                self.assertContains(response, reverse("mfa_index"))
                self.assertContains(response, reverse("core:home"))
                self.assertContains(response, reverse("account_logout"))
                self.assertContains(response, "MFAリセット")
                self.assertNotContains(response, "/admin/")
                self.assert_never_cached(response)
                self.client.logout()

    def test_allowed_slashless_post_redirects_as_get_without_body_storage(self):
        self.login_allowed_admin("slashless-admin")

        response = self.client.post(
            "/management",
            {"operation": "must-not-be-replayed"},
        )

        self.assertRedirects(
            response,
            reverse("management:index"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("must-not-be-replayed", repr(dict(self.client.session)))
        self.assert_never_cached(response)

    def test_dynamic_database_and_session_changes_are_enforced(self):
        scenarios = (
            ("demoted", {"role": User.Role.MEMBER}, 403, None),
            ("inactive", {"is_active": False}, None, None),
            ("primary-removed", {}, 302, reverse("mfa_index")),
            (
                "password-change-required",
                {"must_change_password": True},
                302,
                reverse("account_change_password"),
            ),
        )
        for label, user_changes, expected_status, expected_location in scenarios:
            with self.subTest(label=label):
                user, authenticator = self.login_allowed_admin(f"dynamic-{label}")
                if label == "primary-removed":
                    authenticator.delete()
                else:
                    User.objects.filter(pk=user.pk).update(**user_changes)

                response = self.client.get(reverse("management:index"))

                if expected_status is None:
                    self.assertIn(response.status_code, (302, 403))
                else:
                    self.assertEqual(response.status_code, expected_status)
                if expected_location:
                    self.assertEqual(response.headers["Location"], expected_location)
                self.assert_never_cached(response)
                self.client.logout()

        self.login_allowed_admin("logout-dynamic")
        self.client.post(reverse("account_logout"))
        logged_out = self.client.get(reverse("management:index"))
        self.assertRedirects(
            logged_out,
            f"{reverse('account_login')}?next=%2Fmanagement%2F",
            fetch_redirect_response=False,
        )

    def test_scope_navigation_and_admin_separation(self):
        member = self.create_user("ordinary-member", role=User.Role.MEMBER)
        self.client.force_login(member)

        home = self.client.get(reverse("core:home"))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, reverse("mfa_index"))
        self.assertNotContains(home, reverse("management:index"))
        self.assertEqual(self.client.get(reverse("mfa_index")).status_code, 200)
        self.assertEqual(self.client.get("/management/future/").status_code, 403)

        admin, _authenticator = self.login_allowed_admin("navigation-admin")
        admin_home = self.client.get(reverse("core:home"))
        self.assertContains(admin_home, reverse("management:index"))
        self.assertNotEqual(reverse("management:index"), "/admin/")
        self.assertNotContains(self.client.get(reverse("management:index")), "/admin/")
