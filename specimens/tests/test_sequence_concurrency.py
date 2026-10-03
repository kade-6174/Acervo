from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from specimens.models import Specimen, SpecimenSequence
from specimens.services import create_specimen


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
