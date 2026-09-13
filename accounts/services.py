import secrets
from dataclasses import dataclass

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import User


@dataclass(frozen=True)
class TemporaryPasswordResult:
    user: User
    temporary_password: str


def _generate_temporary_password(user: User) -> str:
    while True:
        password = secrets.token_urlsafe(24)
        try:
            password_validation.validate_password(password, user=user)
        except ValidationError:
            continue
        return password


@transaction.atomic
def create_user_with_temporary_password(
    *, username: str, cohort_number: int, role: str = User.Role.MEMBER
) -> TemporaryPasswordResult:
    candidate = User(username=username, cohort_number=cohort_number, role=role)
    temporary_password = _generate_temporary_password(candidate)
    user = User.objects.create_user(
        username=username,
        cohort_number=cohort_number,
        role=role,
        password=temporary_password,
        must_change_password=True,
    )
    return TemporaryPasswordResult(user=user, temporary_password=temporary_password)


@transaction.atomic
def reissue_temporary_password(*, user_id: int) -> TemporaryPasswordResult:
    user = User.objects.select_for_update().get(pk=user_id)
    temporary_password = _generate_temporary_password(user)
    user.set_password(temporary_password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    return TemporaryPasswordResult(user=user, temporary_password=temporary_password)
