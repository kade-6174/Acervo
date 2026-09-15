from datetime import date

from asgiref.sync import sync_to_async
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .enrollment import CohortStanding, cohort_standing_on, validate_cohort_for_date


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        user = self._create_user_object(username, email, password, **extra_fields)
        user.full_clean()
        user.save(using=self._db)
        return user

    async def _acreate_user(self, username, email, password, **extra_fields):
        user = self._create_user_object(username, email, password, **extra_fields)
        await sync_to_async(user.full_clean, thread_sensitive=True)()
        await user.asave(using=self._db)
        return user


class User(AbstractUser):
    class Role(models.TextChoices):
        MEMBER = "member", "部員"
        ADMIN = "admin", "管理者"

    role = models.CharField(max_length=10, choices=Role, default=Role.MEMBER)
    cohort_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    must_change_password = models.BooleanField(default=False)
    mfa_reset_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cohort_number__gt=0),
                name="accounts_user_cohort_number_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["member", "admin"]),
                name="accounts_user_role_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.cohort_number is not None:
            validate_cohort_for_date(self.cohort_number, timezone.localdate())

    def cohort_standing_on(self, on_date: date) -> CohortStanding:
        return cohort_standing_on(self.cohort_number, on_date)
