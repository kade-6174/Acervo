"""django-allauth MFAのURLルーティング。

Acervoでは最小特権の原則に基づき、必要なviewのみを明示的にマッピングする。
Step 3AではTOTPおよびRecovery Codesの管理に必要な最小限のURLのみを公開し、
ログイン時の認証URL（mfa_authenticate）やWebAuthn関連URLは公開しない。
"""

from allauth.mfa.base import views as base_views
from allauth.mfa.recovery_codes import views as recovery_views
from allauth.mfa.totp import views as totp_views
from django.urls import path
from django.views.decorators.cache import never_cache

from . import mfa_views

urlpatterns = [
    path("", base_views.index, name="mfa_index"),
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
]
