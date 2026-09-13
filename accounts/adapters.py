from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from cryptography.fernet import InvalidToken
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .security import get_mfa_multi_fernet


class AcervoAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

    def get_password_change_redirect_url(self, request):
        return reverse("core:home")


class AcervoMFAAdapter(DefaultMFAAdapter):
    error_messages = {
        **DefaultMFAAdapter.error_messages,
        "incorrect_code": _("認証コードを確認できませんでした。"),
    }

    def get_multi_fernet(self):
        return get_mfa_multi_fernet()

    def encrypt(self, text: str) -> str:
        """TOTP秘密やリカバリーコードseed等の機密情報を先頭Fernet鍵で暗号化して返す。"""
        multi_fernet = self.get_multi_fernet()
        encrypted_bytes = multi_fernet.encrypt(text.encode("utf-8"))
        return encrypted_bytes.decode("ascii")

    def decrypt(self, encrypted_text: str) -> str:
        """暗号化された機密情報を登録済みFernet鍵群で復号して返す。"""
        if not isinstance(encrypted_text, str):
            raise SuspiciousOperation("MFA秘密情報の復号に失敗しました。")

        multi_fernet = self.get_multi_fernet()
        try:
            token_bytes = encrypted_text.encode("ascii")
            decrypted_bytes = multi_fernet.decrypt(token_bytes)
            return decrypted_bytes.decode("utf-8")
        except (InvalidToken, UnicodeError):
            raise SuspiciousOperation("MFA秘密情報の復号に失敗しました。") from None
