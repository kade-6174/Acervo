"""標本の無効化・完全削除と公開経路の遮断。"""

import time
from unittest.mock import patch

from allauth.account.authentication import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.mfa.models import Authenticator
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditLog
from specimens.models import (
    PendingPhotoDeletion,
    QRBatch,
    QRLabel,
    Specimen,
    SpecimenEvent,
    SpecimenPhoto,
    SpecimenSequence,
)
from specimens.services import (
    SpecimenServiceError,
    create_specimen,
    delete_invalidated_specimen,
    invalidate_specimen,
    record_specimen_event,
    retry_pending_photo_deletions,
)


class SpecimenRetirementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="retirement-admin",
            password="SecurePassword123!",
            role=User.Role.ADMIN,
            cohort_number=33,
        )
        self.member = User.objects.create_user(
            username="retirement-member", password="SecurePassword123!", cohort_number=33
        )
        Authenticator.objects.create(
            user=self.admin, type=Authenticator.Type.TOTP, data={"test": True}
        )
        self.specimen = create_specimen(
            created_by=self.member,
            identification_text="未同定",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
        )
        self.batch = QRBatch.objects.create(requested_count=1, created_by=self.admin)
        self.label = QRLabel.objects.create(
            batch=self.batch, status=QRLabel.Status.ASSIGNED, specimen=self.specimen
        )
        self.detail_url = reverse("specimens:detail", args=[self.specimen.detail_uuid])
        self.invalidate_url = reverse(
            "management:specimen_invalidate", args=[self.specimen.detail_uuid]
        )
        self.delete_url = reverse("management:specimen_delete", args=[self.specimen.detail_uuid])

    def login_admin(self, *, recent=True):
        self.client.force_login(self.admin)
        session = self.client.session
        session[AUTHENTICATION_METHODS_SESSION_KEY] = [
            {
                "method": "mfa",
                "type": Authenticator.Type.TOTP,
                "reauthenticated": recent,
                "at": time.time(),
            }
        ]
        session.save()

    def confirm(self):
        return {"specimen_code": self.specimen.specimen_code, "confirmed": "on"}

    def test_invalidate_hides_every_normal_entry_and_retires_qr(self):
        photo = SpecimenPhoto.objects.create(
            specimen=self.specimen,
            file_path=f"specimens/{self.specimen.detail_uuid}/hidden.jpg",
            content_type="image/jpeg",
            width=1,
            height=1,
        )
        self.login_admin()
        self.assertEqual(self.client.get(self.invalidate_url).status_code, 200)
        response = self.client.post(self.invalidate_url, self.confirm())
        self.assertEqual(response.status_code, 302)
        self.specimen.refresh_from_db()
        self.label.refresh_from_db()
        self.assertIsNotNone(self.specimen.invalidated_at)
        self.assertEqual(self.label.status, QRLabel.Status.RETIRED)
        self.assertEqual(self.label.specimen_id, self.specimen.pk)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse("specimens:photo", args=[self.specimen.detail_uuid, photo.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("specimens:qr_resolve", args=[self.label.token])).status_code,
            410,
        )
        self.assertNotContains(
            self.client.get(reverse("specimens:list")), self.specimen.specimen_code
        )
        self.assertNotContains(
            self.client.get(reverse("management:specimen_csv_export")),
            self.specimen.specimen_code,
        )
        self.assertContains(
            self.client.get(reverse("management:specimen_management_list")),
            self.specimen.specimen_code,
        )
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.SPECIMEN_INVALIDATED).count(), 1
        )
        with self.assertRaises(SpecimenServiceError):
            record_specimen_event(
                specimen_id=self.specimen.pk,
                event_type=SpecimenEvent.Type.MOVE,
                created_by=self.admin,
            )

    def test_delete_requires_invalidation_exact_code_and_confirmation(self):
        self.login_admin()
        self.assertEqual(self.client.get(self.delete_url).status_code, 404)
        self.assertEqual(self.client.post(self.delete_url, self.confirm()).status_code, 404)
        self.client.post(self.invalidate_url, self.confirm())
        self.assertEqual(self.client.post(self.delete_url, {"confirmed": "on"}).status_code, 200)
        self.assertEqual(
            self.client.post(
                self.delete_url, {"specimen_code": "wrong", "confirmed": "on"}
            ).status_code,
            200,
        )
        self.assertTrue(Specimen.objects.filter(pk=self.specimen.pk).exists())
        path = f"specimens/{self.specimen.detail_uuid}/test.jpg"
        SpecimenPhoto.objects.create(
            specimen=self.specimen,
            file_path=path,
            content_type="image/jpeg",
            width=1,
            height=1,
        )
        SpecimenEvent.objects.create(
            specimen=self.specimen,
            event_type=SpecimenEvent.Type.OTHER,
            created_by=self.admin,
        )
        with patch("specimens.services.default_storage.delete") as remove_file:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.delete_url, self.confirm())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Specimen.objects.filter(pk=self.specimen.pk).exists())
        self.assertEqual(SpecimenSequence.objects.get(pk=1).next_number, 2)
        self.assertFalse(PendingPhotoDeletion.objects.exists())
        remove_file.assert_called_once_with(path)
        self.label.refresh_from_db()
        self.assertEqual(self.label.status, QRLabel.Status.RETIRED)
        self.assertIsNone(self.label.specimen_id)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.SPECIMEN_DELETED).count(), 1
        )

    def test_photo_deletion_failure_is_retriable(self):
        invalidate_specimen(specimen_id=self.specimen.pk, actor=self.admin)
        path = f"specimens/{self.specimen.detail_uuid}/test.jpg"
        SpecimenPhoto.objects.create(
            specimen=self.specimen,
            file_path=path,
            content_type="image/jpeg",
            width=1,
            height=1,
        )
        with patch("specimens.services.default_storage.delete", side_effect=OSError("failed")):
            with self.captureOnCommitCallbacks(execute=True):
                delete_invalidated_specimen(specimen_id=self.specimen.pk)
        self.assertEqual(PendingPhotoDeletion.objects.count(), 1)
        with patch("specimens.services.default_storage.delete") as remove_file:
            self.assertEqual(retry_pending_photo_deletions(), (1, 0))
        remove_file.assert_called_once_with(path)
        self.assertFalse(PendingPhotoDeletion.objects.exists())

    def test_audit_failure_rolls_back_invalidation_and_deletion(self):
        self.login_admin()
        with patch("management_portal.views.AuditLog.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post(self.invalidate_url, self.confirm())
        self.specimen.refresh_from_db()
        self.label.refresh_from_db()
        self.assertIsNone(self.specimen.invalidated_at)
        self.assertEqual(self.label.status, QRLabel.Status.ASSIGNED)
        invalidate_specimen(specimen_id=self.specimen.pk, actor=self.admin)
        with patch("management_portal.views.AuditLog.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post(self.delete_url, self.confirm())
        self.assertTrue(Specimen.objects.filter(pk=self.specimen.pk).exists())
        self.label.refresh_from_db()
        self.assertEqual(self.label.specimen_id, self.specimen.pk)

    def test_management_gate_and_recent_mfa_cover_destructive_routes(self):
        for url in (self.invalidate_url, self.delete_url):
            self.assertEqual(Client().post(url, self.confirm()).status_code, 302)
        self.client.force_login(self.member)
        for url in (self.invalidate_url, self.delete_url):
            self.assertEqual(self.client.post(url, self.confirm()).status_code, 403)
        self.login_admin(recent=False)
        self.assertEqual(self.client.post(self.invalidate_url, self.confirm()).status_code, 302)
        self.specimen.refresh_from_db()
        self.assertIsNone(self.specimen.invalidated_at)
