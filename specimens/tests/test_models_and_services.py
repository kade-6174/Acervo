import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from specimens.models import Specimen, SpecimenEvent, SpecimenSequence, Taxon
from specimens.services import (
    SpecimenServiceError,
    SpecimenServiceErrorCode,
    create_specimen,
    record_specimen_event,
)


class SpecimenModelsAndServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="specimen-user", password="SecurePassword123!", cohort_number=31
        )

    def create_specimen(self, **overrides):
        fields = {
            "acquisition_method": Specimen.AcquisitionMethod.COLLECTED,
            "identification_text": "未同定の甲虫",
        }
        fields.update(overrides)
        return create_specimen(created_by=self.user, **fields)

    def test_creation_assigns_non_reusable_code_uuid_and_initial_event(self):
        first = self.create_specimen()
        second = self.create_specimen(identification_text="未同定の植物")

        self.assertEqual(first.specimen_code, "ACERVO-000001")
        self.assertEqual(second.specimen_code, "ACERVO-000002")
        self.assertEqual(first.detail_uuid.version, 4)
        self.assertNotEqual(first.detail_uuid, second.detail_uuid)
        self.assertEqual(first.events.get().event_type, SpecimenEvent.Type.COLLECTION)
        self.assertEqual(SpecimenSequence.objects.get(pk=1).next_number, 3)

    def test_unknown_taxon_and_unknown_collection_date_are_allowed(self):
        specimen = self.create_specimen()

        self.assertIsNone(specimen.taxon)
        self.assertIsNone(specimen.collected_on)
        self.assertEqual(specimen.identification_text, "未同定の甲虫")

    def test_taxon_or_identification_text_is_required_and_failure_does_not_consume_number(self):
        with self.assertRaises(ValidationError):
            self.create_specimen(identification_text="")

        specimen = self.create_specimen()
        self.assertEqual(specimen.specimen_code, "ACERVO-000001")

    def test_taxon_allows_empty_identification_text(self):
        taxon = Taxon.objects.create(scientific_name="Lucanus maculifemoratus")

        specimen = self.create_specimen(taxon=taxon, identification_text="")

        self.assertEqual(specimen.taxon, taxon)

    def test_code_and_detail_uuid_are_immutable(self):
        specimen = self.create_specimen()
        specimen.specimen_code = "ACERVO-999999"
        with self.assertRaises(ValidationError):
            specimen.save()

        specimen.refresh_from_db()
        specimen.detail_uuid = uuid.uuid4()
        with self.assertRaises(ValidationError):
            specimen.save()

    def test_loan_and_return_change_state_with_events_atomically(self):
        specimen = self.create_specimen()

        loan = record_specimen_event(
            specimen_id=specimen.pk,
            event_type=SpecimenEvent.Type.LOAN,
            created_by=self.user,
            note="調査用",
        )
        returned = record_specimen_event(
            specimen_id=specimen.pk,
            event_type=SpecimenEvent.Type.RETURN,
            created_by=self.user,
        )

        self.assertEqual(loan.previous_status, Specimen.Status.IN_COLLECTION)
        self.assertEqual(loan.current_status, Specimen.Status.ON_LOAN)
        self.assertEqual(returned.current_status, Specimen.Status.IN_COLLECTION)
        self.assertEqual(specimen.events.count(), 3)

    def test_invalid_transition_does_not_add_event_or_change_state(self):
        specimen = self.create_specimen()
        record_specimen_event(
            specimen_id=specimen.pk,
            event_type=SpecimenEvent.Type.SALE,
            created_by=self.user,
        )

        with self.assertRaises(SpecimenServiceError) as raised:
            record_specimen_event(
                specimen_id=specimen.pk,
                event_type=SpecimenEvent.Type.LOAN,
                created_by=self.user,
            )

        self.assertEqual(raised.exception.code, SpecimenServiceErrorCode.INVALID_STATE_TRANSITION)
        specimen.refresh_from_db()
        self.assertEqual(specimen.status, Specimen.Status.SOLD)
        self.assertEqual(specimen.events.count(), 2)

    def test_events_are_append_only(self):
        event = self.create_specimen().events.get()
        event.note = "変更"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_invalid_event_type_is_rejected_without_history(self):
        specimen = self.create_specimen()

        with self.assertRaises(SpecimenServiceError) as raised:
            record_specimen_event(
                specimen_id=specimen.pk,
                event_type="invalid",
                created_by=self.user,
            )

        self.assertEqual(raised.exception.code, SpecimenServiceErrorCode.INVALID_EVENT_TYPE)
        self.assertEqual(specimen.events.count(), 1)

    def test_deleted_specimen_code_is_not_reused(self):
        first = self.create_specimen()
        SpecimenEvent.objects.filter(specimen=first).delete()
        first.delete()

        second = self.create_specimen()
        self.assertEqual(second.specimen_code, "ACERVO-000002")

    def test_database_constraints_reject_invalid_sequence_values(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SpecimenSequence.objects.create(id=2, next_number=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SpecimenSequence.objects.create(id=1, next_number=0)
