"""django-allauth MFAのURLルーティング。

Acervoでは最小特権の原則に基づき、必要なviewのみを明示的にマッピングする。
Step 4Bでは必要なWebAuthn管理・再認証・第二要素だけを明示的に公開する。
"""

from allauth.mfa.base import views as base_views
from allauth.mfa.recovery_codes import views as recovery_views
from allauth.mfa.totp import views as totp_views
from allauth.mfa.webauthn import views as webauthn_views
from django.urls import path
from django.views.decorators.cache import never_cache

from . import mfa_views

urlpatterns = [
    path("", never_cache(base_views.index), name="mfa_index"),
    path(
        "authenticate/",
        never_cache(mfa_views.authenticate),
        name="mfa_authenticate",
    ),
    path("reauthenticate/", base_views.reauthenticate, name="mfa_reauthenticate"),
    path("totp/activate/", never_cache(totp_views.activate_totp), name="mfa_activate_totp"),
    path("totp/deactivate/", totp_views.deactivate_totp, name="mfa_deactivate_totp"),
    path(
        "recovery-codes/",
        never_cache(recovery_views.view_recovery_codes),
        name="mfa_view_recovery_codes",
    ),
    path(
        "recovery-codes/generate/",
        never_cache(mfa_views.generate_recovery_codes),
        name="mfa_generate_recovery_codes",
    ),
    path(
        "recovery-codes/download/",
        recovery_views.download_recovery_codes,
        name="mfa_download_recovery_codes",
    ),
    path("webauthn/", never_cache(webauthn_views.list_webauthn), name="mfa_list_webauthn"),
    path("webauthn/add/", never_cache(mfa_views.add_webauthn), name="mfa_add_webauthn"),
    path(
        "webauthn/registration-options/",
        never_cache(mfa_views.begin_webauthn_registration),
        name="mfa_webauthn_registration_options",
    ),
    path("webauthn/login/", never_cache(mfa_views.login_webauthn), name="mfa_login_webauthn"),
    path(
        "webauthn/reauthenticate/",
        never_cache(webauthn_views.reauthenticate_webauthn),
        name="mfa_reauthenticate_webauthn",
    ),
    path(
        "webauthn/keys/<int:pk>/edit/",
        never_cache(webauthn_views.edit_webauthn),
        name="mfa_edit_webauthn",
    ),
    path(
        "webauthn/keys/<int:pk>/remove/",
        never_cache(mfa_views.remove_webauthn),
        name="mfa_remove_webauthn",
    ),
]
