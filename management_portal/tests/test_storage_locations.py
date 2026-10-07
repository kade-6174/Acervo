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
from specimens.models import Specimen, StorageLocation


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

    def test_edit_moves_subtree_and_records_audit_without_secret_values(self):
        self.login_admin()
        original = StorageLocation.objects.create(name="標本室")
        child = StorageLocation.objects.create(name="棚A", parent=original)
        other = StorageLocation.objects.create(name="別室")
        url = reverse("management:storage_location_edit", args=[original.pk])

        response = self.client.post(
            url, {"name": "新標本室", "parent": other.pk, "note": "移設済み"}
        )
        self.assertRedirects(response, self.url)
        original.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(
            (original.name, original.parent, original.note), ("新標本室", other, "移設済み")
        )
        self.assertEqual(child.parent, original)
        audit = AuditLog.objects.get(action=AuditLog.Action.STORAGE_LOCATION_UPDATED)
        self.assertEqual(audit.target_username, f"保管場所 #{original.pk}")
        self.assertNotIn("移設済み", audit.target_username)

    def test_edit_rejects_descendant_parent_duplicate_sibling_and_invalid_parent(self):
        self.login_admin()
        root = StorageLocation.objects.create(name="標本室")
        child = StorageLocation.objects.create(name="棚A", parent=root)
        StorageLocation.objects.create(name="棚B", parent=root)
        url = reverse("management:storage_location_edit", args=[root.pk])
        cycle = self.client.post(url, {"name": "標本室", "parent": child.pk})
        self.assertContains(cycle, "下位の場所を上位にはできません")
        duplicate = self.client.post(
            reverse("management:storage_location_edit", args=[child.pk]),
            {"name": "棚B", "parent": root.pk},
        )
        self.assertEqual(duplicate.status_code, 200)
        invalid = self.client.post(url, {"name": "標本室", "parent": 999999})
        self.assertEqual(invalid.status_code, 200)
        root.refresh_from_db()
        self.assertIsNone(root.parent)
        self.assertFalse(AuditLog.objects.exists())

    def test_delete_requires_name_confirmation_and_does_not_remove_referenced_location(self):
        self.login_admin()
        root = StorageLocation.objects.create(name="標本室")
        child = StorageLocation.objects.create(name="棚A", parent=root)
        url = reverse("management:storage_location_delete", args=[root.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(StorageLocation.objects.count(), 2)
        wrong = self.client.post(url, {"location_name": "別室", "confirmed": "on"})
        self.assertContains(wrong, "名称が一致しません")
        blocked = self.client.post(url, {"location_name": "標本室", "confirmed": "on"})
        self.assertContains(blocked, "使われているため削除できません")
        self.assertTrue(StorageLocation.objects.filter(pk=root.pk).exists())
        self.assertFalse(AuditLog.objects.exists())

        specimen = Specimen.objects.create(
            specimen_code="TEST-000001",
            identification_text="未同定",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            created_by=self.member,
            storage_location=child,
        )
        child_url = reverse("management:storage_location_delete", args=[child.pk])
        referenced = self.client.post(child_url, {"location_name": "棚A", "confirmed": "on"})
        self.assertContains(referenced, "使われているため削除できません")
        self.assertTrue(Specimen.objects.filter(pk=specimen.pk).exists())

    def test_delete_unused_location_records_audit_and_rolls_back_if_audit_fails(self):
        self.login_admin()
        location = StorageLocation.objects.create(name="空の箱")
        url = reverse("management:storage_location_delete", args=[location.pk])
        data = {"location_name": "空の箱", "confirmed": "on"}
        with patch("management_portal.views.AuditLog.objects.create", side_effect=IntegrityError):
            failure = self.client.post(url, data)
        self.assertEqual(failure.status_code, 200)
        self.assertTrue(StorageLocation.objects.filter(pk=location.pk).exists())
        self.assertFalse(AuditLog.objects.exists())
        success = self.client.post(url, data)
        self.assertRedirects(success, self.url)
        self.assertFalse(StorageLocation.objects.filter(pk=location.pk).exists())
        self.assertEqual(AuditLog.objects.get().action, AuditLog.Action.STORAGE_LOCATION_DELETED)

    def test_edit_and_delete_reject_non_admin_and_mfa_incomplete(self):
        location = StorageLocation.objects.create(name="標本室")
        edit_url = reverse("management:storage_location_edit", args=[location.pk])
        delete_url = reverse("management:storage_location_delete", args=[location.pk])
        for url in (edit_url, delete_url):
            self.client.force_login(self.member)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(url).status_code, 302)
            self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.assertTrue(StorageLocation.objects.filter(pk=location.pk).exists())

    def test_settings_summary_is_admin_only_and_excludes_secret_configuration(self):
        url = reverse("management:site_settings")
        self.login_admin()
        response = self.client.get(url)
        self.assertContains(response, "導入先設定")
        self.assertContains(response, "サイト表示名")
        self.assertNotContains(response, "DJANGO_SECRET_KEY")
        self.assertNotContains(response, "MFA_FERNET")
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 403)
