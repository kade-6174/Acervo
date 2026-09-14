from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.account.forms import ChangePasswordForm, LoginForm
from allauth.mfa.base.forms import AuthenticateForm
from allauth.mfa.webauthn.forms import (
    AddWebAuthnForm,
    AuthenticateWebAuthnForm,
    EditWebAuthnForm,
    ReauthenticateWebAuthnForm,
)
from django import forms
from django.core.exceptions import ValidationError


class OneTimeCodeInput(forms.TextInput):
    """入力済みの認証コードをエラー応答へ再表示しない入力欄。"""

    def format_value(self, value):
        return None


class SensitiveCredentialInput(forms.HiddenInput):
    """WebAuthn credential JSONを失敗応答へ再表示しない。"""

    def format_value(self, value):
        return None


class AcervoLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"].label = "ユーザー名"
        self.fields["password"].label = "パスワード"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class AcervoChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["oldpassword"].label = "現在のパスワード"
        self.fields["oldpassword"].help_text = None
        self.fields["password1"].label = "新しいパスワード"
        self.fields["password2"].label = "新しいパスワード（確認）"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def save(self):
        super().save()
        if self.user.must_change_password:
            self.user.must_change_password = False
            self.user.save(update_fields=["must_change_password"])


class AcervoAuthenticateForm(AuthenticateForm):
    """allauth標準の照合をそのまま使うMFA認証画面用フォーム。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].label = "認証コード"
        self.fields["code"].widget = OneTimeCodeInput(
            attrs={
                "class": "form-control",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "autofocus": True,
            }
        )

    def clean_code(self):
        """allauth標準の制限到達エラーを画面共通のコードへ正規化する。"""
        try:
            return super().clean_code()
        except ValidationError as error:
            if error.code == "too_many_login_attempts":
                raise get_account_adapter().validation_error("rate_limited") from None
            raise


class AcervoAddWebAuthnForm(AddWebAuthnForm):
    """allauth標準のWebAuthn検証を維持した日本語の登録フォーム。"""

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("passwordless", True)
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "端末名（任意）"
        self.fields["name"].widget.attrs["class"] = "form-control"
        self.fields["passwordless"].label = "パスキーとして登録する"


class AcervoEditWebAuthnForm(EditWebAuthnForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "端末名"
        self.fields["name"].widget.attrs["class"] = "form-control"


class _AcervoWebAuthnAuthenticationForm:
    """allauth標準の照合結果だけを安全な表示用エラーコードへ正規化する。"""

    def clean_credential(self):
        try:
            return super().clean_credential()
        except ValidationError as error:
            if error.code == "too_many_login_attempts":
                raise get_account_adapter().validation_error("rate_limited") from None
            raise

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["credential"].widget = SensitiveCredentialInput()


class AcervoAuthenticateWebAuthnForm(_AcervoWebAuthnAuthenticationForm, AuthenticateWebAuthnForm):
    pass


class AcervoReauthenticateWebAuthnForm(
    _AcervoWebAuthnAuthenticationForm, ReauthenticateWebAuthnForm
):
    pass
