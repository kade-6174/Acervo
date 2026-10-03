from time import time
from urllib.parse import urlencode

from allauth.account.adapter import get_adapter
from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.management_access import evaluate_management_access
from accounts.mfa_reset import MFAResetError, MFAResetErrorCode, reset_user_mfa_by_admin
from accounts.models import User
from accounts.user_administration import (
    UserAdministrationError,
    UserAdministrationErrorCode,
    create_user_by_admin,
    reissue_temporary_password_by_admin,
    update_user_administration_by_admin,
)
from audit.models import AuditLog

from .admin_warnings import get_administrator_warnings


class MFAResetConfirmationForm(forms.Form):
    confirmed = forms.BooleanField(label="本人確認済み", required=True)
    username = forms.CharField(
        label="対象のユーザー名", max_length=User._meta.get_field("username").max_length
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmed"].widget.attrs["class"] = "form-check-input"
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "off"}
        )


class UserAdministrationForm(forms.Form):
    role = forms.ChoiceField(label="role", choices=User.Role.choices)
    is_active = forms.BooleanField(label="有効", required=False)
    confirmed = forms.BooleanField(label="変更内容を確認した", required=True)
    username = forms.CharField(
        label="対象のユーザー名",
        max_length=User._meta.get_field("username").max_length,
    )

    def __init__(self, *args, target: User, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update({"role": target.role, "is_active": target.is_active})
        self.fields["role"].widget.attrs["class"] = "form-select"
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        self.fields["confirmed"].widget.attrs["class"] = "form-check-input"
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "off"}
        )


class UserCreationForm(forms.Form):
    username = forms.CharField(
        label="ユーザー名",
        max_length=User._meta.get_field("username").max_length,
    )
    cohort_number = forms.IntegerField(label="回生", min_value=1, required=False)
    role = forms.ChoiceField(label="role", choices=User.Role.choices)
    confirmed = forms.BooleanField(label="作成内容を確認した", required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "off",
            }
        )
        self.fields["cohort_number"].widget.attrs["class"] = "form-control"
        self.fields["role"].widget.attrs["class"] = "form-select"
        self.fields["confirmed"].widget.attrs["class"] = "form-check-input"


def _authenticator_summary(user_id: int) -> list[str]:
    """認証器の秘密データに触れず、一般的な種別だけを返す。"""
    types = set(Authenticator.objects.filter(user_id=user_id).values_list("type", flat=True))
    labels = []
    for authenticator_type, label in (
        (Authenticator.Type.TOTP, "TOTP"),
        (Authenticator.Type.WEBAUTHN, "パスキー"),
        (Authenticator.Type.RECOVERY_CODES, "Recovery Codes"),
    ):
        if authenticator_type in types:
            labels.append(label)
    return labels


def _has_recent_primary_mfa_reauthentication(request) -> bool:
    """直近のTOTP/WebAuthn再認証だけを取消不能操作の最終確認に使う。"""
    timeout = getattr(settings, "ACCOUNT_REAUTHENTICATION_TIMEOUT", 300)
    now = time()
    records = get_authentication_records(request)
    if not isinstance(records, list):
        return False
    return any(
        isinstance(record, dict)
        and record.get("method") == "mfa"
        and record.get("type") in {Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN}
        and record.get("reauthenticated") is True
        and isinstance(record.get("at"), (int, float))
        and not isinstance(record.get("at"), bool)
        and 0 <= now - record["at"] <= timeout
        for record in records
    )


def _mfa_reauthentication_redirect(request, confirmation_url: str):
    """許可済みのMFA方式だけへ、固定した内部確認URLをnextとして渡す。"""
    methods = get_adapter(request).get_reauthentication_methods(request.user)
    method = next(
        (
            item
            for item in methods
            if item.get("id", "").startswith("mfa_reauthenticate") and item.get("url")
        ),
        None,
    )
    if method is None:
        messages.error(request, "MFA再認証方法を確認できないため、リセットを実行できません。")
        return redirect("management:mfa_reset_search")
    return HttpResponseRedirect(f"{method['url']}?{urlencode({'next': confirmation_url})}")


def _reset_error_message(error: MFAResetError) -> str:
    messages_by_code = {
        MFAResetErrorCode.SELF_RESET_NOT_ALLOWED: "自分自身のMFAはこの画面からリセットできません。",
        MFAResetErrorCode.TARGET_HAS_NO_AUTHENTICATORS: (
            "対象のMFAはすでにリセット済みか、登録されていません。再検索して確認してください。"
        ),
        MFAResetErrorCode.TARGET_NOT_FOUND: "対象の利用者を確認できません。再検索してください。",
        MFAResetErrorCode.ACTOR_INACTIVE: (
            "現在の管理権限を確認できないため、リセットを実行できません。"
        ),
        MFAResetErrorCode.ACTOR_NOT_ADMIN: (
            "現在の管理権限を確認できないため、リセットを実行できません。"
        ),
        MFAResetErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED: (
            "パスワード変更を完了してから、もう一度操作してください。"
        ),
        MFAResetErrorCode.ACTOR_PRIMARY_MFA_REQUIRED: (
            "管理者のMFA設定を確認できないため、リセットを実行できません。"
        ),
        MFAResetErrorCode.ACTOR_NOT_FOUND: (
            "現在の管理権限を確認できないため、リセットを実行できません。"
        ),
    }
    return messages_by_code.get(
        error.code, "MFAリセットを実行できませんでした。再確認してください。"
    )


def _user_administration_error_message(error: UserAdministrationError) -> str:
    messages_by_code = {
        UserAdministrationErrorCode.TARGET_NOT_FOUND: (
            "対象の利用者を確認できません。再検索してください。"
        ),
        UserAdministrationErrorCode.ACTOR_INACTIVE: (
            "現在の管理権限を確認できないため、変更できません。"
        ),
        UserAdministrationErrorCode.ACTOR_NOT_ADMIN: (
            "現在の管理権限を確認できないため、変更できません。"
        ),
        UserAdministrationErrorCode.ACTOR_PASSWORD_CHANGE_REQUIRED: (
            "パスワード変更を完了してから、もう一度操作してください。"
        ),
        UserAdministrationErrorCode.ACTOR_PRIMARY_MFA_REQUIRED: (
            "管理者のMFA設定を確認できないため、変更できません。"
        ),
        UserAdministrationErrorCode.LAST_ACTIVE_ADMIN_REQUIRED: (
            "最後の有効な管理者は降格または無効化できません。"
        ),
        UserAdministrationErrorCode.SELF_PASSWORD_REISSUE_NOT_ALLOWED: (
            "自分自身の一時パスワードはこの画面から再発行できません。"
        ),
    }
    return messages_by_code.get(
        error.code, "利用者設定を変更できませんでした。再確認してください。"
    )


@never_cache
def index(request):
    """管理トップ。認可は中央middlewareで行う。"""

    return render(
        request,
        "management_portal/index.html",
        {"administrator_warnings": get_administrator_warnings(on_date=timezone.localdate())},
    )


@never_cache
@require_GET
def user_list(request):
    users = User.objects.only("id", "username", "role", "is_active", "cohort_number").order_by(
        "username", "pk"
    )
    return render(
        request,
        "management_portal/user_list.html",
        {
            "users": users,
            "administrator_warnings": get_administrator_warnings(on_date=timezone.localdate()),
        },
    )


@never_cache
@require_GET
def audit_log_list(request):
    """最小限の追記専用監査記録を、新しい順で表示する。"""

    audit_logs = AuditLog.objects.select_related("actor", "target").all()[:100]
    return render(request, "management_portal/audit_log_list.html", {"audit_logs": audit_logs})


@never_cache
@require_http_methods(["GET", "POST"])
def user_create(request):
    if request.method == "POST":
        if not evaluate_management_access(request).allowed:
            return redirect("management:user_list")
        confirmation_url = reverse("management:user_create")
        if not _has_recent_primary_mfa_reauthentication(request):
            return _mfa_reauthentication_redirect(request, confirmation_url)

        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                result = create_user_by_admin(
                    actor_id=request.user.pk,
                    username=form.cleaned_data["username"],
                    cohort_number=form.cleaned_data["cohort_number"],
                    role=form.cleaned_data["role"],
                )
            except UserAdministrationError as error:
                form.add_error(None, _user_administration_error_message(error))
            except (IntegrityError, ValidationError):
                form.add_error(None, "利用者を作成できませんでした。入力内容を確認してください。")
            else:
                return render(
                    request,
                    "management_portal/temporary_password_result.html",
                    {
                        "target": result.user,
                        "temporary_password": result.temporary_password,
                        "operation_label": "利用者を作成しました",
                        "return_url": reverse("management:user_list"),
                    },
                )
    else:
        form = UserCreationForm(initial={"role": User.Role.MEMBER})

    return render(request, "management_portal/user_create.html", {"form": form})


@never_cache
@require_http_methods(["GET", "POST"])
def user_edit(request, user_id):
    target = (
        User.objects.filter(pk=user_id)
        .only("id", "username", "role", "is_active", "cohort_number")
        .first()
    )
    if target is None:
        raise Http404("対象の利用者は見つかりません。")

    if request.method == "POST":
        if not evaluate_management_access(request).allowed:
            return redirect("management:user_list")
        confirmation_url = reverse("management:user_edit", args=[target.pk])
        if not _has_recent_primary_mfa_reauthentication(request):
            return _mfa_reauthentication_redirect(request, confirmation_url)

        form = UserAdministrationForm(request.POST, target=target)
        if form.is_valid():
            latest_target = User.objects.filter(pk=target.pk).only("id", "username").first()
            if latest_target is None or form.cleaned_data["username"] != latest_target.username:
                form.add_error("username", "対象のユーザー名が一致しません。再確認してください。")
            else:
                try:
                    result = update_user_administration_by_admin(
                        actor_id=request.user.pk,
                        target_user_id=latest_target.pk,
                        role=form.cleaned_data["role"],
                        is_active=form.cleaned_data["is_active"],
                    )
                except UserAdministrationError as error:
                    form.add_error(None, _user_administration_error_message(error))
                else:
                    if result.role_changed or result.active_state_changed:
                        messages.success(
                            request, f"{latest_target.username} の設定を更新しました。"
                        )
                    else:
                        messages.info(request, "変更はありませんでした。")
                    return redirect("management:user_edit", user_id=latest_target.pk)
    else:
        form = UserAdministrationForm(target=target)

    return render(request, "management_portal/user_edit.html", {"target": target, "form": form})


@never_cache
@require_http_methods(["GET", "POST"])
def user_password_reissue(request, user_id):
    target = User.objects.filter(pk=user_id).only("id", "username", "role", "is_active").first()
    if target is None:
        raise Http404("対象の利用者は見つかりません。")

    if request.method == "POST":
        if not evaluate_management_access(request).allowed:
            return redirect("management:user_list")
        confirmation_url = reverse("management:user_password_reissue", args=[target.pk])
        if not _has_recent_primary_mfa_reauthentication(request):
            return _mfa_reauthentication_redirect(request, confirmation_url)

        form = MFAResetConfirmationForm(request.POST)
        if form.is_valid():
            latest_target = User.objects.filter(pk=target.pk).only("id", "username").first()
            if latest_target is None or form.cleaned_data["username"] != latest_target.username:
                form.add_error("username", "対象のユーザー名が一致しません。再確認してください。")
            else:
                try:
                    result = reissue_temporary_password_by_admin(
                        actor_id=request.user.pk,
                        target_user_id=latest_target.pk,
                    )
                except UserAdministrationError as error:
                    form.add_error(None, _user_administration_error_message(error))
                else:
                    return render(
                        request,
                        "management_portal/temporary_password_result.html",
                        {
                            "target": result.user,
                            "temporary_password": result.temporary_password,
                            "operation_label": "一時パスワードを再発行しました",
                            "return_url": reverse("management:user_edit", args=[result.user.pk]),
                        },
                    )
    else:
        form = MFAResetConfirmationForm()

    return render(
        request,
        "management_portal/user_password_reissue.html",
        {"target": target, "form": form},
    )


@never_cache
@require_GET
def mfa_reset_search(request):
    username = request.GET.get("username", "")
    target = None
    searched = bool(username)
    if searched:
        target = (
            User.objects.filter(username=username)
            .only("id", "username", "role", "is_active", "cohort_number")
            .first()
        )
    return render(
        request,
        "management_portal/mfa_reset_search.html",
        {
            "username": username,
            "searched": searched,
            "target": target,
            "authenticator_types": _authenticator_summary(target.pk) if target else [],
        },
    )


@never_cache
@require_http_methods(["GET", "POST"])
def mfa_reset_confirm(request, user_id):
    target = (
        User.objects.filter(pk=user_id)
        .only("id", "username", "role", "is_active", "cohort_number")
        .first()
    )
    if target is None:
        raise Http404("対象の利用者は見つかりません。")

    if request.method == "POST":
        # middlewareに加え、実行直前にもDB上の管理アクセス状態を再検査する。
        if not evaluate_management_access(request).allowed:
            return redirect("management:mfa_reset_search")
        confirmation_url = reverse("management:mfa_reset_confirm", args=[target.pk])
        if not _has_recent_primary_mfa_reauthentication(request):
            return _mfa_reauthentication_redirect(request, confirmation_url)

        form = MFAResetConfirmationForm(request.POST)
        if form.is_valid():
            # GET表示時ではなく、POST時の最新DB値と一致させる。
            latest_target = User.objects.filter(pk=target.pk).only("id", "username").first()
            if latest_target is None or form.cleaned_data["username"] != latest_target.username:
                form.add_error("username", "対象のユーザー名が一致しません。再確認してください。")
            else:
                try:
                    result = reset_user_mfa_by_admin(
                        actor_id=request.user.pk,
                        target_user_id=latest_target.pk,
                    )
                except MFAResetError as error:
                    form.add_error(None, _reset_error_message(error))
                else:
                    messages.success(
                        request,
                        (
                            f"{latest_target.username} のMFAをリセットしました"
                            f"（削除した認証器: {result.deleted_authenticator_count}件）。"
                        ),
                    )
                    return redirect("management:mfa_reset_confirm", user_id=latest_target.pk)
    else:
        form = MFAResetConfirmationForm()

    return render(
        request,
        "management_portal/mfa_reset_confirm.html",
        {
            "target": target,
            "authenticator_types": _authenticator_summary(target.pk),
            "form": form,
        },
    )
