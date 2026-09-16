from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CohortNullableMigrationTests(TransactionTestCase):
    migrate_from = [("accounts", "0002_user_mfa_reset_at")]
    migrate_to = [("accounts", "0003_user_cohort_number_nullable")]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)

    def tearDown(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_cohort_is_preserved_and_null_blocks_reverse(self):
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        OldUser = old_apps.get_model("accounts", "User")
        legacy = OldUser.objects.create(username="legacy-cohort", cohort_number=31)

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        NewUser = new_apps.get_model("accounts", "User")
        self.assertEqual(NewUser.objects.get(pk=legacy.pk).cohort_number, 31)
        NewUser.objects.create(username="null-cohort", cohort_number=None)

        self.executor = MigrationExecutor(connection)
        with self.assertRaisesRegex(RuntimeError, "NULLの回生データ"):
            self.executor.migrate(self.migrate_from)
