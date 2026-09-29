"""Acervo固有のMFA view境界。

Recovery Codesの生成そのものはdjango-allauthへ委譲する。この薄いラッパーは、
再認証が古い状態での生成POSTだけを通常のGET遷移へ変換する。allauthの標準
``suspend_request()`` はPOSTをセッションへ保存し、再認証成功後に再送するため、
取消不能な再生成を利用者の再認証だけで実行してしまうのを防ぐ。
"""

from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.reauthentication import did_recently_authenticate
from allauth.account.models import Login
from allauth.account.utils import get_next_redirect_url
from allauth.core.internal.httpkit import add_query_params
from allauth.mfa.base import views as base_views
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes import views as recovery_views
from allauth.mfa.webauthn import views as webauthn_views
from allauth.mfa.webauthn.internal import auth as webauthn_auth
from allauth.mfa.webauthn.internal import flows as webauthn_flows
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
    JsonResponse,
)
from django.views.generic.edit import FormView
from fido2.webauthn import UserVerificationRequirement


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


_REGISTRATION_PASSWORDLESS_SESSION_KEY = "acervo.mfa.webauthn.registration_passwordless"


@login_required
def begin_webauthn_registration(request: HttpRequest) -> HttpResponse:
    """選択された登録方式に対応する、セッション結合済みchallengeを返す。"""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    response = _redirect_stale_post(request)
    if response:
        return response

    passwordless = request.POST.get("passwordless") == "true"
    options = webauthn_auth.begin_registration(request.user, passwordless)
    request.session[_REGISTRATION_PASSWORDLESS_SESSION_KEY] = passwordless
    return JsonResponse({"creation_options": options})


class AcervoAddWebAuthnView(webauthn_views.AddWebAuthnView):
    """選択内容をchallengeに結び付け、対応する登録方式だけを保存する。"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # allauth標準viewが事前に作る固定方式のchallengeは使わない。
        context.pop("js_data", None)
        webauthn_auth.clear_state()
        self.request.session.pop(_REGISTRATION_PASSWORDLESS_SESSION_KEY, None)
        return context

    def form_valid(self, form):
        passwordless = form.cleaned_data["passwordless"]
        requested_passwordless = self.request.session.pop(
            _REGISTRATION_PASSWORDLESS_SESSION_KEY, None
        )
        if requested_passwordless is None or requested_passwordless is not passwordless:
            form.add_error(None, "登録操作をもう一度開始してください。")
            return self.form_invalid(form)

        authenticator, recovery_codes = webauthn_flows.add_authenticator(
            self.request,
            name=form.cleaned_data["name"],
            credential=form.cleaned_data["credential"],
        )
        # credProps未対応の認証器でも、サーバーが要求した登録方式を保持する。
        authenticator.data["acervo_passwordless"] = passwordless
        authenticator.save(update_fields=["data"])
        self.did_generate_recovery_codes = bool(recovery_codes)
        return FormView.form_valid(self, form)


add_webauthn = AcervoAddWebAuthnView.as_view()


def begin_passwordless_authentication():
    server = webauthn_auth.get_server()
    options, state = server.authenticate_begin(
        user_verification=UserVerificationRequirement.REQUIRED
    )
    webauthn_auth.set_state(state)
    return dict(options)


class AcervoLoginWebAuthnView(webauthn_views.LoginWebAuthnView):
    def get(self, request, *args, **kwargs):
        if get_adapter().is_ajax(request):
            return JsonResponse({"request_options": begin_passwordless_authentication()})
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        authenticator = form.cleaned_data["credential"]
        login = Login(
            user=authenticator.user, redirect_url=get_next_redirect_url(self.request, "next")
        )
        return webauthn_flows.perform_passwordless_login(self.request, authenticator, login)


login_webauthn = AcervoLoginWebAuthnView.as_view()
