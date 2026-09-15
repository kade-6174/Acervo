"""Acervo管理機能のアクセス可否を判定するポリシー。

このモジュールは判定だけを担当する。redirect、HTTPレスポンス、middlewareへの
適用はStep 5Bで行う。
"""

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from django.http import HttpRequest
from django.utils import timezone

from accounts.models import User


class ManagementAccessReason(Enum):
    """管理アクセスの判定理由。"""

    UNAUTHENTICATED = "unauthenticated"
    INACTIVE = "inactive"
    NOT_ADMIN = "not_admin"
    PASSWORD_CHANGE_REQUIRED = "password_change_required"
    PRIMARY_MFA_REQUIRED = "primary_mfa_required"
    SESSION_MFA_REQUIRED = "session_mfa_required"
    ALLOWED = "allowed"


@dataclass(frozen=True, slots=True)
class ManagementAccessDecision:
    """呼出元が許可状態と理由を型安全に扱うための判定結果。"""

    reason: ManagementAccessReason

    @property
    def allowed(self) -> bool:
        return self.reason is ManagementAccessReason.ALLOWED


PRIMARY_MFA_TYPES = (Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)
SESSION_MFA_TYPES = {
    Authenticator.Type.TOTP,
    Authenticator.Type.WEBAUTHN,
    Authenticator.Type.RECOVERY_CODES,
}


def has_primary_mfa(user: User) -> bool:
    """現在のDBにTOTPまたはWebAuthnの登録が存在するか返す。"""

    if not user.is_authenticated or user.pk is None:
        return False
    return Authenticator.objects.filter(user_id=user.pk, type__in=PRIMARY_MFA_TYPES).exists()


def has_session_mfa(request: HttpRequest, *, mfa_reset_at=None) -> bool:
    """現在のセッションにallauth標準のMFA認証記録があるか返す。"""

    records = get_authentication_records(request)
    if not isinstance(records, list):
        return False

    for record in records:
        if not isinstance(record, dict) or record.get("signup"):
            continue
        authenticated_at = record.get("at")
        if isinstance(authenticated_at, bool) or not isinstance(authenticated_at, (int, float)):
            continue
        if not isfinite(authenticated_at) or authenticated_at > timezone.now().timestamp():
            continue
        if mfa_reset_at is not None and authenticated_at <= mfa_reset_at.timestamp():
            continue
        if record.get("method") == "mfa" and record.get("type") in SESSION_MFA_TYPES:
            return True
    return False


def evaluate_management_access(request: HttpRequest) -> ManagementAccessDecision:
    """現在のDB状態とログインセッションから管理アクセス可否を判定する。"""

    request_user = request.user
    if not request_user.is_authenticated or request_user.pk is None:
        return ManagementAccessDecision(ManagementAccessReason.UNAUTHENTICATED)

    user_state = (
        User.objects.filter(pk=request_user.pk)
        .values("is_active", "role", "must_change_password", "mfa_reset_at")
        .first()
    )
    if user_state is None:
        return ManagementAccessDecision(ManagementAccessReason.UNAUTHENTICATED)
    if not user_state["is_active"]:
        return ManagementAccessDecision(ManagementAccessReason.INACTIVE)
    if user_state["role"] != User.Role.ADMIN:
        return ManagementAccessDecision(ManagementAccessReason.NOT_ADMIN)
    if user_state["must_change_password"]:
        return ManagementAccessDecision(ManagementAccessReason.PASSWORD_CHANGE_REQUIRED)
    if not has_primary_mfa(request_user):
        return ManagementAccessDecision(ManagementAccessReason.PRIMARY_MFA_REQUIRED)
    if not has_session_mfa(request, mfa_reset_at=user_state["mfa_reset_at"]):
        return ManagementAccessDecision(ManagementAccessReason.SESSION_MFA_REQUIRED)
    return ManagementAccessDecision(ManagementAccessReason.ALLOWED)
