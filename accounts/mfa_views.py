"""Acervo固有のMFA view境界。

Recovery Codesの生成そのものはdjango-allauthへ委譲する。この薄いラッパーは、
再認証が古い状態での生成POSTだけを通常のGET遷移へ変換する。allauthの標準
``suspend_request()`` はPOSTをセッションへ保存し、再認証成功後に再送するため、
取消不能な再生成を利用者の再認証だけで実行してしまうのを防ぐ。
"""

from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.reauthentication import did_recently_authenticate
from allauth.core.internal.httpkit import add_query_params
from allauth.mfa.base import views as base_views
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes import views as recovery_views
from allauth.mfa.webauthn import views as webauthn_views
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect


def _redirect_stale_post(request: HttpRequest) -> HttpResponse | None:
    """取消不能なPOSTを再認証後に自動再送しない。"""
    if request.user.is_authenticated and not did_recently_authenticate(request):
        methods = get_adapter().get_reauthentication_methods(request.user)
        if methods:
            return HttpResponseRedirect(
                add_query_params(
                    methods[0]["url"],
                    {REDIRECT_FIELD_NAME: request.get_full_path()},
                )
            )
    return None


def generate_recovery_codes(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """古い認証の再生成POSTを、再送しない再認証画面へ案内する。"""
    if request.method == "POST":
        response = _redirect_stale_post(request)
        if response:
            return response
    return recovery_views.generate_recovery_codes(request, *args, **kwargs)


class AcervoAuthenticateView(base_views.AuthenticateView):
    """標準ログインステージを保ち、登録済み鍵だけを選択肢として描画する。"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_webauthn"] = Authenticator.objects.filter(
            user=self.stage.login.user, type=Authenticator.Type.WEBAUTHN
        ).exists()
        return context


authenticate = AcervoAuthenticateView.as_view()


class AcervoRemoveWebAuthnView(webauthn_views.RemoveWebAuthnView):
    def post(self, request, *args, **kwargs):
        response = _redirect_stale_post(request)
        return response or super().post(request, *args, **kwargs)


remove_webauthn = AcervoRemoveWebAuthnView.as_view()
