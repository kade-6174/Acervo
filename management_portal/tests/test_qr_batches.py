"""Phase 9のQRラベル一括発行・印刷の管理画面テスト。"""

import time
from unittest.mock import patch

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from specimens.models import QRBatch, QRLabel, SpecimenSequence
from specimens.services import create_qr_batch, retire_qr_label


class QRBatchManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="qr-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(username="qr-member", cohort_number=33)
        Authenticator.objects.create(
            user=self.admin,
            type=Authenticator.Type.TOTP,
            data={"test": True},
        )
        self.list_url = reverse("management:qr_batch_list")

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

    def test_member_and_unauthenticated_user_cannot_issue_or_download(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(self.list_url).status_code, 302)
        self.assertEqual(anonymous.post(self.list_url, {"requested_count": 1}).status_code, 302)
        self.client.force_login(self.member)
        pdf_url = reverse("management:qr_batch_pdf", kwargs={"batch_id": 1})
        labels_url = reverse("management:qr_batch_labels", kwargs={"batch_id": 1})
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.list_url, {"requested_count": 1, "confirmed": "on"}).status_code,
            403,
        )
        self.assertEqual(self.client.get(pdf_url).status_code, 403)
        self.assertEqual(self.client.get(labels_url).status_code, 403)
        self.assertFalse(QRBatch.objects.exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_admin_without_session_mfa_cannot_issue(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.list_url, {"requested_count": 1, "confirmed": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(QRBatch.objects.exists())

    def test_valid_issue_creates_unused_labels_without_specimen_number(self):
        self.login_admin()
        response = self.client.post(
            self.list_url,
            {"requested_count": 2, "note": "春の作業", "confirmed": "on"},
        )
        self.assertRedirects(response, self.list_url)
        batch = QRBatch.objects.get()
        labels = list(QRLabel.objects.filter(batch=batch))
        self.assertEqual(batch.requested_count, 2)
        self.assertEqual(batch.note, "春の作業")
        self.assertEqual(len(labels), 2)
        self.assertTrue(all(label.status == QRLabel.Status.UNUSED for label in labels))
        self.assertFalse(SpecimenSequence.objects.exists())
        audit = AuditLog.objects.get(action=AuditLog.Action.QR_BATCH_CREATED)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.target_username, "")
        page = self.client.get(self.list_url)
        self.assertContains(page, "春の作業")
        self.assertNotContains(page, str(labels[0].token))
        self.assertIn("no-store", page["Cache-Control"])

    def test_invalid_counts_and_missing_confirmation_create_nothing(self):
        self.login_admin()
        for payload in (
            {"requested_count": 0, "confirmed": "on"},
            {"requested_count": 101, "confirmed": "on"},
            {"requested_count": "no", "confirmed": "on"},
            {"requested_count": 1},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(self.list_url, payload)
                self.assertEqual(response.status_code, 200)
        self.assertFalse(QRBatch.objects.exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_issue_button_starts_disabled_until_confirmation_is_checked(self):
        self.login_admin()

        response = self.client.get(self.list_url)

        self.assertContains(
            response,
            '<button id="qr-batch-submit" class="btn btn-dark" type="submit" disabled>',
            html=False,
        )
        self.assertContains(
            response,
            "submitButton.disabled = !confirmedCheckbox.checked;",
            html=False,
        )

    def test_audit_failure_rolls_back_issue(self):
        self.login_admin()
        with patch("management_portal.views.AuditLog.objects.create", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.client.post(self.list_url, {"requested_count": 2, "confirmed": "on"})
        self.assertFalse(QRBatch.objects.exists())
        self.assertFalse(QRLabel.objects.exists())

    def test_pdf_download_records_print_and_audit_but_omits_retired(self):
        self.login_admin()
        batch = create_qr_batch(requested_count=2, created_by=self.admin)
        labels = list(QRLabel.objects.filter(batch_id=batch.batch_id))
        retire_qr_label(token=labels[1].token)
        pdf_url = reverse("management:qr_batch_pdf", kwargs={"batch_id": batch.batch_id})

        response = self.client.get(pdf_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("no-store", response["Cache-Control"])
        labels[0].refresh_from_db()
        labels[1].refresh_from_db()
        self.assertEqual(labels[0].print_count, 1)
        self.assertIsNotNone(labels[0].last_printed_at)
        self.assertEqual(labels[1].print_count, 0)
        audit = AuditLog.objects.get(action=AuditLog.Action.QR_BATCH_PDF_EXPORTED)
        self.assertEqual(audit.actor, self.admin)
        self.assertNotIn(str(labels[0].token), audit.actor_username)

    def test_missing_or_fully_retired_batch_does_not_audit_pdf(self):
        self.login_admin()
        batch = create_qr_batch(requested_count=1, created_by=self.admin)
        label = QRLabel.objects.get(batch_id=batch.batch_id)
        retire_qr_label(token=label.token)
        for batch_id in (batch.batch_id, batch.batch_id + 1000):
            with self.subTest(batch_id=batch_id):
                response = self.client.get(
                    reverse("management:qr_batch_pdf", kwargs={"batch_id": batch_id})
                )
                self.assertEqual(response.status_code, 404)
        self.assertFalse(AuditLog.objects.exists())

    def test_pdf_generation_failure_does_not_mark_printed(self):
        self.login_admin()
        batch = create_qr_batch(requested_count=1, created_by=self.admin)
        with patch("management_portal.views.build_qr_labels_pdf", side_effect=OSError):
            with self.assertRaises(OSError):
                self.client.get(
                    reverse("management:qr_batch_pdf", kwargs={"batch_id": batch.batch_id})
                )
        self.assertEqual(QRLabel.objects.get(batch_id=batch.batch_id).print_count, 0)
        self.assertFalse(AuditLog.objects.exists())

    def test_admin_can_retire_a_label_only_after_reconfirming_its_number(self):
        self.login_admin()
        batch = create_qr_batch(requested_count=1, created_by=self.admin)
        label = QRLabel.objects.get(batch_id=batch.batch_id)
        labels_url = reverse("management:qr_batch_labels", kwargs={"batch_id": batch.batch_id})
        retire_url = reverse(
            "management:qr_label_retire",
            kwargs={"batch_id": batch.batch_id, "label_id": label.pk},
        )

        labels = self.client.get(labels_url)
        self.assertContains(labels, f"#{label.pk}")
        self.assertContains(labels, retire_url)
        self.assertNotContains(labels, str(label.token))

        response = self.client.post(retire_url, {"confirmed": "on", "label_id": label.pk + 1})
        self.assertEqual(response.status_code, 200)
        label.refresh_from_db()
        self.assertEqual(label.status, QRLabel.Status.UNUSED)

        response = self.client.post(retire_url, {"confirmed": "on", "label_id": label.pk})
        self.assertRedirects(response, labels_url)
        label.refresh_from_db()
        self.assertEqual(label.status, QRLabel.Status.RETIRED)
        self.assertIsNotNone(label.retired_at)
        audit = AuditLog.objects.get(action=AuditLog.Action.QR_LABEL_RETIRED)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.target_username, f"QRラベル #{label.pk}")

    def test_audit_failure_rolls_back_qr_retirement(self):
        self.login_admin()
        batch = create_qr_batch(requested_count=1, created_by=self.admin)
        label = QRLabel.objects.get(batch_id=batch.batch_id)
        retire_url = reverse(
            "management:qr_label_retire",
            kwargs={"batch_id": batch.batch_id, "label_id": label.pk},
        )

        with patch("management_portal.views.AuditLog.objects.create", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.client.post(retire_url, {"confirmed": "on", "label_id": label.pk})

        label.refresh_from_db()
        self.assertEqual(label.status, QRLabel.Status.UNUSED)
        self.assertIsNone(label.retired_at)
