"""管理者による利用者のrole・有効状態変更を扱うサービス層。"""

from dataclasses import dataclass
from enum import StrEnum

from django.db import transaction

from accounts.management_access import has_primary_mfa
from accounts.models import User
from accounts.services import (
    TemporaryPasswordResult,
    create_user_with_temporary_password,
    reissue_temporary_password,
)
from audit.models import AuditLog


class UserAdministrationErrorCode(StrEnum):
    ACTOR_NOT_FOUND = "actor_not_found"
    TARGET_NOT_FOUND = "target_not_found"
    ACTOR_INACTIVE = "actor_inactive"
    ACTOR_NOT_ADMIN = "actor_not_admin"
    ACTOR_PASSWORD_CHANGE_REQUIRED = "actor_password_change_required"
    ACTOR_PRIMARY_MFA_REQUIRED = "actor_primary_mfa_required"
    INVALID_ROLE = "invalid_role"
    INVALID_ACTIVE_STATE = "invalid_active_state"
    LAST_ACTIVE_ADMIN_REQUIRED = "last_active_admin_required"
    SELF_PASSWORD_REISSUE_NOT_ALLOWED = "self_password_reissue_not_allowed"


class UserAdministrationError(Exception):
    """利用者管理の業務エラー。"""

    def __init__(self, code: UserAdministrationErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class UserAdministrationResult:
    target_user_id: int
    role_changed: bool
    active_state_changed: bool


def _require_management_actor(actor: User | None) -> User:
    if actor is None:
        raise UserAdministrationError(UserAdministrationErrorCode.ACTOR_NOT_FOUND)
    if not actor.is_active:
        raise UserAdministrationError(UserAdministrationErrorCode.ACTOR_INACTIVE)
    if actor.role != User.Role.ADMIN:
        raise UserAdministrationError(UserAdministrationErrorCode.ACTOR_NOT_ADMIN)
    if actor.must_change_password:
        raise UserAdministrationError(UserAdministrationErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED)
    if not has_primary_mfa(actor):
        raise UserAdministrationError(UserAdministrationErrorCode.ACTOR_PRIMARY_MFA_REQUIRED)
    return actor


def _lock_actor_target_and_admins(*, actor_id: int, target_user_id: int) -> dict[int, User]:
    """同時の降格・無効化でも最後の有効adminを失わないよう対象をロックする。"""

    candidate_ids = set(User.objects.filter(role=User.Role.ADMIN).values_list("pk", flat=True)) | {
        actor_id,
        target_user_id,
    }
    return {
        user.pk: user
        for user in User.objects.select_for_update().filter(pk__in=candidate_ids).order_by("pk")
    }


@transaction.atomic
def update_user_administration_by_admin(
    *, actor_id: int, target_user_id: int, role: str, is_active: bool
) -> UserAdministrationResult:
    """別利用者のroleと有効状態を原子的に更新し、必要な監査記録を残す。"""

    if role not in User.Role.values:
        raise UserAdministrationError(UserAdministrationErrorCode.INVALID_ROLE)
    if not isinstance(is_active, bool):
        raise UserAdministrationError(UserAdministrationErrorCode.INVALID_ACTIVE_STATE)

    locked_users = _lock_actor_target_and_admins(actor_id=actor_id, target_user_id=target_user_id)
    actor = locked_users.get(actor_id)
    target = locked_users.get(target_user_id)
    if target is None:
        raise UserAdministrationError(UserAdministrationErrorCode.TARGET_NOT_FOUND)
    actor = _require_management_actor(actor)

    role_changed = target.role != role
    active_state_changed = target.is_active != is_active
    if not role_changed and not active_state_changed:
        return UserAdministrationResult(
            target_user_id=target.pk,
            role_changed=False,
            active_state_changed=False,
        )

    target.role = role
    target.is_active = is_active
    active_admin_count = sum(
        user.is_active and user.role == User.Role.ADMIN
        for user in locked_users.values()
        if user.pk != target.pk
    ) + int(target.is_active and target.role == User.Role.ADMIN)
    if active_admin_count == 0:
        raise UserAdministrationError(UserAdministrationErrorCode.LAST_ACTIVE_ADMIN_REQUIRED)

    target.full_clean()
    target.save(update_fields=["role", "is_active"])
    if role_changed:
        AuditLog.objects.create(
            action=AuditLog.Action.USER_ROLE_CHANGED,
            channel=AuditLog.Channel.MANAGEMENT_UI,
            actor=actor,
            actor_username=actor.username,
            target=target,
            target_username=target.username,
        )
    if active_state_changed:
        AuditLog.objects.create(
            action=AuditLog.Action.USER_ACTIVE_STATE_CHANGED,
            channel=AuditLog.Channel.MANAGEMENT_UI,
            actor=actor,
            actor_username=actor.username,
            target=target,
            target_username=target.username,
        )
    return UserAdministrationResult(
        target_user_id=target.pk,
        role_changed=role_changed,
        active_state_changed=active_state_changed,
    )


@transaction.atomic
def create_user_by_admin(
    *, actor_id: int, username: str, cohort_number: int | None, role: str
) -> TemporaryPasswordResult:
    """管理者が利用者を作成し、秘密値を含めない監査記録を残す。"""

    actor = _require_management_actor(User.objects.select_for_update().filter(pk=actor_id).first())
    result = create_user_with_temporary_password(
        username=username,
        cohort_number=cohort_number,
        role=role,
    )
    AuditLog.objects.create(
        action=AuditLog.Action.USER_CREATED,
        channel=AuditLog.Channel.MANAGEMENT_UI,
        actor=actor,
        actor_username=actor.username,
        target=result.user,
        target_username=result.user.username,
    )
    return result


@transaction.atomic
def reissue_temporary_password_by_admin(
    *, actor_id: int, target_user_id: int
) -> TemporaryPasswordResult:
    """別利用者の一時パスワードを再発行し、秘密値を含めず監査する。"""

    locked_users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in={actor_id, target_user_id})
        .order_by("pk")
    }
    actor = _require_management_actor(locked_users.get(actor_id))
    target = locked_users.get(target_user_id)
    if target is None:
        raise UserAdministrationError(UserAdministrationErrorCode.TARGET_NOT_FOUND)
    if target.pk == actor.pk:
        raise UserAdministrationError(UserAdministrationErrorCode.SELF_PASSWORD_REISSUE_NOT_ALLOWED)

    result = reissue_temporary_password(user_id=target.pk)
    AuditLog.objects.create(
        action=AuditLog.Action.USER_PASSWORD_REISSUED,
        channel=AuditLog.Channel.MANAGEMENT_UI,
        actor=actor,
        actor_username=actor.username,
        target=result.user,
        target_username=result.user.username,
    )
    return result
