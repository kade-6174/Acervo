"""PostgreSQLで標本の無効化・完全削除と並行操作を検証する。"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from specimens.models import QRLabel, Specimen, SpecimenEvent
from specimens.services import (
    SpecimenServiceError,
    assign_qr_label,
    create_qr_batch,
    create_specimen,
    delete_invalidated_specimen,
    invalidate_specimen,
    record_specimen_event,
)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL上の標本管理行ロック検証")
class SpecimenRetirementConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="retirement-concurrency-admin", role=User.Role.ADMIN, cohort_number=33
        )
        self.specimen = create_specimen(
            created_by=self.admin,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            identification_text="並行操作の試験標本",
        )
        batch = create_qr_batch(requested_count=1, created_by=self.admin)
        self.label = QRLabel.objects.get(pk=batch.label_ids[0])

    def run_action(self, action, barrier):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '10s'")
            actor = User.objects.get(pk=self.admin.pk)
            barrier.wait(timeout=10)
            try:
                if action == "invalidate":
                    invalidate_specimen(specimen_id=self.specimen.pk, actor=actor)
                elif action == "delete":
                    delete_invalidated_specimen(specimen_id=self.specimen.pk)
                elif action == "assign":
                    assign_qr_label(token=self.label.token, specimen_id=self.specimen.pk)
                elif action == "event":
                    record_specimen_event(
                        specimen_id=self.specimen.pk,
                        created_by=actor,
                        event_type=SpecimenEvent.Type.MOVE,
                    )
            except SpecimenServiceError as error:
                return error.code.value
            return action
        finally:
            close_old_connections()
            connection.close()

    def run_pair(self, first, second):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.run_action, action, barrier) for action in (first, second)
            ]
            return [future.result(timeout=15) for future in futures]

    def test_two_invalidations_allow_only_one_success(self):
        assign_qr_label(token=self.label.token, specimen_id=self.specimen.pk)
        results = self.run_pair("invalidate", "invalidate")
        self.assertCountEqual(results, ["invalidate", "specimen_invalidated"])
        self.label.refresh_from_db()
        self.specimen.refresh_from_db()
        self.assertEqual(self.label.status, QRLabel.Status.RETIRED)
        self.assertIsNotNone(self.specimen.invalidated_at)

    def test_two_deletions_allow_only_one_success_and_keep_retired_qr(self):
        assign_qr_label(token=self.label.token, specimen_id=self.specimen.pk)
        invalidate_specimen(specimen_id=self.specimen.pk, actor=self.admin)
        results = self.run_pair("delete", "delete")
        self.assertCountEqual(results, ["delete", "specimen_not_found"])
        self.label.refresh_from_db()
        self.assertEqual(self.label.status, QRLabel.Status.RETIRED)
        self.assertIsNone(self.label.specimen_id)
        self.assertFalse(Specimen.objects.filter(pk=self.specimen.pk).exists())

    def test_assignment_and_invalidation_leave_no_active_qr_on_invalidated_specimen(self):
        results = self.run_pair("assign", "invalidate")
        self.assertIn("invalidate", results)
        self.assertTrue("assign" in results or "specimen_invalidated" in results)
        self.specimen.refresh_from_db()
        self.label.refresh_from_db()
        self.assertIsNotNone(self.specimen.invalidated_at)
        if self.label.specimen_id is None:
            self.assertEqual(self.label.status, QRLabel.Status.UNUSED)
        else:
            self.assertEqual(self.label.specimen_id, self.specimen.pk)
            self.assertEqual(self.label.status, QRLabel.Status.RETIRED)

    def test_event_and_invalidation_commit_in_order(self):
        results = self.run_pair("event", "invalidate")
        self.assertIn("invalidate", results)
        self.assertTrue("event" in results or "specimen_invalidated" in results)
        self.assertEqual(
            self.specimen.events.filter(event_type=SpecimenEvent.Type.MOVE).count(),
            int("event" in results),
        )
        with self.assertRaisesRegex(SpecimenServiceError, "specimen_invalidated"):
            record_specimen_event(
                specimen_id=self.specimen.pk,
                created_by=self.admin,
                event_type=SpecimenEvent.Type.MOVE,
            )
