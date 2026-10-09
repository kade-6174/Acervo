"""管理者向け監査ログの検索とページ送り。"""

import time
from datetime import timedelta

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog


class AuditLogListTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="audit-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(username="audit-member", cohort_number=33)
        Authenticator.objects.create(
            user=self.admin, type=Authenticator.Type.TOTP, data={"test": True}
        )
        self.url = reverse("management:audit_log_list")

    def login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {
                "method": "mfa",
                "type": Authenticator.Type.TOTP,
                "reauthenticated": True,
                "at": time.time(),
            }
        ]
        session.save()

    def create_log(self, username, *, action=AuditLog.Action.USER_CREATED, channel=None):
        return AuditLog.objects.create(
            action=action,
            channel=channel or AuditLog.Channel.MANAGEMENT_UI,
            actor=self.admin,
            actor_username=username,
            target_username="",
        )

    def test_all_records_remain_accessible_by_page(self):
        for number in range(55):
            self.create_log(f"operator-{number:02d}")
        self.login_admin()

        first = self.client.get(self.url)
        second = self.client.get(self.url, {"page": "2"})

        self.assertEqual(len(first.context["page"]), 50)
        self.assertEqual(len(second.context["page"]), 5)
        self.assertContains(first, "?page=2")
        self.assertContains(second, "operator-00")
        self.assertNotContains(first, "operator-00")
        self.assertIn("no-store", first["Cache-Control"])

    def test_filters_by_action_channel_actor_and_dates(self):
        matching = self.create_log("sakura-admin")
        other_action = self.create_log("sakura-admin", action=AuditLog.Action.QR_BATCH_CREATED)
        self.create_log("other-admin")
        self.create_log("sakura-admin", channel=AuditLog.Channel.MANAGEMENT_COMMAND)
        old = self.create_log("sakura-admin")
        AuditLog.objects.filter(pk=old.pk).update(occurred_at=timezone.now() - timedelta(days=3))
        self.login_admin()

        response = self.client.get(
            self.url,
            {
                "action": AuditLog.Action.USER_CREATED,
                "channel": AuditLog.Channel.MANAGEMENT_UI,
                "actor_username": "SAKURA",
                "from_date": timezone.localdate().isoformat(),
                "to_date": timezone.localdate().isoformat(),
            },
        )

        self.assertEqual([log.pk for log in response.context["page"]], [matching.pk])
        self.assertNotEqual(matching.pk, other_action.pk)
        self.assertIn("action=user_created", response.context["page_query"])
        self.assertIn("actor_username=SAKURA", response.context["page_query"])

    def test_invalid_filters_show_errors_without_unfiltered_results(self):
        self.create_log("operator")
        self.login_admin()

        invalid_action = self.client.get(self.url, {"action": "unknown"})
        invalid_range = self.client.get(
            self.url, {"from_date": "2026-10-10", "to_date": "2026-10-09"}
        )

        self.assertEqual(len(invalid_action.context["page"]), 0)
        self.assertIn("action", invalid_action.context["form"].errors)
        self.assertEqual(len(invalid_range.context["page"]), 0)
        self.assertIn("to_date", invalid_range.context["form"].errors)

    def test_management_gate_and_get_only(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.login_admin()
        self.assertEqual(self.client.post(self.url).status_code, 405)
