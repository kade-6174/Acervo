from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from specimens.models import QRLabel, Specimen, SpecimenSequence
from specimens.services import (
    SpecimenServiceError,
    assign_qr_label,
    create_qr_batch,
    create_specimen,
)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL上の行ロック検証")
class SpecimenSequenceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="sequence-user", password="SecurePassword123!", cohort_number=31
        )
        SpecimenSequence.objects.create(pk=1, next_number=1)

    def create_in_other_connection(self, identification_text):
        close_old_connections()
        try:
            specimen = create_specimen(
                created_by=User.objects.get(pk=self.user.pk),
                acquisition_method=Specimen.AcquisitionMethod.COLLECTED,
                identification_text=identification_text,
            )
            return specimen.specimen_code
        finally:
            close_old_connections()

    def test_concurrent_numbering_creates_distinct_codes(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(
                executor.map(
                    self.create_in_other_connection,
                    ("同時登録A", "同時登録B"),
                )
            )

        self.assertEqual(set(codes), {"ACERVO-000001", "ACERVO-000002"})
        self.assertEqual(Specimen.objects.count(), 2)
        self.assertEqual(SpecimenSequence.objects.get(pk=1).next_number, 3)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL上のQR行ロック検証")
class QRLabelConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="qr-concurrency-user", password="SecurePassword123!", cohort_number=31
        )
        self.specimen_a = create_specimen(
            created_by=self.user,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            identification_text="競合A",
        )
        self.specimen_b = create_specimen(
            created_by=self.user,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            identification_text="競合B",
        )
        result = create_qr_batch(requested_count=1, created_by=self.user)
        self.token = QRLabel.objects.get(pk=result.label_ids[0]).token

    def assign_in_other_connection(self, specimen_id):
        close_old_connections()
        try:
            try:
                assign_qr_label(token=self.token, specimen_id=specimen_id)
            except SpecimenServiceError as error:
                return error.code.value
            return "assigned"
        finally:
            close_old_connections()

    def test_concurrent_assignment_allows_exactly_one_specimen(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    self.assign_in_other_connection,
                    (self.specimen_a.pk, self.specimen_b.pk),
                )
            )

        label = QRLabel.objects.get(token=self.token)
        self.assertEqual(results.count("assigned"), 1)
        self.assertEqual(results.count("qr_label_not_unused"), 1)
        self.assertEqual(label.status, QRLabel.Status.ASSIGNED)
        self.assertIn(label.specimen_id, {self.specimen_a.pk, self.specimen_b.pk})
