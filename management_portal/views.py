from time import time
from urllib.parse import urlencode

from allauth.account.adapter import get_adapter
from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.management_access import evaluate_management_access
from accounts.mfa_reset import MFAResetError, MFAResetErrorCode, reset_user_mfa_by_admin
from accounts.models import User


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
            if item.get("id") in {"mfa_reauthenticate", "mfa_reauthenticate_webauthn"}
            and item.get("url")
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


@never_cache
def index(request):
    """管理トップ。認可は中央middlewareで行う。"""

    return render(request, "management_portal/index.html")


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
