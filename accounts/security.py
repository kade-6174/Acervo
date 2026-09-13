"""認証およびMFA関連のセキュリティヘルパー。"""

import binascii
import ipaddress
import re
from collections.abc import Sequence
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, MultiFernet
from django.core.exceptions import ImproperlyConfigured

_DNS_HOSTNAME_RE = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)


def get_public_origin_and_rp_id(
    public_base_url: str, *, allow_localhost_http: bool = False
) -> tuple[str, str]:
    """公開URLを検証し、正規化済みOriginとWebAuthn RP IDを返す。"""
    try:
        parsed = urlsplit(public_base_url)
        port = parsed.port
    except (TypeError, ValueError):
        raise ImproperlyConfigured("ACERVO_PUBLIC_BASE_URLの形式が不正です。") from None

    hostname = parsed.hostname
    if (
        parsed.scheme not in {"https", "http"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ImproperlyConfigured("ACERVO_PUBLIC_BASE_URLの形式が不正です。")

    hostname = hostname.lower()
    if parsed.scheme != "https" and not (allow_localhost_http and hostname == "localhost"):
        raise ImproperlyConfigured("ACERVO_PUBLIC_BASE_URLにはhttpsの公開URLが必要です。")

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ImproperlyConfigured("ACERVO_PUBLIC_BASE_URLにIPアドレスは使用できません。")

    if not _DNS_HOSTNAME_RE.fullmatch(hostname):
        raise ImproperlyConfigured(
            "ACERVO_PUBLIC_BASE_URLにはDNS hostnameを設定する必要があります。"
        )

    origin = f"{parsed.scheme}://{hostname}"
    if port is not None:
        origin = f"{origin}:{port}"
    return origin, hostname


def validate_production_public_origin(
    public_base_url: str,
    allowed_hosts: Sequence[str],
    csrf_trusted_origins: Sequence[str],
) -> tuple[str, str]:
    """本番の固定公開OriginとRP IDの設定境界をfail-fastで検証する。"""
    origin, rp_id = get_public_origin_and_rp_id(public_base_url)
    if rp_id == "localhost":
        raise ImproperlyConfigured("本番のACERVO_PUBLIC_BASE_URLにlocalhostは使用できません。")

    exact_allowed_hosts = {
        host.lower()
        for host in allowed_hosts
        if host != "*" and not host.startswith(".") and "*" not in host
    }
    if rp_id not in exact_allowed_hosts:
        raise ImproperlyConfigured(
            "ACERVO_PUBLIC_BASE_URLのhostnameをDJANGO_ALLOWED_HOSTSへ完全一致で設定する必要があります。"
        )

    if origin not in csrf_trusted_origins:
        raise ImproperlyConfigured(
            "ACERVO_PUBLIC_BASE_URLのOriginをDJANGO_CSRF_TRUSTED_ORIGINSへ完全一致で設定する必要があります。"
        )
    return origin, rp_id


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


def get_mfa_multi_fernet(keys: Sequence[str] | str | None = None) -> MultiFernet:
    """ACERVO_MFA_FERNET_KEYSからMultiFernetインスタンスを構築する。"""
    from django.conf import settings

    if keys is None:
        keys = getattr(settings, "ACERVO_MFA_FERNET_KEYS", [])
    key_bytes_list = validate_mfa_fernet_keys(keys)
    return MultiFernet([Fernet(k) for k in key_bytes_list])
