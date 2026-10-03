import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from specimens.models import QRBatch, QRLabel, Specimen
from specimens.services import (
    SpecimenServiceError,
    assign_qr_label,
    build_qr_labels_pdf,
    create_qr_batch,
    create_specimen,
    qr_url,
    record_qr_reprint,
    retire_qr_label,
)


class QRServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="qr-user", cohort_number=33)
        self.specimen = create_specimen(
            created_by=self.user,
            identification_text="未同定",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
        )

    def test_batch_creates_unused_random_labels_without_consuming_specimen_number(self):
        result = create_qr_batch(requested_count=2, created_by=self.user, note="test")

        self.assertEqual(QRBatch.objects.get(pk=result.batch_id).requested_count, 2)
        labels = list(QRLabel.objects.filter(batch_id=result.batch_id))
        self.assertEqual(len(labels), 2)
        self.assertEqual({label.status for label in labels}, {QRLabel.Status.UNUSED})
        self.assertEqual({label.specimen_id for label in labels}, {None})
        self.assertNotEqual(labels[0].token, labels[1].token)
        self.assertEqual(Specimen.objects.count(), 1)

    def test_invalid_batch_count_is_rejected_without_creating_rows(self):
        with self.assertRaisesRegex(SpecimenServiceError, "invalid_qr_batch_size"):
            create_qr_batch(requested_count=0, created_by=self.user)

        self.assertEqual(QRBatch.objects.count(), 0)
        self.assertEqual(QRLabel.objects.count(), 0)

    def test_assignment_is_one_to_one_and_retirement_preserves_history(self):
        result = create_qr_batch(requested_count=2, created_by=self.user)
        first, second = QRLabel.objects.filter(pk__in=result.label_ids).order_by("pk")

        assignment = assign_qr_label(token=first.token, specimen_id=self.specimen.pk)

        first.refresh_from_db()
        self.assertEqual(assignment.specimen_id, self.specimen.pk)
        self.assertEqual(first.status, QRLabel.Status.ASSIGNED)
        with self.assertRaisesRegex(SpecimenServiceError, "specimen_already_has_qr_label"):
            assign_qr_label(token=second.token, specimen_id=self.specimen.pk)

        retired = retire_qr_label(token=first.token)
        self.assertEqual(retired.status, QRLabel.Status.RETIRED)
        self.assertEqual(retired.specimen_id, self.specimen.pk)
        self.assertIsNotNone(retired.retired_at)

    def test_assigned_or_retired_label_cannot_be_assigned_again(self):
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.user).label_ids[0]
        )
        assign_qr_label(token=label.token, specimen_id=self.specimen.pk)

        with self.assertRaisesRegex(SpecimenServiceError, "qr_label_not_unused"):
            assign_qr_label(token=label.token, specimen_id=self.specimen.pk)

        retire_qr_label(token=label.token)
        with self.assertRaisesRegex(SpecimenServiceError, "qr_label_not_unused"):
            assign_qr_label(token=label.token, specimen_id=self.specimen.pk)

    def test_token_is_immutable_and_database_constraint_rejects_invalid_combination(self):
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.user).label_ids[0]
        )
        label.token = uuid.uuid4()
        with self.assertRaisesMessage(Exception, "QR識別子は変更できません"):
            label.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            QRLabel.objects.create(
                batch=label.batch,
                status=QRLabel.Status.ASSIGNED,
            )

    @override_settings(ACERVO_PUBLIC_BASE_URL="https://example.test/base/")
    def test_qr_url_and_pdf_do_not_include_specimen_information(self):
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.user).label_ids[0]
        )
        pdf = build_qr_labels_pdf(labels=[label], size_mm=20)

        self.assertEqual(qr_url(label.token), f"https://example.test/base/q/{label.token}/")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertNotIn(self.specimen.specimen_code.encode(), pdf)
        with self.assertRaises(ValueError):
            build_qr_labels_pdf(labels=[label], size_mm=10)

    def test_reprint_keeps_token_and_assignment(self):
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.user).label_ids[0]
        )
        original_token = label.token
        record_qr_reprint(token=label.token)
        label.refresh_from_db()

        self.assertEqual(label.token, original_token)
        self.assertEqual(label.print_count, 1)
        self.assertIsNotNone(label.last_printed_at)


class QRRouteTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="member", cohort_number=33)
        self.graduate = User.objects.create_user(username="graduate", cohort_number=30)
        self.label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.member).label_ids[0]
        )

    def url(self, token=None):
        return reverse("specimens:qr_resolve", kwargs={"token": token or self.label.token})

    def test_unauthenticated_request_redirects_without_revealing_qr_state(self):
        response = self.client.get(self.url())

        self.assertRedirects(
            response, f"/accounts/login/?next={self.url()}", fetch_redirect_response=False
        )

    def test_current_member_can_resolve_unused_qr_without_specimen_details(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "未使用のQRコードです")
        self.assertNotContains(response, "KDF-BIO")
        self.assertEqual(
            response.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_graduate_and_invalid_token_receive_same_not_found_response(self):
        self.client.force_login(self.graduate)
        denied = self.client.get(self.url())
        invalid = self.client.get(self.url(uuid.uuid4()))

        self.assertEqual(denied.status_code, 404)
        self.assertEqual(invalid.status_code, 404)

    def test_assigned_and_retired_qr_do_not_expose_specimen_details(self):
        specimen = create_specimen(
            created_by=self.member,
            identification_text="非公開の同定情報",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
        )
        assign_qr_label(token=self.label.token, specimen_id=specimen.pk)
        self.client.force_login(self.member)

        assigned = self.client.get(self.url())
        self.assertContains(assigned, "割り当て済みのQRコードです")
        self.assertNotContains(assigned, specimen.specimen_code)
        self.assertNotContains(assigned, "非公開の同定情報")

        retire_qr_label(token=self.label.token)
        retired = self.client.get(self.url())
        self.assertEqual(retired.status_code, 410)
        self.assertNotContains(retired, specimen.specimen_code, status_code=410)
