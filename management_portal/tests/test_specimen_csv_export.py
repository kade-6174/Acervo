import csv
import time
from io import StringIO

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from specimens.models import Specimen
from specimens.services import create_specimen


class SpecimenCSVExportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="csv-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(username="csv-member", cohort_number=33)
        Authenticator.objects.create(
            user=self.admin,
            type=Authenticator.Type.TOTP,
            data={"test": True},
        )
        self.specimen = create_specimen(
            created_by=self.member,
            identification_text='=HYPERLINK("https://example.test")',
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            collected_place=" @SUM(1,1)",
            collector="+danger",
            note="-danger",
        )

    @property
    def url(self):
        return reverse("management:specimen_csv_export")

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

    def test_member_cannot_export_csv(self):
        client = Client()
        client.force_login(self.member)

        response = client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_export_records_audit_and_neutralizes_formula_cells(self):
        self.login_admin()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], "標本番号")
        self.assertEqual(rows[1][0], self.specimen.specimen_code)
        self.assertEqual(rows[1][3], '\'=HYPERLINK("https://example.test")')
        self.assertEqual(rows[1][7], "' @SUM(1,1)")
        self.assertEqual(rows[1][8], "'+danger")
        self.assertEqual(rows[1][10], "'-danger")
        audit = AuditLog.objects.get(action=AuditLog.Action.SPECIMEN_CSV_EXPORTED)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.target_username, "")
