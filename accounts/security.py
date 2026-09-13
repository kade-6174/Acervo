"""認証およびMFA関連のセキュリティヘルパー。"""

import binascii
from collections.abc import Sequence

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured


def validate_mfa_fernet_keys(keys: Sequence[str] | str | None) -> list[bytes]:
    """ACERVO_MFA_FERNET_KEYSの設定値を検証し、Fernet鍵バイト列のリストを返す。

    秘密鍵そのものをログやエラーメッセージに出力しない。
    """
    if keys is None:
        raise ImproperlyConfigured("ACERVO_MFA_FERNET_KEYSの設定が必要です。")

    if isinstance(keys, str):
        key_list = [k.strip() for k in keys.split(",") if k.strip()]
        if not key_list:
            raise ImproperlyConfigured("ACERVO_MFA_FERNET_KEYSの設定が必要です。")
    elif isinstance(keys, Sequence):
        if len(keys) == 0:
            raise ImproperlyConfigured("ACERVO_MFA_FERNET_KEYSの設定が必要です。")
        key_list = []
        for item in keys:
            if not isinstance(item, str) or not item.strip():
                raise ImproperlyConfigured(
                    "ACERVO_MFA_FERNET_KEYSに空または無効な形式の鍵が含まれています。"
                )
            key_list.append(item.strip())
    else:
        raise ImproperlyConfigured("ACERVO_MFA_FERNET_KEYSの形式が不正です。")

    validated: list[bytes] = []
    for key_str in key_list:
        try:
            key_bytes = key_str.encode("ascii")
            Fernet(key_bytes)
        except (ValueError, binascii.Error, Exception):
            raise ImproperlyConfigured(
                "ACERVO_MFA_FERNET_KEYSに不正なFernet鍵が含まれています。"
            ) from None
        validated.append(key_bytes)

    return validated
