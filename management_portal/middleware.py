from urllib.parse import urlencode

from allauth.account.adapter import get_adapter
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.cache import add_never_cache_headers

from accounts.management_access import ManagementAccessReason, evaluate_management_access


def is_management_path(path: str) -> bool:
    """末尾スラッシュの有無を含め、管理ポータル配下だけを識別する。"""

    return path == "/management" or path.startswith("/management/")


class ManagementAccessMiddleware:
    """`/management`配下へStep 5Aの判定を一括適用する中央ゲート。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not is_management_path(request.path_info):
            return self.get_response(request)

        decision = evaluate_management_access(request)
        if decision.allowed:
            if request.path_info == "/management":
                response = redirect("management:index")
            else:
                response = self.get_response(request)
        else:
            response = self._denied_response(request, decision.reason)
        add_never_cache_headers(response)
        return response

    def _denied_response(self, request, reason):
        if reason is ManagementAccessReason.UNAUTHENTICATED:
            return redirect_to_login(request.get_full_path(), reverse("account_login"))
        if reason in {ManagementAccessReason.INACTIVE, ManagementAccessReason.NOT_ADMIN}:
            return render(
                request,
                "management_portal/permission_denied.html",
                status=403,
            )
        if reason is ManagementAccessReason.PASSWORD_CHANGE_REQUIRED:
            return redirect("account_change_password")
        if reason is ManagementAccessReason.PRIMARY_MFA_REQUIRED:
            messages.warning(
                request,
                "管理機能を利用するには、パスキーまたはTOTPの設定が必要です。",
            )
            return redirect("mfa_index")
        if reason is ManagementAccessReason.SESSION_MFA_REQUIRED:
            return self._redirect_to_mfa_reauthentication(request)
        raise AssertionError(f"未対応の管理アクセス判定理由です: {reason!r}")

    @staticmethod
    def _redirect_to_mfa_reauthentication(request):
        methods = get_adapter(request).get_reauthentication_methods(request.user)
        mfa_method = next(
            method for method in methods if method["id"].startswith("mfa_reauthenticate")
        )
        query = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"{mfa_method['url']}?{query}")
