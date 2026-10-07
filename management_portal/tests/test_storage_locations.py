"""保管場所管理画面の認可、入力検証、監査記録。"""

import time
from unittest.mock import patch

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from specimens.forms import SpecimenRegistrationForm
from specimens.models import StorageLocation


class StorageLocationManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="location-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(username="location-member", cohort_number=33)
        Authenticator.objects.create(
            user=self.admin,
            type=Authenticator.Type.TOTP,
            data={"test": True},
        )
        self.url = reverse("management:storage_location_list")

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

    def test_admin_creates_root_and_nested_location_with_audit_record(self):
        self.login_admin()

        response = self.client.post(self.url, {"name": "標本室", "note": "1階"})
        self.assertRedirects(response, self.url)
        root = StorageLocation.objects.get(name="標本室")
        self.assertIsNone(root.parent)

        response = self.client.post(self.url, {"name": "棚A", "parent": root.pk, "note": "上段"})
        self.assertRedirects(response, self.url)
        shelf = StorageLocation.objects.get(name="棚A")
        self.assertEqual(shelf.parent, root)
        self.assertEqual(shelf.note, "上段")
        self.assertIn(shelf, SpecimenRegistrationForm().fields["storage_location"].queryset)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.STORAGE_LOCATION_CREATED).count(), 2
        )
        page = self.client.get(self.url)
        self.assertContains(page, "棚A")
        self.assertContains(page, "標本室")
        self.assertIn("no-store", page["Cache-Control"])

    def test_invalid_parent_and_duplicate_sibling_are_rejected(self):
        self.login_admin()
        root = StorageLocation.objects.create(name="標本室")
        StorageLocation.objects.create(name="棚A", parent=root)

        invalid_parent = self.client.post(self.url, {"name": "棚B", "parent": 999999})
        self.assertEqual(invalid_parent.status_code, 200)
        duplicate = self.client.post(self.url, {"name": "棚A", "parent": root.pk})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(StorageLocation.objects.count(), 2)
        self.assertFalse(AuditLog.objects.exists())

    def test_member_anonymous_and_admin_without_mfa_cannot_create(self):
        anonymous = Client()
        self.assertEqual(anonymous.post(self.url, {"name": "標本室"}).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"name": "標本室"}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url, {"name": "標本室"}).status_code, 302)
        self.assertFalse(StorageLocation.objects.exists())

    def test_audit_failure_rolls_back_location_creation(self):
        self.login_admin()
        with patch("management_portal.views.AuditLog.objects.create", side_effect=IntegrityError):
            response = self.client.post(self.url, {"name": "標本室"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(StorageLocation.objects.exists())
        self.assertFalse(AuditLog.objects.exists())
