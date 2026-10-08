"""管理者向け標本一覧の認可と絞込み。"""

import time

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from specimens.models import Specimen, StorageLocation, Taxon


class SpecimenManagementListTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="specimen-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(username="specimen-member", cohort_number=33)
        Authenticator.objects.create(
            user=self.admin, type=Authenticator.Type.TOTP, data={"test": True}
        )
        self.url = reverse("management:specimen_management_list")

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

    def test_admin_can_filter_by_code_name_and_status(self):
        location = StorageLocation.objects.create(name="棚A")
        taxon = Taxon.objects.create(japanese_name="アゲハ", rank="species")
        first = Specimen.objects.create(
            specimen_code="TEST-000001",
            taxon=taxon,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            status=Specimen.Status.IN_COLLECTION,
            storage_location=location,
            created_by=self.member,
        )
        Specimen.objects.create(
            specimen_code="TEST-000002",
            identification_text="未同定",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            status=Specimen.Status.LOST,
            created_by=self.member,
        )
        self.login_admin()
        response = self.client.get(self.url, {"q": "アゲハ", "status": "in_collection"})
        self.assertContains(response, "TEST-000001")
        self.assertNotContains(response, "TEST-000002")
        self.assertContains(response, reverse("specimens:detail", args=[first.detail_uuid]))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_anonymous_member_and_admin_without_mfa_cannot_open_management_list(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 302)
