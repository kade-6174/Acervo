"""Acervo固有のMFA view境界。

Recovery Codesの生成そのものはdjango-allauthへ委譲する。この薄いラッパーは、
再認証が古い状態での生成POSTだけを通常のGET遷移へ変換する。allauthの標準
``suspend_request()`` はPOSTをセッションへ保存し、再認証成功後に再送するため、
取消不能な再生成を利用者の再認証だけで実行してしまうのを防ぐ。
"""

from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.reauthentication import did_recently_authenticate
from allauth.core.internal.httpkit import add_query_params
from allauth.mfa.recovery_codes import views as recovery_views
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect


def generate_recovery_codes(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """古い認証の再生成POSTを、再送しない再認証画面へ案内する。"""
    if (
        request.method == "POST"
        and request.user.is_authenticated
        and not did_recently_authenticate(request)
    ):
        methods = get_adapter().get_reauthentication_methods(request.user)
        if methods:
            return HttpResponseRedirect(
                add_query_params(
                    methods[0]["url"],
                    {REDIRECT_FIELD_NAME: request.get_full_path()},
                )
            )
    return recovery_views.generate_recovery_codes(request, *args, **kwargs)
