"""HTTP層から独立した、別管理者によるMFAリセットサービス。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from allauth.mfa.models import Authenticator
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from accounts.management_access import PRIMARY_MFA_TYPES, has_primary_mfa
from accounts.models import User
from audit.models import AuditLog


class MFAResetErrorCode(StrEnum):
    ACTOR_NOT_FOUND = "actor_not_found"
    TARGET_NOT_FOUND = "target_not_found"
    ACTOR_INACTIVE = "actor_inactive"
    ACTOR_NOT_ADMIN = "actor_not_admin"
    ACTOR_PASSWORD_CHANGE_REQUIRED = "actor_password_change_required"
    ACTOR_PRIMARY_MFA_REQUIRED = "actor_primary_mfa_required"
    SELF_RESET_NOT_ALLOWED = "self_reset_not_allowed"
    TARGET_HAS_NO_AUTHENTICATORS = "target_has_no_authenticators"
    COMMAND_TARGET_NOT_ADMIN = "command_target_not_admin"
    COMMAND_TARGET_INACTIVE = "command_target_inactive"
    COMMAND_OTHER_ADMIN_AVAILABLE = "command_other_admin_available"


class MFAResetError(Exception):
    """利用者へ安全に扱える、MFAリセットの業務エラー。"""

    def __init__(self, code: MFAResetErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class MFAResetResult:
    target_user_id: int
    deleted_authenticator_count: int
    reset_at: datetime


def _delete_target_sessions(target_user_id: int) -> None:
    """DB sessionから対象ユーザーだけを削除し、破損行は安全に読み飛ばす。"""

    for session in Session.objects.all().only("session_key", "session_data", "expire_date"):
        try:
            session_data = session.get_decoded()
        except Exception:  # 破損した過去セッションはリセット全体を妨げない。
            continue
        if str(session_data.get(SESSION_KEY, "")) == str(target_user_id):
            session.delete()


@transaction.atomic
def reset_user_mfa_by_admin(*, actor_id: int, target_user_id: int) -> MFAResetResult:
    """有効な別管理者が対象のMFAと既存ログインsessionを無効化する。"""

    locked_users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in={actor_id, target_user_id})
        .order_by("pk")
    }
    actor = locked_users.get(actor_id)
    if actor is None:
        raise MFAResetError(MFAResetErrorCode.ACTOR_NOT_FOUND)
    target = locked_users.get(target_user_id)
    if target is None:
        raise MFAResetError(MFAResetErrorCode.TARGET_NOT_FOUND)
    if actor.pk == target.pk:
        raise MFAResetError(MFAResetErrorCode.SELF_RESET_NOT_ALLOWED)
    if not actor.is_active:
        raise MFAResetError(MFAResetErrorCode.ACTOR_INACTIVE)
    if actor.role != User.Role.ADMIN:
        raise MFAResetError(MFAResetErrorCode.ACTOR_NOT_ADMIN)
    if actor.must_change_password:
        raise MFAResetError(MFAResetErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED)
    if not has_primary_mfa(actor):
        raise MFAResetError(MFAResetErrorCode.ACTOR_PRIMARY_MFA_REQUIRED)

    authenticators = Authenticator.objects.filter(user_id=target.pk)
    deleted_authenticator_count = authenticators.count()
    if deleted_authenticator_count == 0:
        raise MFAResetError(MFAResetErrorCode.TARGET_HAS_NO_AUTHENTICATORS)

    reset_at = timezone.now()
    authenticators.delete()
    target.mfa_reset_at = reset_at
    target.save(update_fields=["mfa_reset_at"])
    _delete_target_sessions(target.pk)
    AuditLog.objects.create(
        action=AuditLog.Action.ADMIN_MFA_RESET,
        channel=AuditLog.Channel.MANAGEMENT_UI,
        actor=actor,
        actor_username=actor.username,
        target=target,
        target_username=target.username,
    )
    return MFAResetResult(
        target_user_id=target.pk,
        deleted_authenticator_count=deleted_authenticator_count,
        reset_at=reset_at,
    )


@transaction.atomic
def reset_admin_mfa_by_command(*, target_username: str) -> MFAResetResult:
    """最後の復旧不能な有効adminだけをサーバー管理者が緊急復旧する。"""
    target_id = User.objects.filter(username=target_username).values_list("pk", flat=True).first()
    if target_id is None:
        raise MFAResetError(MFAResetErrorCode.TARGET_NOT_FOUND)

    admin_ids = list(User.objects.filter(role=User.Role.ADMIN).values_list("pk", flat=True))
    locked_users = {
        user.pk: user
        for user in User.objects.select_for_update().filter(pk__in=admin_ids).order_by("pk")
    }
    target = locked_users.get(target_id)
    if target is None:
        raise MFAResetError(MFAResetErrorCode.COMMAND_TARGET_NOT_ADMIN)
    if not target.is_active:
        raise MFAResetError(MFAResetErrorCode.COMMAND_TARGET_INACTIVE)

    authenticators = Authenticator.objects.filter(user_id=target.pk)
    deleted_authenticator_count = authenticators.count()
    if deleted_authenticator_count == 0:
        raise MFAResetError(MFAResetErrorCode.TARGET_HAS_NO_AUTHENTICATORS)

    other_admin_ids = [user_id for user_id in locked_users if user_id != target.pk]
    if Authenticator.objects.filter(
        user_id__in=other_admin_ids,
        user__is_active=True,
        user__role=User.Role.ADMIN,
        user__must_change_password=False,
        type__in=PRIMARY_MFA_TYPES,
    ).exists():
        raise MFAResetError(MFAResetErrorCode.COMMAND_OTHER_ADMIN_AVAILABLE)

    reset_at = timezone.now()
    authenticators.delete()
    target.mfa_reset_at = reset_at
    target.save(update_fields=["mfa_reset_at"])
    _delete_target_sessions(target.pk)
    AuditLog.objects.create(
        action=AuditLog.Action.COMMAND_MFA_RESET,
        channel=AuditLog.Channel.MANAGEMENT_COMMAND,
        actor=None,
        actor_username="server-operator",
        target=target,
        target_username=target.username,
    )
    return MFAResetResult(
        target_user_id=target.pk,
        deleted_authenticator_count=deleted_authenticator_count,
        reset_at=reset_at,
    )
