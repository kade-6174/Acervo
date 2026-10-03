from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from allauth.mfa.models import Authenticator
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from accounts.user_administration import (
    UserAdministrationError,
    UserAdministrationErrorCode,
    update_user_administration_by_admin,
)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL上の行ロック検証")
class UserAdministrationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.first_admin = self.create_admin("first-admin")
        self.second_admin = self.create_admin("second-admin")

    @staticmethod
    def create_admin(username):
        user = User.objects.create_user(
            username=username,
            password="SecurePassword123!",
            cohort_number=31,
            role=User.Role.ADMIN,
        )
        Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"test": True})
        return user

    @staticmethod
    def demote(actor_id, target_id):
        close_old_connections()
        try:
            update_user_administration_by_admin(
                actor_id=actor_id,
                target_user_id=target_id,
                role=User.Role.MEMBER,
                is_active=True,
            )
        except UserAdministrationError as error:
            return error.code
        finally:
            close_old_connections()
        return None

    def test_simultaneous_demotions_leave_one_active_admin(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(
                    lambda ids: self.demote(*ids),
                    (
                        (self.first_admin.pk, self.first_admin.pk),
                        (self.second_admin.pk, self.second_admin.pk),
                    ),
                )
            )

        self.assertEqual(outcomes.count(None), 1)
        self.assertEqual(
            outcomes.count(UserAdministrationErrorCode.LAST_ACTIVE_ADMIN_REQUIRED),
            1,
        )
        self.assertEqual(
            User.objects.filter(role=User.Role.ADMIN, is_active=True).count(),
            1,
        )
